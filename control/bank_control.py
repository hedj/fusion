#!/usr/bin/python3
import serial
import io


class BankControl:
  def __init__(self, port="COM3", baudrate=230400):
    self.port = port
    self.baudrate = baudrate
    self.ser = serial.Serial(port, baudrate, timeout=1)
    self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser,self.ser), newline='\n')
    self._waitForReady()

  def _waitForReady(self):
    while(True):
      line = self.sio.readline()
      if (line[0:2] == '> '):  # device has sent us all the data
        return

  def showStatus(self):
    print("Bank Control running on port %s"%self.port)

  def invoke(self, cmd, show=True):
    out = ''
    self.sio.write(cmd + '\n')
    self.sio.flush()
    while(True):
      line = self.sio.readline()
      out += line
      if (line[0:2] == 'E '):
        print(line)
      if (line[0:2] == '> '):  # device has sent us all the data
        break
    if (show):
      print(out)
    return out

  def chargePower(self, val ):
    if (val == 0 or val == 1):
      self.invoke("!chgPWR %d"%val)
    else:
      return "Error! Invalid value for chargePower"

  def chargeEnable(self, val ):
    if (val == 0 or val == 1):
      self.invoke("!chgEnbl %d"%val)
    else:
      return "Error! Invalid value for chargeEnable"

  def help(self):
    print(self.invoke("help"))

  def charge(self, voltage):
    return self.invoke("charge_V %d"%voltage)

  def pulse(self):
    return self.invoke("pulse")

  def reset(self):
    self.chargePower(0)
    self.chargeEnable(0)
    self.sio.write('reset\n')
    self.sio.flush()
    self._waitForReady()
