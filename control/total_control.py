import os
import serial
import ds1054z
import ds1054z.discovery
import picoscope
import bank_control
import stepper_control
import time
import csv

# A collection of useful utilities for controlling our system
# Must be connected to Rigol scopes via Ethernet

class TotalControl:

  scopeNames = dict()
  scopeIDs = dict()
  scopeAddress = dict()
  directory = 'c:/data'

  def __init__(self):
    self.connectToBank() 
    self.connectToSteppers()
    self.connectToRigolScopes()
    self.connectToPicoScopes()

  def connectToPicoScopes(self):
    pass

  def startup(self):
    self.bank.chargePower(1)
    time.sleep(0.5)
    self.bank.chargeEnable(1)
    time.sleep(0.5)
    return "device started"

  def shutdown(self):
    self.bank.chargeEnable(0)
    time.sleep(0.5)
    self.bank.chargeEnable(1)
    time.sleep(0.5)
    self.bank.reset()
    return "shutdown complete"

  def forward(self,mm):
    return self.stepper.forwards(mm)

  def backward(self,mm):
    return self.stepper.backwards(mm)

  def charge(self, voltage):
    return self.bank.charge(int(voltage))

  def pulse_all(self):
    return self.bank.pulse()

  def connectToRigolScopes(self):
    devicelist = ds1054z.discovery.discover_devices()
    self.ds1000zs = []
    for d in devicelist:
      print("Connecting to " + d["model"] + " at " + d["ip"] )
      dev = ds1054z.DS1054Z(d["ip"])
      self.ds1000zs.append( dev )
      self.scopeNames[dev.idn] = "SCOPE_"+d["ip"]
      self.scopeIDs[d["ip"]] = dev.idn
      self.scopeAddress[dev.idn] = d["ip"]

  def connectToSteppers(self):
    print("Connecting to stepper controllers")
    self.stepper = None
    try:
      self.stepper = stepper_control.StepperControl()
    except:
      print("Could not connect to stepper controllers")

  def connectToBank(self):
    print("Connecting to Bank Control mcu (Controllino)")
    self.bank = bank_control.BankControl()

  def showStatus(self):
    print("Connected Devices:")
    self.bank.showStatus()
    for d in self.ds1000zs:
      print("Rigol scope called %s with ip %s id %s"%(self.scopeNames[d.idn],self.scopeAddress[d.idn],d.idn)) 

  def setScopeName(self,ip,name):
    self.scopeNames[self.scopeIDs[ip]] = name;

  def writeCSVFiles(self,directory,sequencenum,label=''):
    data = self.getScopeScreenContents()
    seq = '{0:03d}'.format(sequencenum)
    outdir = os.path.join(directory, seq+label)
    if not os.path.exists(outdir):
      os.makedirs(outdir)
    for scope in sorted(data.keys()):
      this_scope_data = data[scope]
      outfile = os.path.join(outdir, "%s.csv"%scope)
      with open(outfile,"w") as csvfile:
        writer =  csv.writer(csvfile)
        # get length of time series
        length = len(data[scope]['Channel_1'][0])
        for i in range(length):
          line = []
          line.append(data[scope]['Channel_1'][1][i])
          for channel in sorted(this_scope_data.keys()):
            line.append(data[scope][channel][0][i])
          writer.writerow(line)

  def getScopeScreenContents(self):
    time.sleep(1)
    data = dict()
    for d in self.ds1000zs:
      data[self.scopeNames[d.idn]] = dict()
      for channel in range(4):
        data[self.scopeNames[d.idn]]["Channel_%d"%(channel+1)] = (d.get_waveform_samples(channel+1),d.waveform_time_values)
    return data



