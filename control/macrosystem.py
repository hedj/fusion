import os
import sys
import re
import copy
import traceback
import time


handlers = dict()
handlers['emit'] = print

class AbortError(Exception):
  pass

class TimeOutError(Exception):
  def __init__(self, value):
    self.value = value

def sleep(secs):  # sleep, or bail out if received an abort message
  while(secs > 0 and not state.should_abort):
    time.sleep(0.1)
    secs = secs - 0.1
  if state.should_abort:
    state.should_abort = False
    raise AbortError()

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])

class State:
  pass

def abort():
  state.should_abort = True
  state.waiting = False

def emit(s):
  if state.should_abort:
    raise AbortError()
  else:
    handlers['emit'](s)

def showhelp():
  emit("New commands can be defined using the following_syntax:")
  emit("  def my_function(argument) -> dosomething(argument); dosomethingelse()")
  emit("Existing commands: ")
  for k,v in sorted(state.functions.items()):
    emit("   %s  ->  %s"%(k, v))

def wait(s, timeout=1):
  state.waiting_for = s
  state.waiting = True

  for p in state.backlog:
    if p.startswith(s):
      state.waiting = False
      state.backlog = []
  
  while timeout > 0 and not state.should_abort and state.waiting:
    time.sleep(0.2)
    timeout = timeout - 0.2

  if state.should_abort:
    raise AbortError()
    return

  if state.waiting:
    raise TimeOutError(s)
    return

  return

state = State()
state.locals = locals()
state.globals = globals()
state.should_abort = False
state.waiting = False
state.seq = 1
state.parent = None

state.functions = {
  'help()' : 'Primitive: shows this useful help',
  'emit(s)' : 'Primitive: sends the string s to the IRC channel',
  'wait(s, timeout=1)' : 'Primitive: waits to hear the string s from the IRC channel, or panics after timeout seconds',
  'process_line(s)' : "Primitive: lines starting with '@' are executed; lines starting with '!' are emitted;  lines starting with '#' are ignored"
}

inputs = [
  'RUNDIR = r"c:\data\default_rundir"',
  'def setup_rigols() -> emit("rigol: add_device 192.168.137.10 rigol_1"); wait("Connected to rigol", 5)',
  'def charge_enable(s) -> emit("bank: set charge_enable " + s)',
  'def charge_power(s) -> emit("bank: set charge_power " +s)',
  'def countdown(n) -> [ (emit("say: "+str(d)), wait("OK", 5)) for d in range(n,0,-1) ]',
  'def setup() -> setup_rigols(); countdown(5); charge_power("on"); sleep(0.5); charge_enable("on")',
  'def shutdown() -> charge_power("off"); sleep(0.1); charge_enable("off"); emit("Shutdown complete")',
  'def charge(V) -> emit("bank: charge "+str(V)); wait("charge : OK, value = 0", 30)',
  'def start_capture() -> emit("picoscope: start_capture 5000")',
  'def pulse() -> emit("bank: pulse"); wait("pulse : OK, value = 0", 10)',
  'def collect_data(dir) -> emit("picoscope: write_data " + dir); emit("rigol: write_data " + dir)',
  'def shot(V, dir) -> charge(V); start_capture(); pulse(); sleep(1); collect_data(dir); sleep(10)',
  'def run_file(filename) -> state.seq = 1; [  process_line(line.strip()) for line in open(filename).readlines() ]'
]

def feed_to_self(s):
   state.parent.consume( state.nick + ': ' + s )

def deferred_emit(s):
  feed_to_self( 'emit("%s")'%s )

def process_line(s):
  if state.should_abort:
    return

  if s.startswith("#"):
    return
  elif s.startswith("@"):
    feed_to_self( s[1:].strip() )
  elif s.startswith("!"):
    feed_to_self( 'emit("%s")'%s[1:].strip() )
  elif s.strip() == '':
    return
  else:
    try:
      elems = re.split('\s+',s)
      if len(elems) != 8:
        emit("ERROR: expected 8 elements, but got %d"%len(elems))
        emit("Offending line: %s"%s.strip())
        return
      elems_as_numbers = []
      for ix,v in enumerate(elems):  
        try:
          elems_as_numbers.append( int(elems[ix]) )
        except:
          emit("ERROR: could not parse element %d as integer"%(ix+1))
          emit("Offending line: %s"%s.strip())
          should_abort = True
          return
      if elems_as_numbers[0] > 0:
        deferred_emit("stepper: forward %s"%elems[0])
      elif elems_as_numbers[0] < 0:
        deferred_emit("stepper: backwards %s"%elems[0])
      if elems_as_numbers[1] > 0:
        feed_to_self('sleep(%d)'%elems_as_numbers[1])
      # set the parameters
      for i in [1,2,3,4]:
        deferred_emit("bank: set pulse_delay %d %d"%(i, elems_as_numbers[4]))
        feed_to_self("wait('set pulse_delay: OK')" )
        deferred_emit("bank: set pulse_width %d %d"%(i, elems_as_numbers[5]))
        feed_to_self("wait('set pulse_width: OK')" )

      deferred_emit("bank: set pulse_delay 5 %d"%elems_as_numbers[6])
      feed_to_self("wait('set pulse_delay: OK')" )

      deferred_emit("bank: set pulse_width 5 %d"%elems_as_numbers[7])
      feed_to_self("wait('set pulse_width: OK')" )

      # fire the shot and collect the data
      shot_cmd = 'shot(%d, os.path.join(RUNDIR, str("{:03}".format(state.seq))))'%(elems_as_numbers[2])
      feed_to_self(shot_cmd)
      state.seq = state.seq + 1

    except:
      handle_exception()
      emit("ERROR: Could not process line %s"%s.strip())
      state.should_abort = True


def demangle(s):
  if (s.strip().startswith('def')):
    s1 = re.sub('\s*->\s*', ':\n  ', s)
    s2 = re.sub(';\s*','\n  ', s1)
    return s2 + '\n'
  else:
    return s

def register_function(s):
  if s.startswith('def'):
    name = s.split(':')[0][3:].strip()
    state.functions[name] = ';'.join(s.split('\n')[1:])

def guarded_invoke(s,g,l):
  try:
    exec(demangle(s),g,l)
    if (s.startswith('def')):
      register_function(demangle(s))
  except AbortError as e:
    state.should_abort = False
    state.waiting = False
    handlers['emit']('Aborted')
  except TimeOutError as e:
    state.waiting = False
    state.should_abort = True
    handlers['emit']("Timed out waiting for '%s'"%e.value)
  except:
    handle_exception()
    emit("Could not understand \"%s\""%s)

for i in inputs:
  guarded_invoke(i, state.globals, state.locals)


