import bottom
import system_control

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "stepper"
CHANNEL = "#system"

def helpmsg():
    return [
"%s accepts simple movement commands."%NICK,
"'%s: forward 5' will move the stepper forward 5mm."%NICK,
"'%s: backward 10' would move the stepper forward 10mm. "%NICK]


s = system_control.StepperControl()  

bot = bottom.Client(host=host, port=port, ssl=ssl)
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
    stripped = message.split(NICK+': ')
    if len(stripped) > 1:
        cmd = ''.join(stripped)
        if (cmd.strip().lower() == 'help'):
            for line in helpmsg():
              bot.send("PRIVMSG", target=target, message=line)
        elif cmd.startswith('forward'):
          try:
            d = int(cmd.split(' ')[1])
            if not s.is_connected():
              bot.send("PRIVMSG", target=target, message="ERROR: not connected to the stepper controller")
            else:
              s.forward(d)
          except:
            bot.send("PRIVMSG",target=target, message="Sorry, couldn't parse that! ('help' for supported commands)")
        elif cmd.startswith('backward'):
          try:
            d = int(cmd.split(' ')[1])
            if not s.is_connected():
              bot.send("PRIVMSG", target=target, message="ERROR: not connected to the stepper controller")
            else:
              s.backwards(d)
          except:
            bot.send("PRIVMSG",target=target, message="Sorry, couldn't parse that! ('help' for supported commands)")

bot.loop.create_task(bot.connect())
bot.loop.run_forever()