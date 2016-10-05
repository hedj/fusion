import bottom
import nslc
import threading
import time
import sys
import traceback
import serial
import queue
import asyncio
import re

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])


class SerialThread(threading.Thread):
  """Set up a thread to handle communication and error-recovery talking to the bank"""
  connected = False       # is the bank presently connected
  serial = None           # serial connection
  is_running = True       # flag to allow easy remote termination of thread
  lock = threading.Lock() # guard against data races accessing queue of messages to send
  is_up = False           # is the bank up
  q = queue.Queue()       # a queue of messages to send to the bank
  def __init__(self):
    super().__init__()
    self.lc = nslc.NSLC()

  def msg(self, bytestring):
    self.lock.acquire()
    bytes_to_send = self.lc.frame(bytestring)
    self.q.put(bytes_to_send)
    self.lock.release()

  def is_up(self):
    return self.is_up

  def add_error_handler(self, f):
    self.lc.add_error_handler(f)

  def add_frame_handler(self, f):
    self.lc.add_frame_handler(f)

  def connect(self):
    print("Connecting to bank...", end='')
    sys.stdout.flush()
    while(True):
      try:
        self.serial = serial.Serial(port=None, baudrate=250000,  bytesize=8, parity='N', stopbits=1)
        self.serial.port='COM3'
        self.serial.close()
        self.serial.open()
        self.connected = True
        break;
      except:
        handle_exception()
        print(".",end='')
        sys.stdout.flush()
        time.sleep(2)
    print("Connected to bank")

  def stop(self):
    print("Closing connection to bank")
    if (self.serial):
      self.serial.close()
    self.is_running = False

  def run(self):
    while(self.is_running):
      # ensure we're connected
      if not self.connected:
        self.is_up = False
        self.connect()
      try:
        # consume the next byte from the device
        if self.serial.in_waiting > 0:
          if (not self.is_up):
            print("Bank online")
            self.is_up = True
          self.lc.consume(self.serial.read())
      except:
        handle_exception()
        self.connected = False
        self.is_up = False
        self.serial.close()
        self.connect()
      # any messages to send the device?
      if (self.connected):
        if not self.q.empty():
          self.lock.acquire()
          m = self.q.get()
          try:
            self.serial.write(m)
          except:
            self.q.put(m)
            handle_exception()
          self.lock.release()


host = '192.168.137.3'
port = 6667
ssl = False

NICK = "bank"
CHANNEL = "#system"

switch_codes = {
  'MANUAL': 1,
  'OFF': 0,
  'AUTO': 2,
  'ERROR_MANUAL_AND_AUTO': 3,
  'TRIGGER_OFF': 4,
  'TRIGGER_MANUAL': 5,
  'TRIGGER_AUTO': 6,
  'ERROR_TRIGGER_MANUAL_AND_AUTO': 7
}

command_codes = {
  'get': 0,
  'set': 1,
  'reset': 2,
  'dry_run' : 4,
  'charge': 8,
  'pulse': 16,
  'abort' : 32
}

response_codes = {
  'OK' : 0,
  'AT_LEAST_ONE_BANK_MANUAL': 1,
  'WRONG_NUMBER_OF_ARGUMENTS': 2,
  'INVALID_BANK_NUMBER': 3,
  'BANK_VOLTAGE_OUT_OF_RANGE': 4,
  'ATTEMPT_TO_PULSE_WHILST_CHARGING': 5,
  'ALREADY_PULSING': 6,
  'TIMED_OUT': 7,
  'ALREADY_AT_TARGET_VOLTAGE': 8,
  'ALREADY_CHARGING': 9,
  'ATTEMPT_TO_CHARGE_WHILST_PULSING': 10,
  'CHARGE_RATE_ABNORMAL': 11,
  'BAD_SWITCH_STATE': 12,
  'ILLEGAL_VALUE_FOR_ARGUMENT': 13,
  'ABORTED': 14
}

