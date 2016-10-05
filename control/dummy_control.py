import os
import time

class DummyControl:

  def __init__(self):
    pass

  # Command handlers

  def CMD_print(self, s, dryrun):
    if (dryrun):
      return True
    print(s)
    return True

  def CMD_wait(self,s, dryrun):
    if dryrun:
      try:
        a = int(s)
        return True
      except:
        return False
    time.sleep(int(s))
    return True

