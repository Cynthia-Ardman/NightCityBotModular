# cogs/messaging_cog.py
# Messaging commands and DM handling
import discord
from discord.ext import commands
import logging
from NightCityBot.NightCityBotPermissions import is_fixer

logger = logging.getLogger(__name__)

async def setup(bot):
    await bot.add_cog(MessagingCog(bot))


class MessagingCog(commands.Cog):
    """Cog for handling messaging commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        # Set bot reference in services
        bot.dm_service.set_bot(bot)

    @commands.command()
    @is_fixer()
    async def post(self, ctx, destination: str, *, message=None):
        """
        Post a message to the specified channel or thread.
        If message starts with !, execute it as a command.
        """
        dest_channel = await self._resolve_destination(ctx, destination)
        if not dest_channel:
            await ctx.send(f"❌ Couldn't find channel/thread '{destination}'.")
            return

        files = [await attachment.to_file() for attachment in ctx.message.attachments]

        if not message and not files:
            await ctx.send("❌ Provide a message or attachment.")
            return

        try:
            if message and message.strip().startswith("!"):
                # Execute command in target channel
                await self._execute_command_in_channel(ctx, dest_channel, message.strip())
                await ctx.send(f"✅ Executed `{message.strip()}` in {dest_channel.mention}.")
            else:
                # Send regular message
                await dest_channel.send(content=message, files=files)
                await ctx.send(f"✅ Posted anonymously to {dest_channel.mention}.")

                # Log the action
                await self.bot.audit_service.log_audit(
                    ctx.author,
                    f"Posted message to {dest_channel.name}: {message[:50]}..."
                )

        except Exception as e:
            logger.error(f"Failed to post message: {e}")
            await ctx.send("❌ Failed to post message.")

    @commands.command()
    @is_fixer()
    async def dm(self, ctx, user: discord.User, *, message=None):
        """Send a DM to a user."""
        if not user:
            await ctx.send("❌ Could not resolve user.")
            await self.bot.audit_service.log_audit(
                ctx.author,
                "❌ Failed DM: Could not resolve user"
            )
            return

        # Handle !roll commands specially
        if message and message.strip().lower().startswith("!roll"):
            dice = message.strip()[len("!roll"):].strip()
            await self._send_roll_dm(ctx, user, dice)
            return

        # Prepare DM content
        dm_content_parts = []
        if message:
            dm_content_parts.append(message)

        if ctx.message.attachments:
            file_links = [attachment.url for attachment in ctx.message.attachments]
            dm_content_parts.append(f"📎 **Attachments:**\n" + "\n".join(file_links))

        if not dm_content_parts:
            await ctx.send("❌ Provide a message or attachment.")
            return

        dm_content = "\n\n".join(dm_content_parts)

        try:
            # Send the DM
            await user.send(content=dm_content)
            await ctx.send(f'✅ DM sent anonymously to {user.display_name