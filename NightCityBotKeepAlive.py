# NightCityBotKeepAlive.py

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

async def setup(bot):
    await bot.add_cog(KeepAliveCog(bot))

def run():
    app.run(host='0.0.0.0', port=5000)

def keep_alive(bot, token):
    t = Thread(target=run)
    t.start()
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")
