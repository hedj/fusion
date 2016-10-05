import bottom
import win32com
import win32com.client


speaker = win32com.client.Dispatch('SAPI.SpVoice')


host = '192.168.137.3'
port = 6667
ssl = False

NICK = "talkbot"
CHANNEL = "#system"

bot = bottom.Client(host=host, port=port, ssl=ssl)
@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='iamthetalkingrobot')
    bot.send('JOIN', channel=CHANNEL)

@bot.on("client_disconnect")
async def reconnect(**kwargs):
  # Trigger an event that may cascade to a client_connect.
  # Don't continue until a client_connect occurs, which may be never.
  print("lost connection")  

@bot.on('PING')
def keepalive(message, **kwargs):
    print("Received ping")
    bot.send('PONG', message=message)

@bot.on('PRIVMSG')
def message(nick, target, message, **kwargs):
    """ Echo all messages """
    # Don't echo ourselves
    if nick == NICK:
        return
    stripped = message.split(NICK+':') 
    if len(stripped) > 1:
        speaker.Speak(''.join(stripped))

print("hi")
bot.loop.create_task(bot.connect())
bot.loop.run_forever()