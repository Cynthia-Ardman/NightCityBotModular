# NCRP Discord Bot - Refactored
# =====================================
import discord
from discord.ext import commands
import asyncio
import logging
import sys

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Imports
from NightCityBotold import NightCityBotDiceService
from NightCityBotold import NightCityBotAuditService
from NightCityBotold import NightCityBotDMService
from NightCityBotold import NightCityBotEconomyService
from NightCityBotold import NightCityBotGroupService
from NightCityBotold import NightCityBotKeepAlive
from NightCityBotold import NightCityBotMessagingService
from NightCityBotold import NightCityBotPermissions
from NightCityBotold import NightCityBotConfig

class NCRPBot(commands.Bot):
    """Main bot class with service container and cog loading."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.members = True
        intents.dm_messages = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Called once bot is ready to load cogs/services."""
        await NightCityBotMessagingService.setup(self)
        await NightCityBotPermissions.setup(self)
        await NightCityBotKeepAlive.setup(self)
        await NightCityBotGroupService.setup(self)
        await NightCityBotDiceService.setup(self)
        await NightCityBotEconomyService.setup(self)
        await NightCityBotDMService.setup(self)
        await NightCityBotConfig.setup(self)
        await NightCityBotAuditService.setup(self)
        logger.info("✅ All cogs loaded successfully.")

    async def on_ready(self):
        logger.info(f"🚀 Bot logged in as {self.user} ({self.user.id})")


# Entrypoint
if __name__ == "__main__":
    bot = NCRPBot()
    keep_alive(bot, bot.config.TOKEN)
