import picoscope
from picoscope import ps3000a
import io
import os
import time
import logging
import numpy as np
import h5py

# NB - This class only supports a single picoscope at the moment.

class PicoScope:

  device = None
  names = [ 'Channel_A', 'Channel_B', 'Channel_C', 'Channel_D' ]
  trigger_channel = 'External'
  trigger_threshold = 0.2 # V
  trigger_timeout = 5000 # ms

  def connect(self):
    self.device = ps3000a.PS3000a()

  def updateTrigger(self):
    self.device.setSimpleTrigger(self.trigger_channel, 
                                 threshold_V=self.trigger_threshold,
                                 timeout_ms=self.trigger_timeout) 
  
  def setDefaults(self):
    self.last_data = []  
    self.device.setChannel(channel="A", coupling="AC", VRange=1)
    self.device.setChannel(channel="B", coupling="AC", VRange=1)
    self.device.setChannel(channel="C", coupling="AC", VRange=1)
    self.device.setChannel(channel="D", coupling="AC", VRange=1)
    self.device.setSimpleTrigger(self.trigger_channel, threshold_V=0.2, timeout_ms=self.trigger_timeout) #trigger above 0.2V, otherwise force trigger after 5s.
    (self.actualSamplingInterval, self.nSamples, self.maxSamples) = self.device.setSamplingInterval(4e-9, 100e-3) # 4ns period, 100ms window
      
  def close(self):
    self.device.close()

  def setNames(self, names):
    self.names = names

  def startCollection(self):
    self.device.runBlock()

  def setChannel(self, channel, coupling, voltage_range):
    self.device.setChannel(channel=channel, coupling=coupling, VRange=int(voltage_range))

  def setTriggerThreshold(self, threshold):
    self.trigger_threshold = threshold
    self.updateTrigger()

  def setTriggerChannel(self, channel):
    self.trigger_channel = channel
    self.updateTrigger()

  def setTimeout(self, timeout):
    self.trigger_timeout = timeout
    self.updateTrigger()

  def collectData(self):
    data = []
    self.device.waitReady()
    data.append(self.device.getDataV('A', self.nSamples))
    data.append(self.device.getDataV('B', self.nSamples))
    data.append(self.device.getDataV('C', self.nSamples))
    data.append(self.device.getDataV('D', self.nSamples))
    self.device.stop()
    self.last_data = data
    return data

  def writeHDF5(self, path):
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
      os.makedirs(directory)
    print()
    h5f = h5py.File(path + '.h5')
    h5f.create_dataset(self.names[0], data = self.last_data[0], compression='gzip')
    h5f.create_dataset(self.names[1], data = self.last_data[1], compression='gzip')
    h5f.create_dataset(self.names[2], data = self.last_data[2], compression='gzip')
    h5f.create_dataset(self.names[3], data = self.last_data[3], compression='gzip')
    h5f.close()

  def test(self):
    self.connect()
    self.setDefaults()
    self.startCollection()
    self.collectData()
    self.close()
    return self.last_data

 