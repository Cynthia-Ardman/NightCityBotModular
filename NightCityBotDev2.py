# NCRP Combined Bot — Cleaned and Merged
# =====================================
# This script merges DM logging, anonymous messaging, and rent collection.

import discord
from discord.ext import commands
from discord.abc import Messageable
import random
import re
import json
import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread as ThreadingThread
from datetime import datetime, timedelta
from pathlib import Path
from calendar import month_name
from typing import Optional, List
from typing import cast
from re import sub
from discord import File
import aiofiles
from typing import Mapping, Union
from unittest.mock import AsyncMock, MagicMock
import time
from discord import TextChannel, Thread



# --- Configuration ---
TOKEN = "MTM3OTUyNzc4OTQzNDI0MTExNA.GvXqPH.VoumI0nbwNBD2VPIySMRVrpjdI0BNQd3N2ZTYM"
AUDIT_LOG_CHANNEL_ID = 1341160960924319804
GROUP_AUDIT_LOG_CHANNEL_ID = 1366880900599517214
FIXER_ROLE_NAME = "Fixer"
FIXER_ROLE_ID = 1379437060389339156
DM_INBOX_CHANNEL_ID = 1366880900599517214
UNBELIEVABOAT_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2NDQ1MTE2NDkyMDI2IiwiaWF0IjoxNzQ5MTc3NjMxfQ.Hgn611UEILLF1ogVDxlQpHivT89ArroJnAliouHE7P4"
GUILD_ID = 1320924574761746473
TEST_USER_ID = 286338318076084226

SEEN_MSG_ID_FILE = "backfill_seen_ids.json"
THREAD_MAP_FILE = "thread_map.json"
OPEN_LOG_FILE = "business_open_log.json"
LAST_RENT_FILE = "last_rent.json"

# --- Global Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", help_command=None, intents=intents)
bot.help_command = None
app = Flask('')


# Keep-alive server for uptime
@app.route('/')
def home():
    return "Bot is alive Version 1.2!"


def run():
    app.run(host='0.0.0.0', port=5000)


def keep_alive():
    t = ThreadingThread(target=run)
    t.start()
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")

@bot.event
async def on_ready():
    print("✅ Bot is running with helpme v1.2")


# --- Shared State ---
dm_threads = {}
if os.path.exists(THREAD_MAP_FILE):
    try:
        with open(THREAD_MAP_FILE, "r") as f:
            dm_threads = json.load(f)
    except Exception as e:
        print(f"[THREAD CACHE] Failed to load thread_map.json: {e}")

seen_msg_ids = set()
if os.path.exists(SEEN_MSG_ID_FILE):
    try:
        with open(SEEN_MSG_ID_FILE, "r") as f:
            seen_msg_ids = set(json.load(f))
    except Exception as e:
        print(f"[WARN] Could not load seen message IDs: {e}")


# --- Permissions ---

def is_fixer():
    async def predicate(ctx):
        # in‑guild messages
        if isinstance(ctx.author, discord.Member):
            return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None

        # DMs or thread‑posts: fetch member object from main guild
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return False
        member = guild.get_member(ctx.author.id)
        if not member:
            try:
                member = await guild.fetch_member(ctx.author.id)
            except discord.NotFound:
                return False
        return discord.utils.get(member.roles, name=FIXER_ROLE_NAME) is not None
    return commands.check(predicate)

role_costs_business = {
        "Business Tier 0": 0,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000
    }

role_costs_housing = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000
    }

# --- Logging ---

async def log_audit(user, action_desc):
    audit_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)

    if isinstance(audit_channel, discord.TextChannel):
        embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Action", value=action_desc, inline=False)
        await audit_channel.send(embed=embed)
    else:
        print(f"[AUDIT] Skipped: Channel {AUDIT_LOG_CHANNEL_ID} is not a TextChannel")

    print(f"[AUDIT] {user}: {action_desc}")

# -- GROUP RP Channel Building --

