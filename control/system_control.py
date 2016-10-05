#!/usr/bin/python3
"""
Provide a monitoring and control interface to the shielded-grid fusion system.
A thread is established for each device and a uniform query and command interface
is provided.
"""

import os
import time
import serial
import threading
import logging
import queue
import io
import sys
import json
import traceback
import ds1054z
import ds1054z.discovery

import timeit

def handle_err():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])

# Configure logging

logging.basicConfig(format='%(asctime)s %(message)s')

class SequenceThread(threading.Thread):
  def __init__(self):
    super().__init__()
    self.running = False
    self.sequence = []
    self.delay = 1
    self.step = 0
    self.step_callbacks = []
    self.execution_callbacks = []
  
  def set_step(self, n):
    if (n <= len(self.sequence)):
      self.step = n
      self.indicate_step(n)
    else:
      self.running = False

  def indicate_step(self,n):
    for f in self.step_callbacks:
      try:
        f(n)
      except:
        pass

  def get_sequence(self):
    return self.sequence
  
  def add_step(self,step):
    self.sequence.append(step)

  def add_step_callback(self,fn):
    self.step_callbacks.append(fn)

  def add_execution_callback(self,fn):
    self.execution_callbacks.append(fn)

  def set_delay(self,delay):
    self.delay = delay

  def run_step(self):
    try:
      seq = self.sequence[self.step - 1]
      for f in self.execution_callbacks:
        try:
          f(seq, self.step)
        except:
          handle_err()
      if ( self.step == len(self.sequence) or not self.running ):
        return
      print("Step done; sleeping before next step ...")
      t = 0
      while(t <= max(self.delay,0.1)):
        time.sleep(1)
        t = t+1
    except:
      handle_err()
  
  def run(self):
    while(True):
      if self.running:
        if ( self.step >= len(self.sequence)):
          print("Finished Sequence")
          self.set_step(0)
          self.indicate_step(-1)
          self.running = False
        else:
          self.set_step(self.step + 1)
          print("Running step %d"%(self.step))
          self.run_step()
      else:
        time.sleep(0.1)

      

class BankControlLog:

  messages = dict()
  listeners = dict()
  current_state = dict()
  memory_depth = 100  # number of lines to save
  bank_is_ready = False
  decoder = json.JSONDecoder()
  
  def __init__(self):
    self.lock = threading.Lock()
    for category in [ "commands", "replies", "errors", "events", "info", "status" ]:
      self.messages[category] = []
      self.listeners[category] = []

  def history(self, label):
    """ Get the last few messages for a given category """
    if label in keys(self.messages):
      self.lock.acquire()
      r = self.messages[label]
      self.lock.release()
      return r
    else:
      return []

  def add_listener(self,category,f):
    if not category in self.listeners.keys():
      log.warning("Adding new category %s"%category)
      self.listeners[category] =[]
    self.listeners[category].append(f)

  def get_current_state(self):
    self.current_state["ready"] = self.bank_is_ready 
    return self.current_state

  def append(self,data,label):
    # Notify all listeners
    if label in self.listeners.keys():
      for f in self.listeners[label]:
        try:
          f(data)
        except:
          pass
    # save the message for posterity
    self.lock.acquire()
    l = self.messages[label]
    l.append(data)
    if len(l) > self.memory_depth:
      l = l[1:]
    self.lock.release()

  def info(self,data):
    logging.debug(data)
    self.append(data, "info")
  
  def status(self,data):
    # parse out the field, set in current_state
    logging.info(data)
    try:
      d = eval(data)
      for k in d.keys():
        v = d[k]
        try:
          v = eval(v)
        except:
          pass
        if k in self.current_state.keys():
         if self.current_state[k] != v:
           self.current_state[k] = v
           self.append(data,"status")
        else:
          self.current_state[k] = v
          self.append(data,"status")
        
       
    except:
      handle_err()
      logging.warning("Could not evaluate message %s"%data)

  def event(self,data):
    logging.info(data)
    self.append(data, "events")

  def ack(self,data):
    logging.info('BankControl: sent ' + data)
    self.append(data, "commands")

  def response(self,data):
    logging.info('BankControl: responded ' + data)
    self.append(data, "replies")

  def error(self,data):
    logging.error(data)
    self.append(data, "errors")

