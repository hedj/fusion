#!/usr/bin/python3
import serial
import time
import io

class StepperControl:
  def __init__(self, port="COM4", baudrate=9600):
    self.port = port
    self.baudrate = baudrate
    self.ser = serial.Serial(port, baudrate, timeout=1)
    self.ser.flushInput()
    self.ser.flushOutput()
    self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser,self.ser), newline='\n')
    time.sleep(1) # wait for device to come up

  def forward(self, distance):
    self.sio.write("F%d"%distance )
    self.sio.flush()

  def backwards(self, distance):
    self.sio.write("R%d"%distance)
    self.sio.flush()

  def stop(self):
    self.sio.write("stop")
    self.sio.flush()
