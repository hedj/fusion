import bottom
from macrosystem import *
import sys
import traceback
import asyncio
import time
import threading
import queue

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "robot"
CHANNEL = "#system"


abort_synonyms = [ 
  'ABORT', 'HALT', 'DIE', 'STOP', 'ERROR'
]

def handle_exception():
  print("Unexpected error:", sys.exc_info()[0:2])
  traceback.print_tb(sys.exc_info()[2])


class SequenceThread(threading.Thread):
  def __init__(self):
    super().__init__()
    self.lock = threading.Lock()
    self.queue = queue.Queue(3000)

  def clear_queue(self):
    self.lock.acquire()
    while not self.queue.empty():
      self.queue.get()
    self.lock.release()

  def consume(self,s):
    # bail out on error
    if s.strip().lower().startswith(NICK+': ' + 'help'):
      showhelp()
      return

    if ('ERROR' in s) or state.should_abort:
      sysmsg("Aborting due to ERROR message")
      abort()
      self.clear_queue()
      sleep(2)
      self.clear_queue()
      state.should_abort = False
      return

    # bail out on request from channel
    for syn in abort_synonyms:
      if syn in s:
        abort()
        self.clear_queue()
        return

    else:
      if state.waiting:
        if s.startswith(state.waiting_for):
          state.waiting = False
        elif s.startswith(NICK+ ': '):
          stripped = ''.join(s.split(NICK+': ')[1:]).strip()
          self.lock.acquire()
          self.queue.put(stripped)
          self.lock.release()
      elif s.startswith(NICK + ': '):
        # enqueue for running
        stripped = ''.join(s.split(NICK+': ')[1:]).strip()
        self.lock.acquire()
        self.queue.put(stripped)
        self.lock.release()
      else:  # not waiting and not for me directly
        state.backlog.append(s)

  def run(self):
    while True:
      if state.should_abort:
        self.clear_queue()
        state.should_abort = False
      else:
        if not self.queue.empty():
          cmd = self.queue.get()
          guarded_invoke(cmd,state.globals, state.locals)
        time.sleep(0.2)

bot = bottom.Client(host=host, port=port, ssl=ssl)
t = SequenceThread()
state.nick = NICK
t.start()
state.parent = t
state.backlog = []

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)

handlers['emit'] = sysmsg

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
  print("Connected")
  bot.send('NICK', nick=NICK)
  bot.send('USER', user=NICK,
           realname='universal control robot')
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
  if nick == NICK:
      return

  t.consume(message)


bot.loop.create_task(bot.connect())
bot.loop.run_forever()