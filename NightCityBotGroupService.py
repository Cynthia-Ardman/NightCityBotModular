# group_rp.py
# Group RP channel creation and management

import discord
from discord.ext import commands
import re
from typing import Optional, List, Mapping, Union, cast


class GroupRPModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GROUP_AUDIT_LOG_CHANNEL_ID = 1366880900599517214
        self.FIXER_ROLE_ID = 1379437060389339156

    def build_channel_name(self, usernames, max_length=100):
        """
        Builds a Discord channel name for a group RP based on usernames and IDs.
        Falls back to usernames only if the full name exceeds Discord's 100 character limit.
        """
        full_name = "text-rp-" + "-".join(f"{name}-{uid}" for name, uid in usernames)
        if len(full_name) <= max_length:
            return re.sub(r"[^a-z0-9\-]", "", full_name.lower())

        # Fallback: usernames only
        simple_name = "text-rp-" + "-".join(name for name, _ in usernames)
        if len(simple_name) > max_length:
            simple_name = simple_name[:max_length]

        return re.sub(r"[^a-z0-9\-]", "", simple_name.lower())

    async def create_group_rp_channel(
            self,
            guild: discord.Guild,
            users: List[discord.Member],
            category: Optional[discord.CategoryChannel] = None
    ):
        """
        Creates a private RP channel for a group of users, allowing access to them,
        Fixers, Admins, and the bot.
        """
        usernames = [(user.name, user.id) for user in users]
        channel_name = self.build_channel_name(usernames)

        allowed_roles = {"Fixer", "Admin"}
        overwrites: Mapping[Union[discord.Role, discord.Member, discord.Object], discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        for user in users:
            overwrites[user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        for role in guild.roles:
            if role.name in allowed_roles:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        return await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category,
            reason="Creating private RP group channel"
        )

    async def end_rp_session(self, channel: discord.TextChannel):
        """
        Ends an RP session by creating a logging thread in the audit log forum channel,
        posting the entire message history into it, and deleting the RP channel.
        """
        log_channel = channel.guild.get_channel(self.GROUP_AUDIT_LOG_CHANNEL_ID)
        if not isinstance(log_channel, discord.ForumChannel):
            await channel.send("⚠️ Logging failed: audit log channel is not a ForumChannel.")
            return

        # Build thread name
        participants = channel.name.replace("text-rp-", "").split("-")
        thread_name = "GroupRP-" + "-".join(participants)

        # Create forum thread
        created = await log_channel.create_thread(
            name=thread_name,
            content=f"📘 RP log for `{channel.name}`"
        )

        # Unwrap and cast to Discord Thread
        log_thread = created.thread if hasattr(created, "thread") else created
        log_thread = cast(discord.Thread, log_thread)

        # Log all messages into thread
        async for msg in channel.history(limit=None, oldest_first=True):
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = msg.content or "*(No text content)*"
            entry = f"[{ts}] 📥 **Received from {msg.author.display_name}**:\n{content}"

            if msg.attachments:
                for attachment in msg.attachments:
                    entry += f"\n📎 Attachment: {attachment.url}"

            if len(entry) <= 2000:
                await log_thread.send(entry)
            else:
                chunks = [entry[i:i + 1990] for i in range(0, len(entry), 1990)]
                for chunk in chunks:
                    await log_thread.send(chunk)

        # Clean up channel
        await channel.delete(reason="RP session ended and logged.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def start_rp(self, ctx, *user_identifiers: str):
        """
        Starts a private RP channel for the mentioned users. Accepts @mentions or raw user IDs.
        """
        guild = ctx.guild
        users = []

        for identifier in user_identifiers:
            if identifier.isdigit():
                member = guild.get_member(int(identifier))
            else:
                match = re.findall(r"<@!?(\d+)>", identifier)
                member = guild.get_member(int(match[0])) if match else None
            if member:
                users.append(member)

        if not users:
            await ctx.send("❌ Could not resolve any users.")
            return

        channel = await self.create_group_rp_channel(guild, users)

        # Mention users and Fixers
        mentions = " ".join(user.mention for user in users)
        fixer_role = await ctx.guild.fetch_role(self.FIXER_ROLE_ID)
        fixer_mention = fixer_role.mention if fixer_role else ""

        await channel.send(f"✅ RP session created! {mentions} {fixer_mention}")
        await ctx.send(f"✅ RP channel created: {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def end_rp(self, ctx):
        """
        Ends the RP session in the current channel (if it's an RP channel).
        Archives, logs, and deletes the RP channel.
        """
        channel = ctx.channel
        if not channel.name.startswith("text-rp-"):
            await ctx.send("❌ This command can only be used in an RP session channel.")
            return

        await ctx.send("📝 Ending RP session, logging contents and deleting channel...")
        await self.end_rp_session(channel)


async def setup(bot):
    await bot.add_cog(GroupRPModule(bot))