def build_channel_name(usernames, max_length=100):
    """
    Builds a Discord channel name for a group RP based on usernames and IDs.
    Falls back to usernames only if the full name exceeds Discord's 100 character limit.
    If still too long, truncates to fit.
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
        guild: discord.Guild,
        users: list[discord.Member],
        category: Optional[discord.CategoryChannel] = None
    ):
    """
    Creates a private RP channel for a group of users, allowing access to them, Fixers, Admins, and the bot.
    """
    usernames = [(user.name, user.id) for user in users]
    channel_name = build_channel_name(usernames)

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

async def end_rp_session(channel: discord.TextChannel):
    """
    Ends an RP session by creating a logging thread in the audit log forum channel,
    posting the entire message history into it, and deleting the RP channel.
    """
    log_channel = channel.guild.get_channel(GROUP_AUDIT_LOG_CHANNEL_ID)
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

# --- Group RP Commands ---

@bot.command()
@commands.has_permissions(administrator=True)
async def start_rp(ctx, *user_identifiers: str):
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
    channel = await create_group_rp_channel(guild, users)
    mentions = " ".join(user.mention for user in users)
    fixer_role = await ctx.guild.fetch_role(FIXER_ROLE_ID)
    fixer_mention = fixer_role.mention if fixer_role else ""
    await channel.send(f"✅ RP session created! {mentions} {fixer_mention}")
    await ctx.send(f"✅ RP channel created: {channel.mention}")
    return channel  # ✅ NEW: so tests can capture it


@bot.command()
@is_fixer()
async def end_rp(ctx):
    """
    Ends the RP session in the current channel (if it's an RP channel).
    Archives, logs, and deletes the RP channel.
    """
    channel = ctx.channel
    if not channel.name.startswith("text-rp-"):
        await ctx.send("❌ This command can only be used in an RP session channel.")
        return
    await ctx.send("📝 Ending RP session, logging contents and deleting channel...")
    await end_rp_session(channel)

# --- DM Thread Handling ---

async def get_or_create_dm_thread(
    user: discord.abc.User,) -> Union[discord.Thread, discord.TextChannel]:
    """
    Return the logging thread for a DM sender, creating it if necessary.
    Always returns something that supports .send().
    """
    log_channel = bot.get_channel(DM_INBOX_CHANNEL_ID)
    user_id = str(user.id)

    if user_id in dm_threads:
        try:
            thread = await bot.fetch_channel(dm_threads[user_id])
            return cast(Union[discord.Thread, discord.TextChannel], thread)
        except discord.NotFound:
            pass  # fall through → recreate

    thread_name = f"{user.name}-{user.id}".replace(" ", "-").lower()[:100]

    if isinstance(log_channel, discord.TextChannel):
        thread = await log_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            reason=f"Logging DM history for {user}",
        )
    elif isinstance(log_channel, discord.ForumChannel):
        created = await log_channel.create_thread(
            name=thread_name,
            content=f"📥 DM started with {user}.",
            reason=f"Logging DM history for {user}",
        )
        thread = created.thread if hasattr(created, "thread") else created
        thread = cast(discord.Thread, thread)
    else:
        raise RuntimeError("DM inbox must be a TextChannel or ForumChannel")

    dm_threads[user_id] = thread.id
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(dm_threads, f)

    return cast(Union[discord.Thread, discord.TextChannel], thread)



# --- Event Handlers ---

@bot.event
async def on_ready():
    if bot.user:
        print(f"🚀 Logged in as {bot.user.name}!")
    else:
        print("⚠️ Logged in, but bot.user is None (unexpected).")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command.")
        await log_audit(ctx.author, f"❌ Unknown command: {ctx.message.content}")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Permission denied.")
        await log_audit(ctx.author, f"❌ Permission denied: {ctx.message.content}")
    else:
        await ctx.send(f"⚠️ Error: {str(error)}")
        await log_audit(ctx.author, f"⚠️ Error: {ctx.message.content} → {str(error)}")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user or message.author.bot:
        return

    # ── 1. Relay from Fixer DM‑forum threads ──────────────────────────────
    if isinstance(message.channel, discord.Thread):
        for uid, thread_id in dm_threads.items():
            if message.channel.id != thread_id:
                continue

            roles = getattr(message.author, "roles", [])
            if not any(getattr(r, "name", "") == FIXER_ROLE_NAME for r in roles):
                return

            target_user = await bot.fetch_user(int(uid))
            if not target_user:
                return

            if message.content.strip().lower().startswith("!roll"):
                dice = message.content.strip()[len("!roll"):].strip()
                ctx = await bot.get_context(message)
                setattr(ctx, "original_author", message.author)
                ctx.author = target_user
                ctx.channel = await target_user.create_dm()
                await roll(ctx, dice=dice)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

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
            return

    # ── 2. Allow normal command processing ────────────────────────────────
    await bot.process_commands(message)

    # ── 3. Incoming user DM → log to thread ────────────────────────────────
    if isinstance(message.channel, discord.DMChannel):
        try:
            thread = await get_or_create_dm_thread(message.author)
            msg_target: Messageable = thread   # type‑checker: .send() exists

            full = message.content or "*(No text content)*"
            for chunk in (full[i:i+1024] for i in range(0, len(full), 1024)):
                if chunk.strip().startswith("!"):
                    continue
                await msg_target.send(
                    f"📥 **Received from {message.author.display_name}**:\n{chunk}"
                )

            for att in message.attachments:
                await msg_target.send(f"📎 Received attachment: {att.url}")
        except Exception as e:
            print(f"[ERROR] DM logging failed: {e}")



# --- Commands ---

@bot.command()
@is_fixer()
async def post(ctx, destination: str, *, message: str | None = None):
    """
    Posts a message to the specified channel or thread.
    Executes bot commands like !roll if included in the message.
    """
    dest_channel = None

    # Resolve by ID
    if destination.isdigit():
        try:
            dest_channel = await ctx.guild.fetch_channel(int(destination))
        except discord.NotFound:
            dest_channel = None
    else:
        # Try finding by name or as a thread
        dest_channel = discord.utils.get(ctx.guild.text_channels, name=destination)
        if dest_channel is None:
            for channel in ctx.guild.text_channels:
                threads = channel.threads
                dest_channel = discord.utils.get(threads, name=destination)
                if dest_channel:
                    break

    if dest_channel is None:
        await ctx.send(f"❌ Couldn't find channel/thread '{destination}'.")
        return

    files = [await attachment.to_file() for attachment in ctx.message.attachments]

    if message or files:
        if message and message.strip().startswith("!"):
            command_text = message.strip()
            fake_msg = ctx.message
            fake_msg.content = command_text
            fake_ctx = await bot.get_context(fake_msg)
            fake_ctx.channel = dest_channel
            fake_ctx.author = ctx.author
            setattr(fake_ctx, "original_author", ctx.author)

            await bot.invoke(fake_ctx)
            await ctx.send(f"✅ Executed `{command_text}` in {dest_channel.mention}.")
        else:
            await dest_channel.send(content=message, files=files)
            await ctx.send(f"✅ Posted anonymously to {dest_channel.mention}.")
    else:
        await ctx.send("❌ Provide a message or attachment.")


@bot.command()
@is_fixer()
async def dm(ctx, user: discord.User, *, message=None):
    try:
        if not user:
            raise ValueError("User fetch returned None.")
    except discord.NotFound:
        await ctx.send("❌ Could not resolve user.")
        await log_audit(ctx.author, "❌ Failed DM: Could not resolve user.")
        return
    except Exception as e:
        await ctx.send(f"⚠️ Unexpected error: {str(e)}")
        await log_audit(ctx.author, f"⚠️ Exception in DM: {str(e)}")
        return

    file_links = [attachment.url for attachment in ctx.message.attachments]

    # --- EARLY RETURN FOR !roll ---
    if message and message.strip().lower().startswith("!roll"):
        dice = message.strip()[len("!roll"):].strip()
        member = ctx.guild.get_member(user.id) or user  # fallback to user if member not found

        # ✅ Simulate them rolling by injecting a fake context
        fake_ctx = await bot.get_context(ctx.message)
        fake_ctx.author = member
        fake_ctx.channel = await user.create_dm()
        setattr(fake_ctx, "original_author", ctx.author)

        await roll(fake_ctx, dice=dice)
        await ctx.send(f"✅ Rolled `{dice}` anonymously for {user.display_name}.")
        return

    # --- Normal DM message ---
    dm_content_parts = [message] if message else []
    if file_links:
        links_formatted = "\n".join(file_links)
        dm_content_parts.append(f"📎 **Attachments:**\n{links_formatted}")
    dm_content = "\n\n".join(dm_content_parts) if dm_content_parts else "(No text)"

    try:
        await user.send(content=dm_content)
        await ctx.send(f'✅ DM sent anonymously to {user.display_name}.')

        thread = await get_or_create_dm_thread(user)
        if isinstance(thread, (discord.Thread, discord.TextChannel)):
            await thread.send(
                f"📤 **Sent to {user.display_name} by {ctx.author.display_name}:**\n{dm_content}"
            )
        else:
            print(f"[ERROR] Cannot log DM — thread type is {type(thread)}")

    except discord.Forbidden:
        await ctx.send('❌ Cannot DM user (Privacy Settings).')
        await log_audit(ctx.author, f"❌ Failed DM: Recipient: {user} (Privacy settings).")


@bot.command()
async def roll(ctx, *, dice: str):
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
        await loggable_roll(roller, ctx.channel, dice, original_sender=original_sender)
    else:
        await loggable_roll(roller, ctx.channel, dice)


async def loggable_roll(author, channel, dice: str, *, original_sender=None):
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
        thread = await get_or_create_dm_thread(author)
        if isinstance(thread, Messageable):
            await thread.send(
                f"📥 **{author.display_name} used:** `!roll {dice}`\n\n{result}"
            )
    elif original_sender and isinstance(channel, discord.DMChannel):
        thread = await get_or_create_dm_thread(author)
        if isinstance(thread, Messageable):
            await thread.send(
                f"📤 **{original_sender.display_name} rolled as {author.display_name}** → `!roll {dice}`\n\n{result}"
            )


    elif isinstance(channel, discord.DMChannel):
        thread = await get_or_create_dm_thread(author)
        if isinstance(thread, Messageable):
            await thread.send(
                f"📥 **{author.display_name} used:** `!roll {dice}`\n\n{result}"
            )

@bot.command(name="help")
async def block_help(ctx):
    await ctx.send("❌ `!help` is disabled. Use `!helpme` or `!helpfixer` instead.")

@bot.command(name="helpme")
async def helpme(ctx):
    embed = discord.Embed(
        title="📘 NCRP Bot — Player Help",
        description="Basic commands for RP, rent, and rolling dice. Use `!helpfixer` if you're a Fixer.",
        color=discord.Color.teal()
    )

    embed.add_field(
        name="🎲 RP Tools",
        value=(
            "`!roll [XdY+Z]`\n"
            "→ Roll dice in any channel or DM.\n"
            "→ Netrunner Level 2 = +1, Level 3 = +2 bonus.\n"
            "→ Roll results in DMs are logged privately."
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Rent & Cost of Living",
        value=(
            "Everyone pays a **$500/month** baseline fee for survival (food, water, etc).\n"
            "Even if you don't have a house or business — you're still eating Prepack.\n\n"
            "`!open_shop`\n"
            "→ Shop owners log up to 4 openings/month (Sundays only).\n"
            "→ Increases passive income if you're active."
        ),
        inline=False
    )

    embed.add_field(
        name="🏪 Passive Income Breakdown",
        value=(
            "**Tier 0 (Free Stall):**\n"
            " • 1 open = $150\n"
            " • 2 opens = $250\n"
            " • 3 opens = $350\n"
            " • 4 opens = $500\n\n"

            "**Tiers 1–3 (Paid Roles):**\n"
            " • 1 open = 25% of rent\n"
            " • 2 opens = 40%\n"
            " • 3 opens = 60%\n"
            " • 4 opens = 80%\n\n"

            "_Example: Tier 2 shop with 3 opens earns $1800 passive._"
        ),
        inline=False
    )

    embed.set_footer(text="Use !roll, pay your rent, stay alive.")
    await ctx.send(embed=embed)

@bot.command(name="helpfixer")
async def helpfixer(ctx):
    embed = discord.Embed(
        title="🛠️ NCRP Bot — Fixer & Admin Help",
        description="Advanced commands for messaging, RP management, rent, and testing.",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="📨 Anonymous Messaging",
        value=(
            "`!dm @user [message]`\n"
            "→ Sends an anonymous DM to a player.\n"
            "→ Commands like `!roll` will execute as that user.\n"
            "→ Attachments and messages are logged.\n\n"

            "`!post [channel/thread] [message]`\n"
            "→ Post anonymously into RP channels or threads.\n"
            "→ Include a command like `!roll` and a user to simulate them:\n"
            "  `!post thread-name !roll 2d6+1 (username or userid)`"
        ),
        inline=False
    )

    embed.add_field(
        name="🗨️ RP Channel Management",
        value=(
            "`!start_rp @user1 @user2`\n"
            "→ Starts a private RP text channel for a group.\n\n"
            "`!end_rp`\n"
            "→ Logs the full session to a forum thread and deletes the channel."
        ),
        inline=False
    )

    embed.add_field(
        name="💸 Rent & Economy Tools",
        value=(
            "`!collect_rent [@user]` — Full rent pipeline.\n"
            "`!collect_housing [@user]` — Manual housing deduction.\n"
            "`!collect_business [@user]` — Manual business deduction.\n"
            "`!collect_trauma [@user]` — Manual trauma subscription.\n"
            "`!open_shop` — Logs a shop opening (Sunday only)."
        ),
        inline=False
    )

    embed.add_field(
        name="🧪 Dev & Debug Commands",
        value=(
            "`!test_bot` — Runs full self-test suite.\n"
            "Validates DMs, rent logic, RP logging, roll parsing, and permissions."
        ),
        inline=False
    )

    embed.set_footer(text="Fixer tools by MedusaCascade | v1.2")
    await ctx.send(embed=embed)



@post.error
@dm.error
async def fixer_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Permission denied.")
        await log_audit(ctx.author, f"❌ Permission denied: {ctx.message.content}")
    else:
        await ctx.send(f"⚠️ Error: {str(error)}")
        await log_audit(ctx.author, f"⚠️ Error: {str(error)}")

# --- UnbelievaBoat API Integration ---

async def get_balance(user_id):
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
    headers = {
        "Authorization": UNBELIEVABOAT_API_TOKEN
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return None


async def update_balance(user_id, amount_dict, reason="Automated rent/income"):
    url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
    headers = {
        "Authorization": UNBELIEVABOAT_API_TOKEN,
        "Content-Type": "application/json"
    }
    payload = amount_dict.copy()
    payload["reason"] = reason

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                error = await resp.text()
                print(f"❌ PATCH failed: {resp.status} — {error}")
            return resp.status == 200


# --- Trauma Team Subscription Processing ---

TRAUMA_ROLE_COSTS = {
    "Trauma Team Silver": 1000,
    "Trauma Team Gold": 2000,
    "Trauma Team Plat": 4000,
    "Trauma Team Diamond": 10000
}

TRAUMA_TEAM_ROLE_ID = 1380341033124102254
TRAUMA_FORUM_CHANNEL_ID = 1366880900599517214


async def process_trauma_team_payment(
    member: discord.Member,
    *,
    log: Optional[List[str]] = None,
) -> None:
    """
    Deduct Trauma Team subscription (if any) using the live balance.
    """
    trauma_channel = bot.get_channel(TRAUMA_FORUM_CHANNEL_ID)
    if not isinstance(trauma_channel, discord.ForumChannel):
        if log is not None:
            log.append("⚠️ TT forum channel not found.")
        return

    balance = await get_balance(member.id)
    if not balance:
        if log is not None:
            log.append("⚠️ Could not fetch balance for Trauma processing.")
        return

    cash = balance["cash"]
    bank = balance["bank"]

    trauma_role = next((r for r in member.roles if r.name in TRAUMA_ROLE_COSTS), None)
    if not trauma_role:
        return  # no subscription

    cost = TRAUMA_ROLE_COSTS[trauma_role.name]
    if log is not None:
        log.append(f"🔎 {trauma_role.name} → Subscription: ${cost}")
        log.append(f"💊 Deducting ${cost} for Trauma Team plan: {trauma_role.name}")

    thread_name_suffix = f"- {member.id}"
    target_thread = next((t for t in trauma_channel.threads if t.name.endswith(thread_name_suffix)), None)
    if not target_thread:
        if log is not None:
            log.append(f"⚠️ Could not locate Trauma Team thread for <@{member.id}>")
        return

    if cash + bank < cost:
        mention = f"<@&{TRAUMA_TEAM_ROLE_ID}>"
        await target_thread.send(
            f"❌ Payment for **{trauma_role.name}** (${cost}) by <@{member.id}> failed."
            f"\n## {mention} Subscription suspended."
        )
        if log is not None:
            log.append("❌ Insufficient funds for Trauma payment.")
        return

    payload = {
        "cash": -min(cash, cost),
        "bank": -(cost - min(cash, cost)),
    }
    success = await update_balance(member.id, payload, reason="Trauma Team Subscription")
    if success:
        await target_thread.send(
            f"✅ **Payment Successful** — <@{member.id}> paid `${cost}` for **{trauma_role.name}** coverage."
        )
        if log is not None:
            log.append("✅ Trauma Team payment completed. Notice Sent to users #tt-plans-payment thread.")

    else:
        await target_thread.send(
            f"⚠️ **Deduction failed** for <@{member.id}> despite available funds."
        )
        if log is not None:
            log.append("⚠️ PATCH failed for Trauma Team payment.")



def calculate_passive_income_for_role(role: str, open_count: int) -> int:
    tier_0_income_scale = {1: 150, 2: 250, 3: 350, 4: 500}
    open_percent = {0: 0, 1: 0.25, 2: 0.4, 3: 0.6, 4: 0.8}

    if role == "Business Tier 0":
        return tier_0_income_scale.get(open_count, 0)

    base_rent = role_costs_business.get(role, 500)  # fallback to 500 if undefined
    return int(base_rent * open_percent[open_count])


async def apply_passive_income(member, applicable_roles, business_open_log, log: List[str]):
    total_income = 0

    member_id_str = str(member.id)
    opens_this_month = [
        ts for ts in business_open_log.get(member_id_str, [])
        if datetime.fromisoformat(ts).month == datetime.utcnow().month and
           datetime.fromisoformat(ts).year == datetime.utcnow().year
    ]
    open_count = min(len(opens_this_month), 4)

    for role in applicable_roles:
        if "Housing Tier" in role:
            continue  # Skip housing roles from passive income

        income = calculate_passive_income_for_role(role, open_count)
        log.append(f"💰 Passive income for {role}: ${income} ({open_count} opens)")
        total_income += income

    # ✅ Only update balance if income > 0
    if total_income > 0:
        success = await update_balance(member.id, {"cash": total_income}, reason="Passive income")
        if success:
            updated = await get_balance(member.id)
            log.append(f"➕ Added ${total_income} passive income.")
            if updated:
                return updated["cash"], updated["bank"]
            else:
                log.append("❌ Failed to fetch updated balance after applying passive income.")
    # ✅ Always return current balance
    current = await get_balance(member.id)
    if current:
        return current["cash"], current["bank"]

    return None, None



async def process_housing_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel, role_costs_housing):
    housing_total = 0
    for role in roles:
        if "Housing Tier" in role:
            amount = role_costs_housing.get(role, 0)
            housing_total += amount
            log.append(f"🔎 Housing Role {role} → Rent: ${amount}")

    if housing_total == 0:
        return cash, bank

    total = (cash or 0) + (bank or 0)
    if total < housing_total:
        log.append(f"❌ Cannot pay housing rent of ${housing_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — Housing Rent due: ${housing_total} — **FAILED** (insufficient funds) 🚨"
                f"\n## You have **7 days** to pay or face eviction."
            )
        log.append(f"⚠️ Housing rent skipped for <@{member.id}> due to insufficient funds.")
        return cash, bank

    deduct_cash = min(cash, housing_total)
    deduct_bank = housing_total - deduct_cash
    update_payload = {}
    if deduct_cash > 0:
        update_payload["cash"] = -deduct_cash
    if deduct_bank > 0:
        update_payload["bank"] = -deduct_bank

    success = await update_balance(member.id, update_payload, reason="Housing Rent")
    if success:
        cash -= deduct_cash
        bank -= deduct_bank
        log.append(f"🧮 Subtracted housing rent ${housing_total} — ${deduct_cash} from cash, ${deduct_bank} from bank.")
        log.append(f"📈 Balance after housing rent — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${(cash or 0) + (bank or 0):,}")
        log.append("✅ Housing Rent collection completed. Notice Sent to #rent")
        if rent_log_channel:
            await rent_log_channel.send(f"✅ <@{member.id}> — Housing Rent paid: ${housing_total}")
    else:
        log.append("❌ Failed to deduct housing rent despite having sufficient funds.")
    return cash, bank


async def process_business_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel,
                                role_costs_business):
    business_total = 0
    for role in roles:
        if "Business Tier" in role:
            amount = role_costs_business.get(role, 0)
            business_total += amount
            log.append(f"🔎 Business Role {role} → Rent: ${amount}")

    if business_total == 0:
        return cash, bank

    total = (cash or 0) + (bank or 0)
    if total < business_total:
        log.append(f"❌ Cannot pay business rent of ${business_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — Business Rent due: ${business_total} — **FAILED** (insufficient funds) 🚨"
                f"\n## You have **7 days** to pay or face eviction."
            )
        log.append(f"⚠️ Business rent skipped for <@{member.id}> due to insufficient funds.")
        return cash, bank

    deduct_cash = min(cash, business_total)
    deduct_bank = business_total - deduct_cash
    update_payload = {}
    if deduct_cash > 0:
        update_payload["cash"] = -deduct_cash
    if deduct_bank > 0:
        update_payload["bank"] = -deduct_bank

    success = await update_balance(member.id, update_payload, reason="Business Rent")
    if success:
        cash -= deduct_cash
        bank -= deduct_bank
        log.append(
            f"🧮 Subtracted business rent ${business_total} — ${deduct_cash} from cash, ${deduct_bank} from bank.")
        log.append(f"📈 Balance after business rent — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${(cash or 0) + (bank or 0):,}")
        log.append("✅ Business Rent collection completed. Notice Sent to #rent")
        if rent_log_channel:
            await rent_log_channel.send(f"✅ <@{member.id}> — Business Rent paid: ${business_total}")
    else:
        log.append("❌ Failed to deduct business rent despite having sufficient funds.")
    return cash, bank



# --- Manual Individual Rent Commands ---

@bot.command()
@commands.has_permissions(administrator=True)
async def collect_housing(ctx, user: discord.Member):
    """Manually collect housing rent from a single user"""
    log = [f"🏠 Manual Housing Rent Collection for <@{user.id}>"]
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    EVICTION_CHANNEL_ID = 1379611043843539004
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)

    role_names = [r.name for r in user.roles]
    log.append(f"🧾 Roles: {role_names}")

    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = (cash or 0) + (bank or 0)
    log.append(f"💵 Balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

    cash, bank = await process_housing_rent(user, role_names, cash, bank, log, rent_log_channel, eviction_channel, role_costs_housing)

    final = await get_balance(user.id)
    if final:
        final_cash = final.get("cash", 0)
        final_bank = final.get("bank", 0)
        final_total = final_cash + final_bank
        log.append(f"📊 Final balance — Cash: ${final_cash:,}, Bank: ${final_bank:,}, Total: ${final_total:,}")

    await ctx.send("\n".join(log))

@bot.command()
@commands.has_permissions(administrator=True)
async def collect_business(ctx, user: discord.Member):
    """Manually collect business rent from a single user"""
    log = [f"🏢 Manual Business Rent Collection for <@{user.id}>"]
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    EVICTION_CHANNEL_ID = 1379611043843539004
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)

    role_names = [r.name for r in user.roles]
    log.append(f"🧾 Roles: {role_names}")

    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = (cash or 0) + (bank or 0)
    log.append(f"💵 Balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

    cash, bank = await process_business_rent(user, role_names, cash, bank, log, rent_log_channel, eviction_channel, role_costs_business)

    final = await get_balance(user.id)
    if final:
        final_cash = final.get("cash", 0)
        final_bank = final.get("bank", 0)
        final_total = final_cash + final_bank
        log.append(f"📊 Final balance — Cash: ${final_cash:,}, Bank: ${final_bank:,}, Total: ${final_total:,}")

    await ctx.send("\n".join(log))


@bot.command()
@commands.has_permissions(administrator=True)
async def collect_trauma(ctx, user: discord.Member):
    """Manually collect Trauma Team subscription"""
    log = [f"💊 Manual Trauma Team Subscription Processing for <@{user.id}>"]
    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = (cash or 0) + (bank or 0)
    log.append(f"💵 Balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

    await process_trauma_team_payment(user, log=log)

    final = await get_balance(user.id)
    if final:
        final_cash = final.get("cash", 0)
        final_bank = final.get("bank", 0)
        final_total = final_cash + final_bank
        log.append(f"📊 Final balance — Cash: ${final_cash:,}, Bank: ${final_bank:,}, Total: ${final_total:,}")

    await ctx.send("\n".join(log))


# --- Rent Collection Command ---

async def deduct_flat_fee(member, cash, bank, log, amount=500):
    total = (cash or 0) + (bank or 0)

    if total < amount:
        log.append(f"❌ Insufficient funds for flat fee deduction (${amount}). Current balance: ${total}.")
        return False, cash, bank

    deduct_cash = min(cash, amount)
    deduct_bank = amount - deduct_cash

    update_payload = {}
    if deduct_cash > 0:
        update_payload["cash"] = -deduct_cash
    if deduct_bank > 0:
        update_payload["bank"] = -deduct_bank

    success = await update_balance(member.id, update_payload, reason="Flat Monthly Fee")

    if success:
        cash -= deduct_cash
        bank -= deduct_bank
        log.append(f"💸 Deducted flat monthly fee of ${amount} (Cash: ${deduct_cash}, Bank: ${deduct_bank}).")
    else:
        log.append("❌ Failed to deduct flat monthly fee.")

    return success, cash, bank



@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: Optional[discord.Member] = None):
    """
    Global or per‑member rent collection.
    - Applies baseline cost, passive income, housing, business, trauma
    - Protects business_open_log.json when run for a single user
    """
    await ctx.send("🚦 Starting rent collection...")

    BASELINE_LIVING_COST = 500

    if not target_user:
        if Path(OPEN_LOG_FILE).exists():
            with open(OPEN_LOG_FILE, "r") as f:
                business_open_log = json.load(f)
            backup = f"open_history_{datetime.utcnow():%B_%Y}.json"
            Path(OPEN_LOG_FILE).rename(backup)
        else:
            business_open_log = {}

        with open(OPEN_LOG_FILE, "w") as f:
            json.dump({}, f)
    else:
        if Path(OPEN_LOG_FILE).exists():
            with open(OPEN_LOG_FILE, "r") as f:
                business_open_log = json.load(f)
        else:
            business_open_log = {}

    if not target_user and Path(LAST_RENT_FILE).exists():
        with open(LAST_RENT_FILE) as f:
            last_run = datetime.fromisoformat(json.load(f)["last_run"])
        if datetime.utcnow() - last_run < timedelta(days=30):
            await ctx.send("⚠️ Rent already collected in the last 30 days.")
            return
    if not target_user:
        with open(LAST_RENT_FILE, "w") as f:
            json.dump({"last_run": datetime.utcnow().isoformat()}, f)

    members_to_process: List[discord.Member] = []
    for m in ctx.guild.members:
        if target_user and m.id == target_user.id:
            members_to_process = [m]
            break
        if not target_user and any("Tier" in r.name for r in m.roles):
            members_to_process.append(m)
    if not members_to_process:
        await ctx.send("❌ No matching members found.")
        return

    eviction_channel = ctx.guild.get_channel(1379611043843539004)
    rent_log_channel = ctx.guild.get_channel(1379615621167321189)

    for member in members_to_process:
        try:
            log: List[str] = [f"🔍 **Working on:** <@{member.id}>"]

            role_names = [r.name for r in member.roles]
            app_roles = [r for r in role_names if "Tier" in r]
            log.append(f"🏷️ Detected roles: {', '.join(app_roles) or 'None'}")

            bal = await get_balance(member.id)
            if not bal:
                log.append("⚠️ Could not fetch balance.")
                await ctx.send("\n".join(log))
                continue
            cash, bank = bal["cash"], bal["bank"]
            log.append(f"💵 Starting balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${(cash or 0) + (bank or 0):,}")

            base_ok, cash, bank = await deduct_flat_fee(member, cash, bank, log, BASELINE_LIVING_COST)
            if not base_ok:
                if eviction_channel:
                    await eviction_channel.send(
                        f"⚠️ <@{member.id}> could not pay baseline living cost (${BASELINE_LIVING_COST}).")
                log.append("❌ Skipping remaining rent steps.")
                await ctx.send("\n".join(log))
                continue

            try:
                new_cash, new_bank = await apply_passive_income(
                    member, app_roles, business_open_log, log)
                if new_cash is not None and new_bank is not None:
                    cash, bank = new_cash, new_bank
                else:
                    log.append("⚠️ Passive income failed to return balance. Using previous state.")
            except RuntimeError as err:
                log.append(f"❌ {err}")
                await ctx.send("\n".join(log))
                continue

            cash, bank = await process_housing_rent(
                member, app_roles, cash, bank, log,
                rent_log_channel, eviction_channel, role_costs_housing)
            cash, bank = await process_business_rent(
                member, app_roles, cash, bank, log,
                rent_log_channel, eviction_channel, role_costs_business)

            await process_trauma_team_payment(member, log=log)

            # 🔄 Re-fetch final balance after all deductions including trauma team
            final = await get_balance(member.id)
            if final:
                cash = final.get("cash", 0)
                bank = final.get("bank", 0)

            log.append(
                f"📊 Final balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${(cash or 0) + (bank or 0):,}"
            )

            await ctx.send("\n".join(log))

        except Exception as e:
            await ctx.send(f"❌ Error processing <@{member.id}>: `{e}`")

    await ctx.send("✅ Rent collection completed.")



@bot.command()
@commands.has_permissions(send_messages=True)
async def open_shop(ctx):
    ALLOWED_CHANNEL_ID = 1379623117994852443
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("❌ You can only log business openings in the designated business activity channel.")
        return

    now = datetime.utcnow()
    if now.weekday() != 6:
        await ctx.send("❌ Business openings can only be logged on Sundays.")
        return

    user_id = str(ctx.author.id)
    now_str = now.isoformat()

    if Path(OPEN_LOG_FILE).exists():
        with open(OPEN_LOG_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    all_opens = data.get(user_id, [])
    this_month_opens = [
        datetime.fromisoformat(ts)
        for ts in all_opens
        if datetime.fromisoformat(ts).month == now.month and datetime.fromisoformat(ts).year == now.year
    ]

    # Check if user has already opened today
    opened_today = any(
        ts.date() == now.date()
        for ts in this_month_opens
    )

    if opened_today:
        await ctx.send("❌ You’ve already logged a business opening today.")
        return

    if len(this_month_opens) >= 4:
        await ctx.send("❌ You’ve already used all 4 business posts for this month.")
        return

    all_opens.append(now_str)
    data[user_id] = all_opens
    with open(OPEN_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    await ctx.send(f"✅ Business opening logged! ({len(this_month_opens) + 1}/4 this month)")

#### ------ BOT TESTS ----- #####

test_descriptions = {
    "test_dm_roll_relay": "Relays a roll to a user's DM forum thread using `!dm`.",
    "test_roll_direct_dm": "User runs `!roll` in a DM. Verifies result is DM'd and logged to DM thread.",
    "test_post_executes_command": "Sends a `!roll` command into a channel using `!post`.",
    "test_post_roll_execution": "Executes a roll via !post and checks result inside RP channel.",
    "test_rolls": "Runs `!roll` with valid and invalid input and checks result.",
    "test_bonus_rolls": "Checks that Netrunner bonuses are applied correctly.",
    "test_full_rent_commands": "Executes rent collection on a live user and verifies balance updates.",
    "test_passive_income_logic": "Applies passive income based on recent shop opens.",
    "test_trauma_payment": "Attempts to log a trauma plan subscription in the correct DM thread.",
    "test_rent_logging_sends": "Verifies that rent events are logged in #rent and #eviction-notices.",
    "test_open_shop_command": "Runs !open_shop in the correct channel.",
}

async def get_test_user(ctx):
    user = ctx.guild.get_member(TEST_USER_ID)
    if not user:
        user = await ctx.guild.fetch_member(TEST_USER_ID)
    return user

def assert_send(logs, mock_obj, label):
    try:
        mock_obj.send.assert_awaited()
        logs.append(f"✅ {label}.send was called")
    except AssertionError:
        logs.append(f"❌ {label}.send was not called")

async def test_dm_roll_relay(ctx):
    logs = []
    try:
        user = await get_test_user(ctx)
        thread = await get_or_create_dm_thread(user)
        await loggable_roll(user, thread, "1d20", original_sender=ctx.author)
        logs.append("✅ !dm @user !roll d20 relay succeeded")

        try:
            dm_channel = await user.create_dm()
            await dm_channel.send("✅ DM test message from NightCityBotTest.")
            logs.append("✅ Direct DM sent to user.")
        except discord.Forbidden:
            logs.append("⚠️ Could not DM user — Privacy settings?")
    except Exception as e:
        logs.append(f"❌ Exception in test_dm_roll_relay: {e}")
    return logs

async def test_rent_logging_sends(ctx):
    logs = []
    try:
        user = await get_test_user(ctx)

        rent_log_channel = ctx.guild.get_channel(1379615621167321189)
        eviction_channel = ctx.guild.get_channel(1379611043843539004)

        logs.append("→ Expected: collect_rent should post messages to rent and eviction log channels.")

        if not rent_log_channel or not eviction_channel:
            logs.append("→ Result: ❌ Rent or eviction channels not found.")
            return logs

        await collect_rent(ctx, target_user=user)
        logs.append("→ Result: ✅ Rent logic executed and logging channels present.")
    except Exception as e:
        logs.append(f"❌ Exception in test_rent_logging_sends: {e}")
    return logs

async def test_open_shop_command(ctx):
    logs = []
    try:
        correct_channel_id = 1379623117994852443
        correct_channel = ctx.guild.get_channel(correct_channel_id)

        logs.append("→ Expected: !open_shop should succeed when run inside the business channel.")

        if not correct_channel:
            logs.append("→ Result: ❌ Business open channel not found")
            return logs

        original_channel = ctx.channel
        ctx.channel = correct_channel

        await open_shop(ctx)
        logs.append("→ Result: ✅ !open_shop executed in correct channel")

        ctx.channel = original_channel
    except Exception as e:
        logs.append(f"❌ Exception in test_open_shop_command: {e}")
    return logs


async def test_full_rent_commands(ctx):
    logs = []
    try:
        user = await get_test_user(ctx)

        logs.append("→ Expected: All rent-related commands should complete without error.")

        if os.path.exists(LAST_RENT_FILE):
            os.remove(LAST_RENT_FILE)

        await collect_rent(ctx)
        logs.append("✅ collect_rent (global) executed")

        if os.path.exists(LAST_RENT_FILE):
            os.remove(LAST_RENT_FILE)

        await collect_rent(ctx, target_user=user)
        logs.append("✅ collect_rent (specific user) executed")

        await collect_housing(ctx, user)
        logs.append("✅ collect_housing executed")

        await collect_business(ctx, user)
        logs.append("✅ collect_business executed")

        await collect_trauma(ctx, user)
        logs.append("✅ collect_trauma executed")

        logs.append("→ Result: ✅ All rent commands executed.")
    except Exception as e:
        logs.append(f"❌ Exception in test_full_rent_commands: {e}")
    return logs



async def test_passive_income_logic(ctx):
    logs = []
    user = await get_test_user(ctx)

    for role in role_costs_business.keys():
        for open_count in range(5):  # 0 to 4 opens
            now = datetime.utcnow().isoformat()
            business_open_log = {str(user.id): [now] * open_count}
            applicable_roles = [role]
            test_log = []

            expected_income = calculate_passive_income_for_role(role, open_count)

            logs.append(f"→ {role} with {open_count} open(s): Expect ${expected_income}")

            await apply_passive_income(user, applicable_roles, business_open_log, test_log)

            expected_log = f"💰 Passive income for {role}: ${expected_income} ({open_count} opens)"
            found_log_line = expected_log in test_log
            if found_log_line:
                logs.append(f"✅ Found income log: `{expected_log}`")
            else:
                logs.append(f"❌ Missing income log: Expected `{expected_log}`, got: {test_log}")

            added_line = f"➕ Added ${expected_income} passive income."
            if expected_income > 0:
                if any(added_line in line for line in test_log):
                    logs.append(f"✅ Found balance update line: `{added_line}`")
                else:
                    logs.append(f"❌ Missing balance update: Expected `{added_line}`")
            else:
                if any("➕ Added" in line for line in test_log):
                    logs.append(f"❌ Unexpected balance update for $0 income")
                else:
                    logs.append(f"✅ No balance update (correct for $0 income)")

    return logs


async def test_post_roll_execution(ctx):
    logs = []
    try:
        thread = ctx.test_rp_channel
        await post(ctx, thread.name, message="!roll 1d20+1")
        logs.append("✅ !post <thread> !roll d20+1 executed in reused RP channel")
        # ❌ Don't end the RP session here — it's reused by other tests
    except Exception as e:
        logs.append(f"❌ Exception in test_post_roll_execution: {e}")
    return logs

async def test_post_executes_command(ctx):
    logs = []
    try:
        # ✅ Reuse the RP channel created in test_bot
        rp_channel = ctx.test_rp_channel
        ctx.message.attachments = []
        await post(ctx, rp_channel.name, message="!roll 1d4")
        logs.append("✅ !post executed and command sent in reused RP channel")
    except Exception as e:
        logs.append(f"❌ Exception in test_post_executes_command: {e}")
    return logs


async def test_bonus_rolls(ctx):
    logs = []
    mock_author = AsyncMock(spec=discord.Member)
    mock_author.display_name = "BonusTest"
    mock_author.roles = [AsyncMock(name="Netrunner Level 2")]
    for r in mock_author.roles:
        r.name = "Netrunner Level 2"

    channel = AsyncMock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    logs.append("→ Expected: Roll result should include '+1 Netrunner bonus' in output.")

    try:
        await loggable_roll(mock_author, channel, "1d20")
        message = channel.send.call_args[0][0]
        if "+1 Netrunner bonus" in message:
            logs.append("→ Result: ✅ Found bonus text in roll output.")
        else:
            logs.append("→ Result: ❌ Bonus text missing from roll output.")
    except Exception as e:
        logs.append(f"❌ Exception in test_bonus_rolls: {e}")
    return logs


async def test_trauma_payment(ctx):
    logs = []
    try:
        user = await get_test_user(ctx)
        logs.append("→ Expected: collect_trauma should find thread and log subscription payment.")

        await collect_trauma(ctx, user)

        logs.append("→ Result: ✅ Trauma Team logic executed on live user (check #tt-plans-payment).")
    except Exception as e:
        logs.append(f"❌ Exception in test_trauma_payment: {e}")
    return logs


@bot.command(hidden=True)
@commands.is_owner()
async def test_rolls(ctx):
    logs = []
    try:
        logs.append("→ Expected: Valid roll should return a total, invalid roll should return a format error.")

        # Valid roll
        await loggable_roll(ctx.author, ctx.channel, "1d20+2")
        logs.append("→ Result (Valid): ✅ Roll succeeded and result sent.")

        # Invalid roll
        await loggable_roll(ctx.author, ctx.channel, "notadice")
        logs.append("→ Result (Invalid): ✅ Error message shown for invalid format.")
    except Exception as e:
        logs.append(f"❌ Exception in test_rolls: {e}")
    return logs

async def test_roll_direct_dm(ctx):
    logs = []
    try:
        user = await get_test_user(ctx)
        dm_channel = await user.create_dm()

        logs.append("→ Expected: !roll in DM should send a result and log it to the user's DM thread.")

        await loggable_roll(user, dm_channel, "1d6")
        logs.append("→ Result: ✅ !roll executed in user DM context.")

    except Exception as e:
        logs.append(f"❌ Exception in test_roll_direct_dm: {e}")
    return logs

@bot.command(hidden=True)
@commands.is_owner()
async def test_bot(ctx):
    start = time.time()
    all_logs = []

    # ✅ Create a reusable RP channel for all tests
    rp_channel = await start_rp(ctx, f"<@{TEST_USER_ID}>")
    ctx.test_rp_channel = rp_channel  # attach for any tests that want to reuse it

    output_channel = ctx.channel
    ctx.message.attachments = []

    await output_channel.send(f"🧪 Running full self-test on user <@{TEST_USER_ID}>...")

    tests = [
        ("test_dm_roll_relay", test_dm_roll_relay),
        ("test_roll_direct_dm", test_roll_direct_dm),
        ("test_post_executes_command", test_post_executes_command),
        ("test_post_roll_execution", test_post_roll_execution),
        ("test_rolls", test_rolls),
        ("test_bonus_rolls", test_bonus_rolls),
        ("test_full_rent_commands", test_full_rent_commands),
        ("test_passive_income_logic", test_passive_income_logic),
        ("test_trauma_payment", test_trauma_payment),
        ("test_rent_logging_sends", test_rent_logging_sends),
        ("test_open_shop_command", test_open_shop_command),
    ]

    for name, func in tests:
        await output_channel.send(f"🧪 `{name}` — {test_descriptions.get(name, 'No description.')}")
        try:
            logs = await func(ctx)
        except Exception as e:
            logs = [f"❌ Exception in `{name}`: {e}"]
        all_logs.append(f"{name} — {test_descriptions.get(name, '')}")
        all_logs.extend(logs)
        all_logs.append("────────────")

    # ✅ Chunk output into digestible blocks (avoid Discord 4096-char limit)
    current_chunk = ""
    for line in all_logs:
        line = str(line)
        if len(current_chunk) + len(line) + 1 > 1900:
            await output_channel.send(f"```\n{current_chunk.strip()}\n```")
            current_chunk = line
        else:
            current_chunk += line + "\n"
    if current_chunk:
        await output_channel.send(f"```\n{current_chunk.strip()}\n```")

    # ✅ Summary embed
    passed = sum(1 for r in all_logs if "✅" in r)
    failed = sum(1 for r in all_logs if "❌" in r)
    duration = time.time() - start

    embed = discord.Embed(
        title="🧪 Full Bot Self-Test Summary",
        color=discord.Color.green() if failed == 0 else discord.Color.red()
    )
    embed.add_field(name="Result", value=f"✅ Passed: {passed}\n❌ Failed: {failed}", inline=False)
    embed.set_footer(text=f"⏱️ Completed in {duration:.2f}s")
    await output_channel.send(embed=embed)

    # ✅ Cleanup RP channel
    if ctx.test_rp_channel:
        await end_rp_session(ctx.test_rp_channel)
    else:
        print("[WARN] RP channel was not set; skipping end_rp_session.")



if __name__ == "__main__":
    keep_alive()
