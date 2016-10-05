import bottom
import threading
import time
import queue

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "sequence"
CHANNEL = "#system"




class State:
  pass

state = State()
state.sequence = [[]]
state.commands = dict()
state.running = False
state.message_queue = queue.Queue(100)
state.lock = threading.Lock()
state.should_abort = False


bot = bottom.Client(host=host, port=port, ssl=ssl)

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)
  
def show_help(target, message):
  for k,v in command_table.items():
    sysmsg( k + " : " + v[0] )

def show(target, message):
  if state.sequence == [[]]:
    sysmsg("No sequence is currently loaded.")
    return
  sysmsg("Currently loaded sequence has %d steps"%len(state.sequence))
  for i,step in enumerate(state.sequence):
    # show this step
    sysmsg(str(i+1) + " : " + str(step))

def new_step(target, message):
  state.sequence.append([])

def append_action(target, message):
  print(message)
  state.sequence[-1].append(message)

class StepRunner(threading.Thread):
  def __init__(self, seq):
    super().__init__()
    self.sequence = seq
    self.delay = 0.2
  def set_sequence(self, seq):
    self.sequence = seq
  def run(self):
    sysmsg("Starting sequence.")
    state.running = True
    for ix,step in enumerate(self.sequence):
      for action in step:
        if state.should_abort:
          state.running = False
          while not state.message_queue.empty():
            state.lock.acquire()
            state.message_queue.get()
            state.lock.release()
          sysmsg('Sequence Aborted.')
          return
        else:
          if action.startswith('wait') and len(action.split('for ')) == 1:
            elems = action.split()
            timeout = int(elems[1].replace('s',''))
            while (timeout >0 and not state.should_abort):
              time.sleep(0.2)
              timeout = timeout - 0.2
          elif action.startswith('wait '):
            try:
              elems = action.split()
              can_proceed = False
              timeout = int(elems[1].replace('s',''))
              desired_message = action.split('for ')[1]
              #sysmsg("Waiting %d seconds for '%s'"%(timeout, desired_message))
              while (timeout > 0 and not can_proceed and not state.should_abort):
                while not state.message_queue.empty():
                  state.lock.acquire()
                  m = state.message_queue.get()
                  state.lock.release()
                  if "ERROR" in m:
                    sysmsg("Refusing to proceed in the face of errors")
                    state.should_abort = True
                  if m == desired_message:
                    can_proceed = True
                    break
                time.sleep(0.2)
                timeout = timeout - 0.2
              if timeout <= 0:
                sysmsg("Timed out waiting for message '%s'"%desired_message)
                state.should_abort = True
            except:
              handle_err()
              sysmsg("Error processing wait command %s"%action)
              state.should_abort = True
          else:
            sysmsg(action)
          time.sleep(self.delay)
    state.running = False
    while not state.message_queue.empty():
      state.lock.acquire()
      state.message_queue.get()
      state.lock.release()
    sysmsg("Sequence complete.")


def clear(target, message):
  sysmsg("Clearing sequence")
  state.sequence = [[]]

def run(target, message):
  if state.sequence == [[]]:
    sysmsg("No sequence is currently loaded")
    return
  state.should_abort = False
  state.lock.acquire()
  while not state.message_queue.empty():
    state.message_queue.get()
  state.lock.release()
  runner = StepRunner(state.sequence)
  runner.start()

def abort(target, message):
  sysmsg("Aborting")
  state.should_abort = True

def demo(target, message):
  state.sequence = [
    [ 'say: Starting sequence in 5', 'wait 10s for OK' ],
    [ 'say: 4', 'wait 10s for OK' ],
    [ 'say: 3', 'wait 10s for OK' ],
    [ 'say: 2', 'wait 10s for OK' ],
    [ 'say: 1', 'wait 10s for OK' ],
    [ 'say: Sequence started'],
    [ 'bank: reset', 'wait 1s'],
    [ 'bank: set charge_power on', 'wait 1s', 'bank: set charge_enable on', 'wait 1s'],
    [ 'bank: charge 50', 'wait 60s for charge: OK, value = 0', 'bank: pulse', 'wait 10s for pulse : OK, value = 0'],
    [ 'bank: charge 60', 'wait 60s for charge: OK, value = 0', 'bank: pulse', 'wait 10s for pulse : OK, value = 0'],
    [ 'bank: charge 70', 'wait 60s for charge: OK, value = 0', 'bank: pulse', 'wait 10s for pulse : OK, value = 0'],
    [ 'bank: set charge_power off', 'bank: set charge_enable off'],
    [ 'say: Sequence complete']
  ]
  sysmsg("Example sequence loaded")

command_table = {
  'show': ('Show the currently loaded sequence', show),
  'help' : ('Show this helpful message',    show_help),
  'new_step': ('Start defining a new step for the sequence', new_step),
  'append' : ('Append an action to the current step', append_action),
  'start' : ('Start running the sequence', run),
  'clear' : ('Clear the current sequence', clear),
  'load_example' : ('Load a default sequence to illustrate usage', demo),
  'abort' : ('Emergency stop sequence', abort)
}

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
  print("Connected")
  bot.send('NICK', nick=NICK)
  bot.send('USER', user=NICK,
           realname='Sequence control robot')
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
  """ Echo all messages """
  # Don't echo ourselves
  if nick == NICK:
    return
  if message.startswith(NICK + ': '):
    stripped = message.split(NICK+': ')
    if len(stripped) > 1:
      command_bit = ''.join(stripped[1:]).strip().split()
      if command_bit[0].lower() in command_table.keys():
        command_table[command_bit[0].lower()][1](target,' '.join(command_bit[1:]))
  else:
    state.lock.acquire()
    state.message_queue.put(message)
    state.lock.release()

bot.loop.create_task(bot.connect())
bot.loop.run_forever()