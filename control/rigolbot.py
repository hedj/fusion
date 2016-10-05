import bottom
import ipfsApi
import time
import sys
import traceback
import asyncio
import system_control
import csv
import os

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "rigol"
CHANNEL = "#system"

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])

class State:
  pass

state = State()

state.names = dict()
state.ips = dict()
state.channel_names = dict()
state.scopes = set()

def on_rigol_connect(ip):
  sysmsg("Connected to rigol scope at ip %s"%(ip))
  state.scopes.add(ip)

def on_error(s):
  sysmsg('ERROR ' + s)

state.r = system_control.RigolControl()
state.r.onConnect(on_rigol_connect)
state.r.onError(on_error)
state.r.start()

bot = bottom.Client(host=host, port=port, ssl=ssl)

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)

def usage(message):
  sysmsg("%s understands the following commands:"%NICK)
  for k,v in commands.items():
    sysmsg('  ' + k + ' : ' + v[0])

def write_data(message):
  # write data
  if len(state.scopes) == 0:
    sysmsg("No scopes connected")
    return
  data = state.r.scope_screen_contents()
  outdir = message.strip()
  sysmsg("Writing rigol data to output directory %s"%outdir)
  if not os.path.exists(outdir):
    os.makedirs(outdir)
  for scope in data.keys():
    outfile = os.path.join(outdir, "%s.csv"%state.names[scope])
    print("Writing %s"%outfile)
    this_scope_data = data[scope]
    with open(outfile,"w",newline='') as csvfile:
      labels = []
      labels.append("time")
      for n in state.channel_names[state.names[scope]]:
        labels.append(n)
      csvfile.write("%s\r\n"%(','.join(labels)))
      writer =  csv.writer(csvfile)
      # get length of time series
      length = len(data[scope]['Channel_1'][0])
      for i in range(length):
        line = []
        line.append(data[scope]['Channel_1'][1][i])
        for channel in sorted(this_scope_data.keys()):
          thisline = data[scope][channel][0][i]
          line.append(thisline)
        writer.writerow(line)
  sysmsg("Data written")

def add_device(message):
  elems = message.strip().split(' ')
  state.names[elems[0]] = elems[1]
  state.ips[elems[1]] = elems[0]
  state.channel_names[elems[0]] = [ 'Channel_1', 'Channel_2', 'Channel_3', 'Channel_4' ]
  state.r.thread.add_device(elems[0])

def remove_device(message):
  if not elems[0] in state.ips:
    sysmsg("No such device")
    return
  del state.names[ state.ips[elems[0]] ]
  del state.ips[ elems[0] ]
  del state.channel_names[ elems[0] ]
  state.r.thread.remove_device(elems[0])

def name_channels(message):
  elems = message.strip().split(' ')
  if not elems[0] in state.ips.keys():
    sysmsg("No scope called '%s'"%elems[0])
    return
  else:
    state.channel_names[elems[0]] = elems[1:]
    sysmsg("Channel names set")

def status(message):
  if len(state.scopes) == 0:
    sysmsg("No connected rigol scopes")
    return

  sysmsg("Connected scopes: ")
  for ip in state.scopes:
    sysmsg("  %s  @  %s : "%(state.names[ip], ip))
    for ix,n in enumerate(state.channel_names[state.names[ip]]):
      sysmsg("    Channel %d is labelled '%s'"%(ix+1,n))

commands = {
    'channel_names' :   ( 'channel_names <DEVICE_NAME> <NAME_1> <NAME_2> ...    names the channels of the chosen scope', name_channels),
    'add_device' :      ( 'add_device <IP> <NAME>  adds the device at IP and names it NAME  (e.g add_device 192.168.137.10 pulse_scope)', add_device),
    'remove_device' :   ( 'remove_device <NAME> removes the named device', remove_device),
    'status'     :      ( 'shows information about connected Rigol scopes', status),
    'write_data' :      ( 'write_data <PATH> writes the current screen contents of each rigol scope to <PATH>', write_data),
    'help' : ( 'shows this useful message', usage),
}

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='rigol ds1054z control bot')
    bot.send('JOIN', channel=CHANNEL)

@bot.on("client_disconnect")
async def reconnect(**kwargs):
    await asyncio.sleep(3, loop=bot.loop)
    bot.loop.create_task(bot.connect())

@bot.on('PING')
def keepalive(message, **kwargs):
    bot.send('PONG', message=message)

@bot.on('PRIVMSG')
def message(nick, target, message, **kwargs):
    # Don't echo ourselves
    if nick == NICK:
        return
    # Only respond to commands that are to us.
    if not message.startswith(NICK + ': '):
      return

    stripped = ''.join(message.split(NICK+': ')[1:]).strip()

    elems = stripped.split()
    if elems[0] in commands.keys():
      commands[elems[0]][1]( ' '.join(elems[1:]))
    else:
      sysmsg("ERROR: Command not understood")

print("Starting rigol control bot")
bot.loop.create_task(bot.connect())
bot.loop.run_forever()