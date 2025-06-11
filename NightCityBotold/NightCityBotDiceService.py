# dice.py
# Dice rolling functionality with netrunner bonuses and logging

import discord
from discord.ext import commands
import random
import re
from typing import cast

async def setup(bot):
    await bot.add_cog(DiceCog(bot))

class DiceModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DM_INBOX_CHANNEL_ID = 1366880900599517214

    async def get_or_create_dm_thread(self, user: discord.User):
        """Get or create a DM thread for logging purposes"""
        from threading_utils import get_or_create_dm_thread  # Import from your existing module
        return await get_or_create_dm_thread(user)

    async def loggable_roll(self, author, channel, dice: str, *, original_sender=None):
        """
        Process dice rolls with netrunner bonuses and proper logging
        """
        dice_pattern = r'(?:(\d*)d)?(\d+)([+-]\d+)?'
        match = re.fullmatch(dice_pattern, dice.replace(' ', ''))

        if not match:
            if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
                await channel.send('🎲 Format: `!roll XdY+Z` (Example: `!roll 2d6+3`)')
            return

        dice_count, dice_sides, modifier = match.groups()
        dice_count = int(dice_count) if dice_count else 1
        dice_sides = int(dice_sides)
        modifier = int(modifier) if modifier else 0

        # Calculate netrunner bonus
        user_roles = [role.name for role in getattr(author, "roles", [])]
        bonus = 0
        if "Netrunner Level 2" in user_roles:
            bonus = 1
        elif "Netrunner Level 3" in user_roles:
            bonus = 2

        # Roll dice
        rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
        total = sum(rolls) + modifier + bonus

        # Format results
        rolls_detailed = ', '.join(f'**{roll}**' for roll in rolls)
        modifier_text = f" {'+' if modifier >= 0 else '-'} {abs(modifier)}" if modifier else ""

        if bonus:
            result_message = (
                f'🎲 You rolled: {dice_count}d{dice_sides}{modifier_text}\n'
                f'**Results:** {rolls_detailed}\n'
                f'**Total:** {total} (includes +{bonus} Netrunner bonus)'
            )
        else:
            result_message = (
                f'🎲 You rolled: {dice_count}d{dice_sides}{modifier_text}\n'
                f'**Results:** {rolls_detailed}\n'
                f'**Total:** {total}'
            )

        # Determine logging behavior
        in_dm_log_thread = (
            isinstance(channel, discord.Thread)
            and channel.parent
            and channel.parent.id == self.DM_INBOX_CHANNEL_ID
        )

        should_log_to_dm = False
        if original_sender:
            should_log_to_dm = True
        elif isinstance(channel, discord.DMChannel):
            should_log_to_dm = True
        elif in_dm_log_thread:
            should_log_to_dm = False  # already logging in correct place

        # Send result to recipient
        if original_sender:
            dm = await author.create_dm()
            await dm.send(result_message)

        # Log result appropriately
        if should_log_to_dm:
            thread = await self.get_or_create_dm_thread(author)
            if original_sender:
                await thread.send(
                    f"📤 **Sent to {author.display_name} by {original_sender.display_name}:** `!roll {dice}`\n\n{result_message}"
                )
            else:
                await thread.send(
                    f"📥 **{author.display_name} used:** `!roll {dice}`\n\n{result_message}"
                )
        else:
            if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
                await channel.send(result_message)
            else:
                print(f"[WARN] loggable_roll tried to send to unsupported channel type: {type(channel)}")

    @commands.command()
    async def roll(self, ctx, *, dice: str):
        """
        Roll dice with optional netrunner bonuses
        Format: !roll XdY+Z (e.g., !roll 2d6+3)
        """
        original_sender = getattr(ctx, "original_author", None)

        # If this command was relayed into a thread (Fixer sending on behalf of bot)
        if original_sender:
            try:
                await ctx.message.delete()
            except Exception as e:
                print(f"[WARN] Couldn't delete relayed !roll command: {e}")
            await self.loggable_roll(ctx.author, await ctx.author.create_dm(), dice, original_sender=original_sender)
        else:
            await self.loggable_roll(ctx.author, ctx.channel, dice)


async def setup(bot):
    await bot.add_cog(DiceModule(bot))