class StepperControlThread(threading.Thread):
  def __init__(self, q, lock, port="COM4", baudrate=9600):
    super().__init__()
    self.port = port
    self.baudrate = baudrate
    self.connected = False
    self.q = q
    self.lock = lock

  def connect(self):
    while(not self.connected):
      try:
        logging.warning("Trying to connect to Stepper Controller")
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        self.ser.flushInput()
        self.ser.flushOutput()
        self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser,self.ser), newline='\n')
        self.connected = True
      except:
        time.sleep(5) # wait for device to come up
    logging.warning("Connected to Stepper Controller")

  def run(self):
    self.connect()
    while(True):
      if (not self.connected):
        self.connect()
        
      try:
        if not self.q.empty():
          k = self.q.get()
          print("Sending to stepper: %s"%k)
          self.sio.write(k) 
          self.sio.flush()
        time.sleep(0.1)
      except:
        pass
   





class BankControlThread(threading.Thread):
  """ A simple thread to listen to the serial device, and relay messages """
  port = 'COM3'
  baudrate = 115200
  ser = None
  sio = None
  q = None
  log = None

  def __init__(self,q,log,lock,port='COM3',baudrate=115200):
    super().__init__()
    self.port = port
    self.baudrate = baudrate
    self.q = q
    self.lock = lock
    self.log = log
    self.connected = False

  def process_line(self,line):
   #(line)
    stripped = line[2:].rstrip()
    if line[0:2] == '> ':
      self.log.bank_is_ready = True
    elif line[0:2] == 'E ':
      self.ready = False
      self.log.error(stripped)
    elif line[0:2] == 'C ':
      self.log.bank_is_ready = False
      self.log.ack(stripped)
    elif line[0:2] == '! ':
      self.log.bank_is_ready = False
    elif line[0:2] == 'X ':
      self.log.event(stripped)
    elif line[0:2] == 'I ':
      self.log.info(stripped)
    elif line[0:2] == 'M ':
      self.log.status(stripped)
    elif line[0:2] == 'R ':
      self.log.response(stripped)
    else:
      logging.warning("BankControlThread: Unhandled message: %s"%line)

  def connect(self):
    self.log.current_state["connected"] = False
    while(not self.connected):
      try:
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        #self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser,self.ser), newline='\n')
        self.connected = True
        self.log.current_state["connected"] = True
        self.q.put("!poll 1\n")
      except:
        handle_err()
        logging.error("BankControl failed to establish serial connection. Retrying")
        time.sleep(5)

  def handle_messages(self):
    while(True):
      try:
        #line = self.sio.readline()
        if self.ser.inWaiting():
          line = bytes.decode(self.ser.readline(), 'ascii')
          if( line != ''):
            self.process_line(line)
        if self.log.bank_is_ready:
          self.lock.acquire()
          if not self.q.empty(): 
            k = self.q.get()
            print("Sending to bank: %s"%k.rstrip())
            self.ser.write(k.encode('ascii'))
            self.ser.flushOutput()
          self.lock.release()
      except:
        handle_err()
        self.ser.close()
        self.connect()

  def run(self):
    self.connect()
    try:
      self.handle_messages()

    except:
      handle_err()
      self.ser.close()

class SequenceControl:
  def __init__(self):
    self.thread = SequenceThread()
    self.thread.daemon = True
    self.thread.start()
  def register_step_callback(self,f):
    self.thread.add_step_callback(f)
  def register_execution_callback(self,f):
    self.thread.add_execution_callback(f)
  def set_delay(self,d):
    self.thread.set_delay(d)
  def set_step(self,n):
    self.thread.set_step(n)
  def add_step(self,step):
    self.thread.add_step(step)
  def start(self):
    self.thread.running = True
  def stop(self):
    self.thread.running = False
  def get(self):
    return self.thread.get_sequence()
  def running(self):
    return self.thread.running
  def set(self, seq):
    self.thread.running = False
    self.thread.sequence = seq


