# NightCityBotPermissions.py

import discord
from discord.ext import commands
from NightCityBotold.NightCityBotConfig import FIXER_ROLE_NAME

async def setup(bot):
    await bot.add_cog(PermissionsCog(bot))

def is_fixer():
    async def predicate(ctx):
        if isinstance(ctx.author, discord.Member):
            return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None
        return False
    return commands.check(predicate)
