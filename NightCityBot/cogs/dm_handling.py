import discord
from discord.ext import commands
from discord.abc import Messageable
from typing import Union, Dict
import json
import config
from utils.permissions import is_fixer
from utils.helpers import load_json_file, save_json_file


class DMHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dm_threads: Dict[str, int] = {}
        self.bot.loop.create_task(self.load_thread_cache())

    async def load_thread_cache(self):
        """Load the thread mapping cache on startup."""
        self.dm_threads = await load_json_file(config.THREAD_MAP_FILE, default={})

    async def get_or_create_dm_thread(
            self,
            user: discord.abc.User
    ) -> Union[discord.Thread, discord.TextChannel]:
        """Return the logging thread for a DM sender, creating it if necessary."""
        log_channel = self.bot.get_channel(config.DM_INBOX_CHANNEL_ID)
        user_id = str(user.id)

        if user_id in self.dm_threads:
            try:
                thread = await self.bot.fetch_channel(self.dm_threads[user_id])
                return thread
            except discord.NotFound:
                pass  # Thread was deleted, create new one

        thread_name = f"{user.name}-{user.id}".replace(" ", "-").lower()[:100]

        if isinstance(log_channel, discord.TextChannel):
            thread = await log_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason=f"Logging DM history for {user}"
            )
        elif isinstance(log_channel, discord.ForumChannel):
            created = await log_channel.create_thread(
                name=thread_name,
                content=f"📥 DM started with {user}.",
                reason=f"Logging DM history for {user}"
            )
            thread = created.thread if hasattr(created, "thread") else created
        else:
            raise RuntimeError("DM inbox must be a TextChannel or ForumChannel")

        self.dm_threads[user_id] = thread.id
        await save_json_file(config.THREAD_MAP_FILE, self.dm_threads)

        return thread

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.author.bot:
            return

        # Handle relay from Fixer DM-forum threads
        if isinstance(message.channel, discord.Thread):
            await self.handle_thread_message(message)

        # Handle incoming user DMs
        elif isinstance(message.channel, discord.DMChannel):
            await self.handle_dm_message(message)

    async def handle_thread_message(self, message: discord.Message):
        """Handle messages sent in DM logging threads."""
        for uid, thread_id in self.dm_threads.items():
            if message.channel.id != thread_id:
                continue

            roles = getattr(message.author, "roles", [])
            if not any(getattr(r, "name", "") == config.FIXER_ROLE_NAME for r in roles):
                return

            target_user = await self.bot.fetch_user(int(uid))
            if not target_user:
                return

            # Handle roll command relay
            if message.content.strip().lower().startswith("!roll"):
                roll_cog = self.bot.get_cog('RollSystem')
                if roll_cog:
                    dice = message.content.strip()[len("!roll"):].strip()
                    ctx = await self.bot.get_context(message)
                    setattr(ctx, "original_author", message.author)
                    ctx.author = target_user
                    ctx.channel = await target_user.create_dm()
                    await roll_cog.roll(ctx, dice=dice)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            # Handle normal message relay
            files = [await a.to_file() for a in message.attachments]
            await target_user.send(content=message.content or None, files=files)
            await message.channel.send(
                f"📤 **Sent to {target_user.display_name} "
                f"by {message.author.display_name}:**\n{message.content}"
            )
            try:
                await message.delete()
            except Exception:
                pass

    async def handle_dm_message(self, message: discord.Message):
        """Handle incoming DMs from users."""
        try:
            thread = await self.get_or_create_dm_thread(message.author)
            msg_target: Messageable = thread

            full = message.content or "*(No text content)*"
            for chunk in (full[i:i + 1024] for i in range(0, len(full), 1024)):
                if chunk.strip().startswith("!"):
                    continue
                await msg_target.send(
                    f"📥 **Received from {message.author.display_name}**:\n{chunk}"
                )

            for att in message.attachments:
                await msg_target.send(f"📎 Received attachment: {att.url}")
        except Exception as e:
            print(f"[ERROR] DM logging failed: {e}")

    @commands.command()
    @is_fixer()
    async def dm(self, ctx, user: discord.User, *, message=None):
        """Send an anonymous DM to a user."""
        try:
            if not user:
                raise ValueError("User fetch returned None.")
        except discord.NotFound:
            await ctx.send("❌ Could not resolve user.")
            return
        except Exception as e:
            await ctx.send(f"⚠️ Unexpected error: {str(e)}")
            return

        file_links = [attachment.url for attachment in ctx.message.attachments]

        # Handle roll command relay
        if message and message.strip().lower().startswith("!roll"):
            roll_cog = self.bot.get_cog('RollSystem')
            if roll_cog:
                dice = message.strip()[len("!roll"):].strip()
                member = ctx.guild.get_member(user.id) or user
                fake_ctx = await self.bot.get_context(ctx.message)
                fake_ctx.author = member
                fake_ctx.channel = await user.create_dm()
                setattr(fake_ctx, "original_author", ctx.author)
                await roll_cog.roll(fake_ctx, dice=dice)
                await ctx.send(f"✅ Rolled `{dice}` anonymously for {user.display_name}.")
                return

        # Handle normal DM
        dm_content_parts = [message] if message else []
        if file_links:
            links_formatted = "\n".join(file_links)
            dm_content_parts.append(f"📎 **Attachments:**\n{links_formatted}")
        dm_content = "\n\n".join(dm_content_parts) if dm_content_parts else "(No text)"

        try:
            await user.send(content=dm_content)
            await ctx.send(f'✅ DM sent anonymously to {user.display_name}.')

            thread = await self.get_or_create_dm_thread(user)
            if isinstance(thread, (discord.Thread, discord.TextChannel)):
                await thread.send(
                    f"📤 **Sent to {user.display_name} by {ctx.author.display_name}:**\n{dm_content}"
                )
            else:
                print(f"[ERROR] Cannot log DM — thread type is {type(thread)}")

        except discord.Forbidden:
            await ctx.send('❌ Cannot DM user (Privacy Settings).')