class StepperControl:
  def __init__(self):
    self.current_position = 0
    self.workQueue = queue.Queue(1)
    self.queuelock = threading.Lock()
    self.thread = StepperControlThread(self.workQueue, self.queuelock)
    self.thread.daemon = True
    self.thread.start()

  def is_connected(self):
    return self.thread.connected

  def ready(self):
    return (self.is_connected() and self.workQueue.empty())

  def zero(self):
    self.current_position = 0

  def go(self, position):
    if position > self.current_position:
      self.forward(position-self.current_position)
    if position < self.current_position:
      self.backwards(self.current_position - position)

  def forward(self, distance):
    self.workQueue.put("F%d"%distance )
    self.current_position += distance
  
  def backwards(self, distance):
    self.workQueue.put("R%d"%distance )
    self.current_position -= distance

  def stop(self, distance):
    self.workQueue.put("stop" )


class RigolDS1000Thread(threading.Thread):

  scopes_by_ip = dict()
  channel_lists = dict()
  scope_connect_callbacks = []
  scope_disconnect_callbacks = []
  error_callbacks = []
  scope_images = dict()

  def __init__(self):
    super().__init__()

  def getScopeByIP(self, ip):
    print(self.scopes_by_ip.keys())
    if ip in self.scopes_by_ip.keys():
      print("Found requested key")
      return self.scopes_by_ip[ip]
    else:
      return None

  def getScopeScreenContents(self):
    data = dict()
    for ip,d in self.scopes_by_ip.items():
      data[ip] = dict()
      for channel in range(4):
        data[ip]["Channel_%d"%(channel+1)] = (d.get_waveform_samples(channel+1),d.waveform_time_values)
    return data

  #def _update_scope_image(self,ip):
  #  self.scope_images[ip] = self.scopes_by_ip[ip].display_data

  def add_device(self, ip):
    try:
      self.scopes_by_ip[ip] = ds1054z.DS1054Z(ip)
      for f in self.scope_connect_callbacks:
        try:
          f(ip)
        except:
          handle_err()
   
    except:
      for g in self.error_callbacks:
        try:
          g("Failed to add device %s"%ip)
        except:
          handle_err()
   # self._update_scope_image(ip)

  def onError(self, f):
    self.error_callbacks.append(f)
  
  def onConnect(self, f):
    self.scope_connect_callbacks.append(f)

  def onDisconnect(self, f):
    self.scope_disconnect_callbacks.append(f)

  def remove_device(self, ip):
    self.scopes_by_ip.pop(ip)
    for f in self.scope_disconnect_callbacks:
      try:
        f(ip)
      except:
        handle_err()

  def run(self):
    while(True):
      time.sleep(0.2)
      
class RigolControl:
  def __init__(self):
    self.thread = RigolDS1000Thread()
    self.thread.daemon = True
  def start(self):
    self.thread.start()
  def onConnect(self, f):
    self.thread.onConnect(f)
  def onError(self, f):
    self.thread.onError(f)
  def onDisconnect(self, f):
    self.thread.onDisconnect(f)
  def get(self,ip):
    return self.thread.getScopeByIP(ip)
#  def image(self, ip):
#    return self.thread.scope_images[ip]
  def scope_screen_contents(self):
    return self.thread.getScopeScreenContents()

class BankControl:
  def __init__(self):
    self.log = BankControlLog()
    self.workQueue = queue.Queue(5)
    self.queuelock = threading.Lock()
    self.thread = BankControlThread(self.workQueue,
                                    self.log,
                                    self.queuelock,
                                    port='COM3',
                                    baudrate=115200)
    self.thread.daemon = True
    self.thread.start()

  def ready(self):
    return (self.workQueue.empty() and self.log.bank_is_ready)

  def invoke(self,string):
    self.queuelock.acquire()
    self.workQueue.put(string + '\n')
    self.queuelock.release()

  def add_status_callback(self, fn):
    self.log.add_listener("status", fn)
