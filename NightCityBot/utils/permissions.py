from discord.ext import commands
import config


def is_fixer():
    async def predicate(ctx):
        # in-guild messages
        if isinstance(ctx.author, discord.Member):
            return discord.utils.get(ctx.author.roles, name=config.FIXER_ROLE_NAME) is not None

        # DMs or thread-posts: fetch member object from main guild
        guild = ctx.bot.get_guild(config.GUILD_ID)
        if not guild:
            return False

        member = guild.get_member(ctx.author.id)
        if not member:
            try:
                member = await guild.fetch_member(ctx.author.id)
            except discord.NotFound:
                return False

        return discord.utils.get(member.roles, name=config.FIXER_ROLE_NAME) is not None

    return commands.check(predicate)