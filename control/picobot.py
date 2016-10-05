import bottom
import picointerface
import asyncio
import numpy
import time
import traceback
import sys

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "picoscope"
CHANNEL = "#system"


bot = bottom.Client(host=host, port=port, ssl=ssl)

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])
  traceback.print_tb(sys.exc_info()[2])
class State:
    pass

state = State()
state.p = picointerface.PicoScope()

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)

def start_capture(message):
  try:
    state.p.setTimeout(int(message))
    state.p.startCollection()
    state.p.collectData()
    sysmsg("capture complete; use 'write_data' to save to disk as HDF5")
  except:
    handle_exception()
    sysmsg('ERROR: could not set timeout value to provided value %s'%message)

def write_data(message):
  if message == '':
    t = time.gmtime()
    timestamp = '_'.join([ str(t.tm_year), str(t.tm_mon), str(t.tm_mday), str(t.tm_hour), str(t.tm_min), str(t.tm_sec)] )
    path = 'C:\data\pico\%s'%timestamp
  else:
    path = message
  state.p.writeHDF5(path)
  sysmsg("Wrote HDF5 file %s"%(path + '.h5'))

def reset_scope(message):
  state.p.close()
  state.p.connect()
  state.p.setDefaults()

def set_names(message):
  elems = message.split(' ')
  if len(elems) != 4:
    sysmsg("ERROR: Supplied %d names, but expected 4!"%len(elems))
    return
  state.p.setNames(elems)

def usage(message):
  sysmsg("%s understands the following commands:"%NICK)
  for k,v in commands.items():
    sysmsg('  ' + k + ' : ' + v[0])

def status(message):
  if state.p.device != None:
    sysmsg("Picoscope attached")
    sysmsg("Channel names are : %s"%', '.join(state.p.names))
  else:
    sysmsg("No attached picoscopes")

def set_trig_thresh(message):
  try:
    f = float(message)
    if abs(f) > 20.0:
      sysmsg("ERROR: Trigger voltage out of range")
    else:
      state.p.setTriggerThreshold(f)
  except:
    sysmsg("ERROR: Could not parse that as a number")

def __channels():
  return {
    'A' : 'A',
    state.p.names[0] : 'A',
    'B' : 'B',
    state.p.names[1] : 'B',
    'C' : 'C',
    state.p.names[2] : 'C',
    'D' : 'D',
    state.p.names[3] : 'D',
    'Ext': 'External',
    'External' : 'External'
  }

def canonical_channel(s):
  names = __channels()
  for k,v in names.items():
    if s.strip().lower() == k.lower():
      return v
  return None

def set_trig_channel(message):
  c = message.strip()
  which_channel = canonical_channel(c)
  if which_channel == None:
    sysmsg("ERROR: Valid trigger channels are: ")
    for k in __channels().keys():
      sysmsg('  ' + k)
  else:
    state.p.setTriggerChannel(which_channel)
    if which_channel != message.strip():
      sysmsg("Set trigger channel to %s (%s)"%(which_channel, message.strip()))
    else:
      sysmsg("Set trigger channel to %s"%which_channel)

def channel_config(message):
  elems = message.split(' ')
  if len(elems) < 3:
    sysmsg("ERROR: Need arguments <NAME> <COUPLING> <VOLTAGE_RANGE>")
    sysmsg("  e.g to set channel D to AC coupling and 5V range, use 'channel_config D AC 5'")
    return
  c = canonical_channel(elems[0])
  if c == None:
    sysmsg("ERROR: No such channel %s"%(elems[0]))
    return
  if elems[1].upper() not in ["AC", "DC"]:
    sysmsg("ERROR: Channel coupling should be 'AC' or 'DC")
    return
  try:
    f = float(elems[2])
  except:
    sysmsg("ERROR: Invalid voltage range (e.g 1, 5, 20 )")
    return
  if f > 20.0:
    sysmsg("ERROR: Invalid voltage range (must be <= 20)")
    return
  state.p.setChannel(c, elems[1].upper(), f)
  sysmsg("Set Channel %s to %s coupling and voltage range +/- %d v"%(c, elems[1].upper(), f))


#def setChannel(self, channel, coupling, voltage_range):
#def setTriggerThreshold(self, threshold):
#def setTimeout(self, timeout):
   
commands = {
    'start_capture' : ( 'start_capture <TIMEOUT_MS> arms the picoscope for capture', start_capture),
    'channel_config' : ('configures a chosen channel; e.g  channel_config <NAME> <COUPLING> <VOLTAGE_RANGE>', channel_config),
    'trig_threshold'  : (  'sets the voltage threshold (in Volts) used for triggering;  e.g trig_threshold 0.2', set_trig_thresh ),
    'trig_channel'  : (  'sets the channel used for triggering;  e.g "trig_channel A"  or "trig_channel External"', set_trig_channel ),
    'status'        : ( 'shows device configuration', status),
    'reset_scope'   : ( 'disconnects and reconnects scope', reset_scope),
    'write_data' : ( r'write_data <PATH_PREFIX> writes the last data set to disk in HDF5 format  (e.g write_data c:\data\foo)', write_data),
    'channel_names' : ( 'channel_names <NAME_1> <NAME_2> <NAME_3> <NAME_4>   sets the names for the four device channels', set_names),
    'help' : ( 'shows this useful message', usage),
}

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    state.p.connect()
    state.p.setDefaults()
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='iamthetalkingrobot')
    bot.send('JOIN', channel=CHANNEL)

@bot.on("client_disconnect")
async def reconnect(**kwargs):
    await asyncio.sleep(3, loop=bot.loop)
    bot.loop.create_task(bot.connect())
    state.p.close()

@bot.on('PING')
def keepalive(message, **kwargs):
    bot.send('PONG', message=message)

@bot.on('PRIVMSG')
def message(nick, target, message, **kwargs):
    """ Echo all messages """
    # Don't echo ourselves
    if nick == NICK:
        return
    if message.startswith(NICK + ": "):
        stripped = message.split(NICK+': ')
        if len(stripped) > 1:
          command = ''.join(stripped[1:]).strip()
          base = command.split()[0]
          if base in commands.keys():
            commands[base][1](' '.join(command.split()[1:]))
          else:
            sysmsg("ERROR: Command not understood")

try:
  bot.loop.create_task(bot.connect())
  bot.loop.run_forever()
finally:
  state.p.close()