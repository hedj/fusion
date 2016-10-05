import bottom
import win32com
import win32com.client

speaker = win32com.client.Dispatch('SAPI.SpVoice')

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "say"
CHANNEL = "#system"

bot = bottom.Client(host=host, port=port, ssl=ssl)

def sysmsg(s):
  bot.send("PRIVMSG", target=CHANNEL, message=s)

@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='iamthetalkingrobot')
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
    if message.startswith(NICK + ": "):
        stripped = message.split(NICK+': ')
        if len(stripped) > 1:
            speaker.Speak(''.join(stripped))
            sysmsg("OK")

bot.loop.create_task(bot.connect())
bot.loop.run_forever()