import bottom

host = '192.168.137.3'
port = 6667
ssl = False

NICK = "bottombot"
CHANNEL = "#system"

bot = bottom.Client(host=host, port=port, ssl=ssl)
@bot.on('CLIENT_CONNECT')
def connect(**kwargs):
    print("Connected")
    bot.send('NICK', nick=NICK)
    bot.send('USER', user=NICK,
             realname='https://github.com/numberoverzero/bottom')
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
    # Respond directly to direct messages
    if target == NICK:
        bot.send("PRIVMSG", target=nick, message=message)
    # Channel message
    else:
        bot.send("PRIVMSG", target=target, message=message)

print("hi")
bot.loop.create_task(bot.connect())
bot.loop.run_forever()