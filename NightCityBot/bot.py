import discord
from discord.ext import commands
import config
from utils.permissions import is_fixer
from cogs.dm_handling import DMHandler
from cogs.economy import Economy
from cogs.rp_manager import RPManager
from cogs.roll_system import RollSystem
from cogs.admin import Admin
from cogs.test_suite import TestSuite
from flask import Flask
from threading import Thread


class NightCityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.members = True
        intents.dm_messages = True

        super().__init__(
            command_prefix="!",
            help_command=None,
            intents=intents
        )

    async def setup_hook(self):
        # Load all cogs
        await self.add_cog(DMHandler(self))
        await self.add_cog(Economy(self))
        await self.add_cog(RPManager(self))
        await self.add_cog(RollSystem(self))
        await self.add_cog(Admin(self))
        await self.add_cog(TestSuite(self))

    async def on_ready(self):
        print(f"✅ {self.user.name} is running!")


app = Flask('')


@app.route('/')
def home():
    return "Bot is alive Version 1.2!"


def run_flask():
    app.run(host='0.0.0.0', port=5000)


def keep_alive():
    t = Thread(target=run_flask)
    t.start()


def main():
    bot = NightCityBot()
    keep_alive()
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()