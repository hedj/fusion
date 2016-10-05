import bottom
import ipfsApi
import time
import sys
import traceback
import asyncio

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "ipfs"
CHANNEL = "#system"

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])


connected = False

class State:
  pass

state = State()

print("Connecting to IPFS")
while(not connected):
  try:
    state.ipfs_client = ipfsApi.Client('127.0.0.1', 5001)
    connected = True
  except:
    handle_exception()
    print("Waiting for IPFS daemon")
    time.sleep(5)

print("Creating IRC client")
bot = bottom.Client(host=host, port=port, ssl=ssl)

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)

def usage(message):
  sysmsg("%s understands the following commands:"%NICK)
  for k,v in commands.items():
    sysmsg('  ' + k + ' : ' + v[0])

def publish(path):
  try:
    res = state.ipfs_client.add(path, recursive=True)
    print(res)
    if isinstance(res, list):
      h = res[-1]["Hash"]
    else:
      h = res["Hash"]
    sysmsg("Published to IPFS with hash %s  ( https://gateway.ipfs.io/ipfs/%s )"%(h,h))
  except:
    handle_exception()
    sysmsg("Could not publish that file - are you sure the path is correct?")

commands = {
    'publish' :      ( 'publish <PATH> publishes the given file or directory to IPFS', publish),
    'help' : ( 'shows this useful message', usage),
}

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='stepper control IRC bot')
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

print("Starting ipfs bot")
bot.loop.create_task(bot.connect())
bot.loop.run_forever()