parameter_codes = {
  'pulse_width' : 0,
  'pulse_delay' : 1,
  'charge_enable': 2,
  'charge_power' : 4,
  'hv_state' : 8,
  'hv_voltage' : 16,
  'bank_voltage': 32,
  'switch_state': 64
}

symbolic_names = {
  'true' : 1,
  'false' : 0,
  'on' : 1,
  'off' : 0,
  '0' : 0,
  '1' : 1,
  '2' : 2,
  '3': 3,
  '4': 4,
  '5': 5
}

def make_get_cmd(elems):
  try:
    c = command_codes[elems[0]]
    p = parameter_codes[elems[1]]
    if len(elems) > 2:
      return bytes([c,p, int(elems[2])])
    else:
      return bytes([c,p])
  except:
    handle_exception()
    return None

def make_set_cmd(elems):
  try:
    c = command_codes[elems[0]]
    p = parameter_codes[elems[1]]
    v = symbolic_names[elems[2]]
    if len(elems) > 3:
      return bytes([c,p,v,int(elems[3])])
    else:
      return bytes([c,p,v])
  except:
    handle_exception()
    return None

def sysmsg(b, s):
  b.send("PRIVMSG", target=CHANNEL, message=s)

serial_thread = SerialThread()

def notify_parse_error(b,target):
  sysmsg(b,"Could not parse that. type '%s: help' for help"%NICK)

def handle_privmsg(cmd,target,b):
  elems = re.split('\s+',cmd)
  if elems[0] == 'help':
    sysmsg(b,"Usage instructions for %s:"%NICK)
    sysmsg(b,"  -- SUPPORTED COMMANDS -- ")
    for k in command_codes:
      sysmsg(b,"    %s"%k)
    sysmsg(b,"  -- SUPPORTED PARAMETERS ( use with get / set )-- ")
    for k in parameter_codes:
      sysmsg(b,"    %s"%k)

    sysmsg(b," -- EXAMPLES -- ")
    sysmsg(b,"'%s: get hv_voltage'    : retrieve bank HV voltage"%NICK)
    sysmsg(b,"'%s: charge 100'        : charges bank to 100V"%NICK)
    sysmsg(b,"%s is case-insensitive and understands some symbolic names"%NICK)
    sysmsg(b,"e.g '%s: set charge_enable on' and '%s: set CHARGE_EnAble 1'  will both work fine"%(NICK,NICK))
    return

  if elems[0] == 'reset':
    serial_thread.msg( bytes([ command_codes['reset']]))
    return

  if elems[0] == 'stop':
    serial_thread.msg( bytes([ command_codes['abort']]))
    return

  if elems[0] == 'abort':
    serial_thread.msg( bytes([ command_codes['abort']]))
    return

  if elems[0] == 'pulse':
    if len(elems) > 1:
      sysmsg(b, "'pulse' takes no arguments")
    else:
      serial_thread.msg( bytes([ command_codes['pulse']]))
    return

  if elems[0] == 'dry_run':
    if len(elems) < 2:
      sysmsg(b, "dry_run expects one of 'true', 'false', '1' or '0' as arguments")
      return
    try:
      v = int(symbolic_names[elems[1]])
      serial_thread.msg( bytes( [ command_codes['dry_run'], v ] ))
    except:
      handle_exception()
      sysmsg(b, "ERROR: could not understand that")
    return

  if elems[0] == 'charge':
    if len(elems) < 2:
      sysmsg(b, "charge expects an (integer) voltage as argument")
      return
    try:
      v = int(elems[1])
      serial_thread.msg(bytes([ command_codes['charge'], int(v/256), int(v % 256)]))
    except:
      handle_exception()
      sysmsg(b, "charge expects an (integer) voltage as argument")
    return

  if elems[0] == 'get':
    if len(elems) < 2:
       notify_parse_error(b,target)
    try:
      command_bytes =  make_get_cmd(elems)
      if (command_bytes != None):
        serial_thread.msg( command_bytes )
      else:
        notify_parse_error(b,target)
    except:
      handle_exception()
      notify_parse_error(b,target)
    return

  if elems[0] == 'set':
    if len(elems) < 3:
       notify_parse_error(b,target)
    try:
      command_bytes =  make_set_cmd(elems)
      if (command_bytes != None):
        serial_thread.msg( command_bytes )
      else:
        notify_parse_error(b,target)
    except:
      handle_exception()
      notify_parse_error(b,target)
    return

  notify_parse_error(b, target)


