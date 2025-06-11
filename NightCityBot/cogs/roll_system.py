import discord
from discord.ext import commands
import random
import re
from typing import Optional
from utils.permissions import is_fixer
from cogs.dm_handling import DMHandler

class RollSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def roll(self, ctx, *, dice: str):
        original_sender = getattr(ctx, "original_author", None)

        # Extract user mention if present
        match = re.search(r"(?:<@!?)?([0-9]{15,20})>?", dice)
        mentioned_user = None
        if match:
            user_id = int(match.group(1))
            mentioned_user = ctx.guild.get_member(user_id)
            if mentioned_user:
                dice = re.sub(r"(?:<@!?)?[0-9]{17,20}(?:>)?", "", dice).strip()

        roller = mentioned_user or ctx.author

        if original_sender:
            try:
                await ctx.message.delete()
            except Exception as e:
                print(f"[WARN] Couldn't delete relayed !roll command: {e}")
            await self.loggable_roll(roller, ctx.channel, dice, original_sender=original_sender)
        else:
            await self.loggable_roll(roller, ctx.channel, dice)

    async def loggable_roll(self, author, channel, dice: str, *, original_sender=None):
        pattern = r'(?:(\d*)d)?(\d+)([+-]\d+)?'
        m = re.fullmatch(pattern, dice.replace(' ', ''))
        if not m:
            await channel.send('🎲 Format: `!roll XdY+Z` (e.g. `!roll 2d6+3`)')
            return

        n_dice, sides, mod = m.groups()
        n_dice = int(n_dice) if n_dice else 1
        sides = int(sides)
        mod = int(mod) if mod else 0

        role_names = [getattr(r, "name", "") for r in getattr(author, "roles", [])]
        bonus = 2 if "Netrunner Level 3" in role_names else 1 if "Netrunner Level 2" in role_names else 0

        rolls = [random.randint(1, sides) for _ in range(n_dice)]
        total = sum(rolls) + mod + bonus

        name = author.display_name
        header = f'🎲 {name} rolled: {n_dice}d{sides}{f"+{mod}" if mod else ""}\n'
        body = f'**Results:** {", ".join(map(str, rolls))}\n**Total:** {total}'
        if bonus:
            body += f' (includes +{bonus} Netrunner bonus)'
        result = header + body

        await channel.send(result)

        # Log to DM thread if actual DM, or if relayed with original_sender
        if isinstance(channel, discord.DMChannel):
            thread = await self.bot.get_cog('DMHandler').get_or_create_dm_thread(author)
            if isinstance(thread, discord.abc.Messageable):
                await thread.send(
                    f"📥 **{author.display_name} used:** `!roll {dice}`\n\n{result}"
                )
        elif original_sender and isinstance(channel, discord.DMChannel):
            thread = await self.bot.get_cog('DMHandler').get_or_create_dm_thread(author)
            if isinstance(thread, discord.abc.Messageable):
                await thread.send(
                    f"📤 **{original_sender.display_name} rolled as {author.display_name}** → `!roll {dice}`\n\n{result}"
                )