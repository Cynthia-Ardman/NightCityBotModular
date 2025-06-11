# services/dm_service.py
# Direct message handling and thread management
import discord
import json
import logging
from typing import Dict, Union, cast
from pathlib import Path
from NightCityBot.NightCityBotConfig import BotConfig

logger = logging.getLogger(__name__)

async def setup(bot):
    await bot.add_cog(DMCog(bot))

class DMService:
    """Service for handling DM logging and thread management."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.dm_threads: Dict[str, int] = {}
        self.bot = None  # Will be set by the bot instance

    def set_bot(self, bot):
        """Set the bot instance for this service."""
        self.bot = bot

    async def load_thread_map(self):
        """Load the thread mapping from file."""
        thread_map_path = Path(self.config.THREAD_MAP_FILE)
        if thread_map_path.exists():
            try:
                with open(thread_map_path, "r") as f:
                    self.dm_threads = json.load(f)
                logger.info(f"Loaded {len(self.dm_threads)} DM thread mappings")
            except Exception as e:
                logger.error(f"Failed to load thread map: {e}")
                self.dm_threads = {}
        else:
            self.dm_threads = {}

    async def save_thread_map(self):
        """Save the thread mapping to file."""
        try:
            with open(self.config.THREAD_MAP_FILE, "w") as f:
                json.dump(self.dm_threads, f, indent=2)
            logger.debug("Saved DM thread mappings")
        except Exception as e:
            logger.error(f"Failed to save thread map: {e}")

    async def get_or_create_dm_thread(self, user: discord.User) -> Union[discord.Thread, discord.TextChannel]:
        """Get existing DM thread or create a new one."""
        if not self.bot:
            raise RuntimeError("Bot instance not set")

        log_channel = self.bot.get_channel(self.config.DM_INBOX_CHANNEL_ID)
        user_id = str(user.id)

        logger.debug(f"Getting/creating thread for {user.name} ({user_id})")

        # Try to reuse existing thread
        if user_id in self.dm_threads:
            try:
                thread = await self.bot.fetch_channel(self.dm_threads[user_id])
                logger.debug(f"Reusing existing thread {thread.id}")
                return cast(Union[discord.Thread, discord.TextChannel], thread)
            except discord.NotFound:
                logger.debug("Existing thread not found, creating new one")
                del self.dm_threads[user_id]

        # Create new thread
        thread_name = f"{user.name}-{user.id}".replace(" ", "-").lower()[:100]

        if isinstance(log_channel, discord.TextChannel):
            thread = await log_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason=f"DM logging for {user.name} ({user.id})"
            )

        elif isinstance(log_channel, discord.ForumChannel):
            try:
                created = await log_channel.create_thread(
                    name=thread_name,
                    content="📥 DM conversation started with this user.",
                    reason=f"DM logging for {user.name} ({user.id})"
                )
                thread = created.thread if hasattr(created, "thread") else created
            except Exception as e:
                logger.error(f"Failed to create forum thread: {e}")
                raise
        else:
            raise RuntimeError("DM inbox must be a TextChannel or ForumChannel")

        # Store thread mapping
        thread = cast(Union[discord.Thread, discord.TextChannel], thread)
        self.dm_threads[user_id] = thread.id
        await self.save_thread_map()

        logger.info(f"Created new DM thread {thread.name} ({thread.id})")
        return thread

    async def handle_dm_message(self, message: discord.Message):
        """Handle incoming DM message."""
        if not isinstance(message.channel, discord.DMChannel):
            return

        logger.info(f"DM received from {message.author}: {message.content[:100]}...")

        try:
            thread = await self.get_or_create_dm_thread(message.author)

            # Unarchive thread if needed
            if hasattr(thread, 'archived') and thread.archived:
                try:
                    await thread.edit(archived=False, locked=False)
                    logger.debug("Thread unarchived successfully")
                except Exception as e:
                    logger.error(f"Failed to unarchive thread: {e}")

            # Skip logging commands (they handle their own logging)
            if message.content and message.content.strip().startswith("!"):
                logger.debug(f"Skipped logging command: {message.content}")
                return

            # Log message content
            content = message.content or "*(No text content)*"
            await self._send_to_thread(
                thread,
                f"📥 **Received from {message.author.display_name}**:\n{content}"
            )

            # Log attachments
            for attachment in message.attachments:
                await self._send_to_thread(
                    thread,
                    f"📎 Received attachment: {attachment.url}"
                )

        except Exception as e:
            logger.error(f"DM logging failed for {message.author}: {e}")

    async def handle_thread_relay(self, message: discord.Message):
        """Handle message relay from thread to user."""
        if not isinstance(message.channel, discord.Thread):
            return

        # Check if this is a known DM thread
        for user_id, thread_id in self.dm_threads.items():
            if message.channel.id == thread_id:
                # Check if sender is a Fixer
                if not any(role.name == self.config.FIXER_ROLE_NAME for role in message.author.roles):
                    return

                try:
                    target_user = await self.bot.fetch_user(int(user_id))
                    if not target_user:
                        return

                    # Handle !roll commands specially
                    if message.content.strip().lower().startswith("!roll"):
                        await self._handle_roll_command(message, target_user)
                        return

                    # Relay normal message
                    files = [await a.to_file() for a in message.attachments]
                    await target_user.send(content=message.content or None, files=files)

                    # Log the relay
                    await self._send_to_thread(
                        message.channel,
                        f"📤 **Sent to {target_user.display_name} by {message.author.display_name}:**\n{message.content}"
                    )

                    # Delete original message
                    try:
                        await message.delete()
                    except Exception as e:
                        logger.warning(f"Couldn't delete relayed message: {e}")

                except Exception as e:
                    logger.error(f"Failed to relay message: {e}")

                break

    async def _handle_roll_command(self, message: discord.Message, target_user: discord.User):
        """Handle !roll command in thread relay."""
        dice = message.content.strip()[len("!roll"):].strip()

        # Create a mock context for the roll command
        ctx = await self.bot.get_context(message)
        setattr(ctx, "original_author", message.author)
        ctx.author = target_user
        ctx.channel = await target_user.create_dm()

        # Execute the roll command
        roll_command = self.bot.get_command("roll")
        if roll_command:
            await roll_command(ctx, dice=dice)

        # Delete the original message
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete relayed !roll message: {e}")

    async def _send_to_thread(self, thread: Union[discord.Thread, discord.TextChannel], content: str):
        """Send content to thread, splitting if too long."""
        if len(content) <= 2000:
            await thread.send(content)
        else:
            # Split into chunks
            chunks = [content[i:i + 1990] for i in range(0, len(content), 1990)]
            for chunk in chunks:
                await thread.send(chunk)

    async def log_outgoing_dm(self, user: discord.User, content: str, sender_name: str):
        """Log an outgoing DM to the user's thread."""
        try:
            thread = await self.get_or_create_dm_thread(user)
            await self._send_to_thread(
                thread,
                f"📤 **Sent to {user.display_name} by {sender_name}:**\n{content}"
            )
        except Exception as e:
            logger.error(f"Failed to log outgoing DM: {e}")