bot = bottom.Client(host=host, port=port, ssl=ssl)

def grab_name(byte, d):
  r = ''
  for k,v in d.items():
    if v == byte:
      r = k
      break
  return r


def handle_bank_message(b):
  if b == b'U':    # Bank heartbeat
    pass
  else:
    if len(b) == 5:  # Is a response message
      if (b[0] == 99):  # switch-state change message
        switch = b[1]
        old_state = grab_name(b[2], switch_codes)
        new_state = grab_name(b[4], switch_codes)
        if ( switch == 6 ):
          bot.send("PRIVMSG", target=CHANNEL, message="HV BIAS switch change from %s to %s"%(old_state,new_state))
        else:
          bot.send("PRIVMSG", target=CHANNEL, message="Bank %d switch change from %s to %s"%(switch,old_state,new_state))
      else:
        cmd = grab_name(b[0], command_codes)
        parameter = grab_name(b[1], parameter_codes)
        response = grab_name(b[2], response_codes)
        val = 256*b[3] + b[4]
        if response == 'OK':
          bot.send("PRIVMSG",target=CHANNEL, message="%s %s: %s, value = %d"%(cmd, parameter, response, val))
        else:
          bot.send("PRIVMSG",target=CHANNEL, message="%s %s: ERROR %s, value = %d"%(cmd, parameter, response, val))

    else:
      if (len(b) > 2):
        cmd = grab_name(b[0], command_codes)
        parameter = grab_name(b[1], parameter_codes)
        if cmd == 'get' and parameter =='switch_state':
          result = 'Switch states: '
          for v in b[2:]:
            result += grab_name(v, switch_codes) + " "
          bot.send("PRIVMSG",target=CHANNEL, message=result)
          return
        elif cmd == 'get' and parameter == 'bank_voltage':
          result = "LOWER: "  
          for i in range(4):
            result += str( b[2*i+2]*256 + b[2*i+3] ) + "V "
          bot.send("PRIVMSG",target=CHANNEL, message=result)
          result = "UPPER: "  
          for i in range(4):
            result += str( b[2*i+10]*256 + b[2*i+11] ) + "V "
          bot.send("PRIVMSG",target=CHANNEL, message=result)

def handle_invalid_frame(b):
  print("Found invalid frame %s"%b)

serial_thread.add_frame_handler(handle_bank_message)
serial_thread.add_error_handler(handle_invalid_frame)
serial_thread.start()


@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
  print("Connected to IRC server")
  bot.send('NICK', nick=NICK)
  bot.send('USER', user=NICK,
    realname='stepper control IRC bot')
  bot.send('JOIN', channel=CHANNEL)

@bot.on("client_disconnect")
async def reconnect(**kwargs):
  print("Lost connection to IRC server")
  await asyncio.sleep(3, loop=bot.loop)
  bot.loop.create_task(bot.connect())

@bot.on('PING')
def keepalive(message, **kwargs):
  bot.send('PONG', message=message)

@bot.on('PRIVMSG')
def message(nick, target, message, **kwargs):

  if nick == NICK:
    return

  if message.startswith('STOP'):
    serial_thread.msg( bytes([ command_codes['reset']]))
    return

  if message.startswith(NICK + ': '):
    stripped = message.split(NICK+': ')
    if len(stripped) > 1:
      cmd = ''.join(stripped)
      handle_privmsg(cmd.strip().lower(),target,bot)

try:
  bot.loop.create_task(bot.connect())
  bot.loop.run_forever()
finally:
  serial_thread.stop()