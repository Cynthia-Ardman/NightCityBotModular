# Merged NCRP Bot Script
# ========================

# --- DM Bot Functionality ---
import discord
from discord.ext import commands
import random
import re
import json
import os
from flask import Flask
from threading import Thread

TOKEN = "MTIxMzI1MjEwNjA2NTAyMzAzNw.GDvA6e.HrYYp-mdMJYpX4VGXI-p7-UbEpf93gNbQNmQqI"
AUDIT_LOG_CHANNEL_ID = 1349160856688267285
FIXER_ROLE_NAME = "Fixer"
DM_INBOX_CHANNEL_ID = 1379222007513874523
THREAD_MAP_FILE = "thread_map.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.dm_messages = True

SEEN_MSG_ID_FILE = "backfill_seen_ids.json"

# Load seen message IDs
seen_msg_ids = set()
if os.path.exists(SEEN_MSG_ID_FILE):
    try:
        with open(SEEN_MSG_ID_FILE, "r") as f:
            seen_msg_ids = set(json.load(f))
    except Exception as e:
        print(f"[WARN] Could not load seen message IDs: {e}")


bot = commands.Bot(command_prefix='!', intents=intents)

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

dm_threads = {}
if os.path.exists(THREAD_MAP_FILE):
    try:
        with open(THREAD_MAP_FILE, "r") as f:
            dm_threads = json.load(f)
    except Exception as e:
        print(f"[THREAD CACHE] Failed to load thread_map.json: {e}")

def is_fixer():
    async def predicate(ctx):
        return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None
    return commands.check(predicate)

@bot.command()
@is_fixer()
async def post(ctx, destination: str, *, message=None):
    dest_channel = None

    if destination.isdigit():
        try:
            dest_channel = await ctx.guild.fetch_channel(int(destination))
        except discord.NotFound:
            dest_channel = None
    else:
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
        await dest_channel.send(content=message, files=files)
        await ctx.send(f'✅ Posted anonymously to {dest_channel.mention}.')
    else:
        await ctx.send("❌ Provide a message or attachment.")

@bot.command()
@is_fixer()
async def dm(ctx, user_id: int, *, message=None):
    try:
        user = await bot.fetch_user(user_id)
        if not user:
            raise ValueError("User fetch returned None.")
    except discord.NotFound:
        await ctx.send(f"❌ User ID `{user_id}` not found.")
        await log_audit(ctx.author, f"❌ Failed DM: Invalid user ID `{user_id}`.")
        return
    except Exception as e:
        await ctx.send(f"⚠️ Unexpected error: {str(e)}")
        await log_audit(ctx.author, f"⚠️ Exception in DM: {str(e)}")
        return

    file_links = [attachment.url for attachment in ctx.message.attachments]

    dm_content_parts = [message] if message else []
    if file_links:
        links_formatted = "\n".join(file_links)
        dm_content_parts.append(f"📎 **Attachments:**\n{links_formatted}")
    dm_content = "\n\n".join(dm_content_parts) if dm_content_parts else "(No text)"

    try:
        await user.send(content=dm_content)
        await ctx.send(f'✅ DM sent anonymously to {user.display_name}.')

        thread = await get_or_create_dm_thread(user)
        await thread.send(f"📤 **Sent to {user}**:\n{dm_content}")
    except discord.Forbidden:
        await ctx.send('❌ Cannot DM user (Privacy Settings).')
        await log_audit(ctx.author, f"❌ Failed DM: Recipient: {user} (Privacy settings).")

@bot.command()
async def roll(ctx, *, dice: str):
    dice_pattern = r'(?:(\d*)d)?(\d+)([+-]\d+)?'
    match = re.fullmatch(dice_pattern, dice.replace(' ', ''))

    if not match:
        await ctx.send('🎲 Format: `!roll XdY+Z` (Example: `!roll 2d6+3`)')
        await log_audit(ctx.author, f"❌ Invalid dice roll: `{dice}`")
        return

    dice_count, dice_sides, modifier = match.groups()
    dice_count = int(dice_count) if dice_count else 1
    dice_sides = int(dice_sides)
    modifier = int(modifier) if modifier else 0

    rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
    total = sum(rolls) + modifier

    rolls_detailed = ', '.join(f'**{roll}**' for roll in rolls)
    modifier_text = f" {'+' if modifier >= 0 else '-'} {abs(modifier)}" if modifier else ""

    result_message = (
        f'🎲 You rolled: {dice_count}d{dice_sides}{modifier_text}\n'
        f'**Results:** {rolls_detailed}\n'
        f'**Total:** {total}'
    )

    await ctx.send(result_message)

@bot.command()
async def helpme(ctx):
    embed = discord.Embed(title="🤖 NCRP Bot Help", color=discord.Color.green())
    embed.add_field(name="!post #channel [message]", value="Anonymous post (Fixers only).", inline=False)
    embed.add_field(name="!dm user_id [message]", value="Anonymous DM by user ID (Fixers only).", inline=False)
    embed.add_field(name="!roll [XdY+Z]", value="Roll dice. Example: `!roll 2d6+3`.", inline=False)
    embed.add_field(name="!helpme", value="Show this help message.", inline=False)
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


async def log_audit(user, action_desc):
    audit_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if audit_channel:
        embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Action", value=action_desc, inline=False)
        await audit_channel.send(embed=embed)
    print(f"[AUDIT] {user}: {action_desc}")

async def get_or_create_dm_thread(user: discord.User):
    log_channel = bot.get_channel(DM_INBOX_CHANNEL_ID)
    user_id = str(user.id)
    print(f"[THREAD] Checking thread for {user.name} ({user_id})")

    if user_id in dm_threads:
        try:
            thread = await bot.fetch_channel(dm_threads[user_id])
            print(f"[THREAD] Reusing thread {thread.id}")
            return thread
        except discord.NotFound:
            print("[THREAD] Thread not found, creating new one.")

    thread_name = f"{user.name}-{user.id}".replace(" ", "-").lower()[:100]
    if isinstance(log_channel, discord.TextChannel):
        thread = await log_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            reason=f"Logging DM history for {user.name} ({user.id})"
        )
    elif isinstance(log_channel, discord.ForumChannel):
        created = await log_channel.create_thread(
            name=thread_name,
            content="📥 Creating DM thread...",
            reason=f"Logging DM history for {user.name} ({user.id})"
        )
        thread = created.thread
    else:
        raise RuntimeError("DM inbox must be a TextChannel or ForumChannel.")

    dm_threads[user_id] = thread.id
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(dm_threads, f)

    print(f"[THREAD] Created thread {thread.name} ({thread.id})")
    return thread

@bot.event
async def on_ready():
    print(f'🚀 Logged in as {bot.user.name}!')

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        print(f"[DM RECEIVED] From {message.author}: {message.content}")
        try:
            thread = await get_or_create_dm_thread(message.author)
            full_content = message.content or "*(No text content)*"
            chunks = [full_content[i:i + 1024] for i in range(0, len(full_content), 1024)]
            for chunk in chunks:
                await thread.send(f"📥 **Received from {message.author.display_name}**:\n{chunk}")
            for attachment in message.attachments:
                await thread.send(f"📎 Received attachment: {attachment.url}")
        except Exception as e:
            print(f"[ERROR] DM logging failed: {e}")

@bot.command()
@is_fixer()
async def backfill_dm_logs(ctx, channel_id: int):
    source_channel = bot.get_channel(channel_id)
    print(f"[BACKFILL] Source: {channel_id} → Target: {DM_INBOX_CHANNEL_ID}")

    if not source_channel or not hasattr(source_channel, "history"):
        await ctx.send("❌ Cannot read from that channel.")
        return

    messages = [msg async for msg in source_channel.history(limit=500, oldest_first=True)]
    print(f"[BACKFILL] Loaded {len(messages)} messages.")

    new_seen_ids = set()
    backfilled = 0

    for msg in messages:
        if msg.id in seen_msg_ids:
            continue

        content = msg.content.strip()
        print(f"[BACKFILL] Checking: {msg.author.display_name}: {content[:60]}")

        # Handle !dm commands
        if content.startswith("!dm"):
            match = re.search(r"(\d{17,20})", content)
            if match:
                user_id = match.group(1)
                try:
                    user = await bot.fetch_user(int(user_id))
                    thread = await get_or_create_dm_thread(user)
                    await thread.send(f"📤 **Backfilled message to {user.name} ({user.id})**:\n{content}")
                    dm_threads[user_id] = thread.id
                    with open(THREAD_MAP_FILE, "w") as f:
                        json.dump(dm_threads, f)
                    new_seen_ids.add(msg.id)
                    backfilled += 1
                except Exception as e:
                    print(f"[ERROR] Failed to backfill TO {user_id}: {e}")
            continue

        # Handle embed-style replies from users
        if msg.embeds:
            embed = msg.embeds[0]
            sender_field = next((f for f in embed.fields if f.name.lower() == "sender"), None)
            content_field = next((f for f in embed.fields if f.name.lower() == "content"), None)

            if sender_field and content_field:
                sender_match = re.search(r"\((\d{17,20})\)", sender_field.value)
                if sender_match:
                    user_id = sender_match.group(1)
                    try:
                        user = await bot.fetch_user(int(user_id))
                        thread = await get_or_create_dm_thread(user)
                        combined = f"📥 **Backfilled incoming reply from {user.name} ({user.id})**:\n{content_field.value}"
                        if embed.description:
                            combined += f"\n\n{embed.description}"
                        await thread.send(combined)
                        dm_threads[user_id] = thread.id
                        with open(THREAD_MAP_FILE, "w") as f:
                            json.dump(dm_threads, f)
                        new_seen_ids.add(msg.id)
                        backfilled += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to backfill FROM {user_id}: {e}")
            continue

    # Save updated seen message IDs
    if new_seen_ids:
        try:
            seen_msg_ids.update(new_seen_ids)
            with open(SEEN_MSG_ID_FILE, "w") as f:
                json.dump(list(seen_msg_ids), f)
            print(f"[BACKFILL] Saved {len(new_seen_ids)} new seen message IDs.")
        except Exception as e:
            print(f"[ERROR] Failed to save seen IDs: {e}")

    await ctx.send(f"✅ Backfill complete. Routed {backfilled} new messages.")
    print(f"[DONE] Routed {backfilled} messages.")


keep_alive()
bot.run(TOKEN)

# --- Rent Bot Functionality ---
import discord
from discord.ext import commands
import random
import re
import json
import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
import asyncio
import aiohttp
from pathlib import Path
from calendar import month_name

TOKEN = "MTM3OTUyNzc4OTQzNDI0MTExNA.GTC6-z.HzfIqRu9Zqb5I2QTHGNPEL3M7haCEKPTghH458"
AUDIT_LOG_CHANNEL_ID = 1341160960924319804
FIXER_ROLE_NAME = "Fixer"
DM_INBOX_CHANNEL_ID = 1341160960924319804  # Replace with your DM inbox channel ID                 # Replace with your actual fixer role name
THREAD_MAP_FILE = "thread_map.json"
UNBELIEVABOAT_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2NDQ1MTE2NDkyMDI2IiwiaWF0IjoxNzQ4OTk0MjA4fQ.QK7MeBdOcmUi_-DQImJvsMrtCJ2gGefGVQZfUDS0ruY"
GUILD_ID = "1320924574761746473"
OPEN_LOG_FILE = "business_open_log.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.dm_messages = True

SEEN_MSG_ID_FILE = "backfill_seen_ids.json"

# Load seen message IDs
seen_msg_ids = set()
if os.path.exists(SEEN_MSG_ID_FILE):
    try:
        with open(SEEN_MSG_ID_FILE, "r") as f:
            seen_msg_ids = set(json.load(f))
    except Exception as e:
        print(f"[WARN] Could not load seen message IDs: {e}")

bot = commands.Bot(command_prefix='!', intents=intents)

app = Flask('')


@app.route('/')
def home():
    return "Bot is alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


dm_threads = {}
if os.path.exists(THREAD_MAP_FILE):
    try:
        with open(THREAD_MAP_FILE, "r") as f:
            dm_threads = json.load(f)
    except Exception as e:
        print(f"[THREAD CACHE] Failed to load thread_map.json: {e}")


def is_fixer():
    async def predicate(ctx):
        return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None

    return commands.check(predicate)


@bot.command()
@is_fixer()
async def post(ctx, destination: str, *, message=None):
    dest_channel = None

    if destination.isdigit():
        try:
            dest_channel = await ctx.guild.fetch_channel(int(destination))
        except discord.NotFound:
            dest_channel = None
    else:
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
        await dest_channel.send(content=message, files=files)
        await ctx.send(f'✅ Posted anonymously to {dest_channel.mention}.')
    else:
        await ctx.send("❌ Provide a message or attachment.")


@bot.command()
@is_fixer()
async def dm(ctx, user_id: int, *, message=None):
    try:
        user = await bot.fetch_user(user_id)
        if not user:
            raise ValueError("User fetch returned None.")
    except discord.NotFound:
        await ctx.send(f"❌ User ID `{user_id}` not found.")
        await log_audit(ctx.author, f"❌ Failed DM: Invalid user ID `{user_id}`.")
        return
    except Exception as e:
        await ctx.send(f"⚠️ Unexpected error: {str(e)}")
        await log_audit(ctx.author, f"⚠️ Exception in DM: {str(e)}")
        return

    file_links = [attachment.url for attachment in ctx.message.attachments]

    dm_content_parts = [message] if message else []
    if file_links:
        links_formatted = "\n".join(file_links)
        dm_content_parts.append(f"📎 **Attachments:**\n{links_formatted}")
    dm_content = "\n\n".join(dm_content_parts) if dm_content_parts else "(No text)"

    try:
        await user.send(content=dm_content)
        await ctx.send(f'✅ DM sent anonymously to {user.display_name}.')

        thread = await get_or_create_dm_thread(user)
        await thread.send(f"📤 **Sent to {user}**:\n{dm_content}")
    except discord.Forbidden:
        await ctx.send('❌ Cannot DM user (Privacy Settings).')
        await log_audit(ctx.author, f"❌ Failed DM: Recipient: {user} (Privacy settings).")


@bot.command()
async def roll(ctx, *, dice: str):
    dice_pattern = r'(?:(\d*)d)?(\d+)([+-]\d+)?'
    match = re.fullmatch(dice_pattern, dice.replace(' ', ''))

    if not match:
        await ctx.send('🎲 Format: `!roll XdY+Z` (Example: `!roll 2d6+3`)')
        await log_audit(ctx.author, f"❌ Invalid dice roll: `{dice}`")
        return

    dice_count, dice_sides, modifier = match.groups()
    dice_count = int(dice_count) if dice_count else 1
    dice_sides = int(dice_sides)
    modifier = int(modifier) if modifier else 0

    rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
    total = sum(rolls) + modifier

    rolls_detailed = ', '.join(f'**{roll}**' for roll in rolls)
    modifier_text = f" {'+' if modifier >= 0 else '-'} {abs(modifier)}" if modifier else ""

    result_message = (
        f'🎲 You rolled: {dice_count}d{dice_sides}{modifier_text}\n'
        f'**Results:** {rolls_detailed}\n'
        f'**Total:** {total}'
    )

    await ctx.send(result_message)


@bot.command()
async def helpme(ctx):
    embed = discord.Embed(title="🤖 NCRP Bot Help", color=discord.Color.green())
    embed.add_field(name="!post #channel [message]", value="Anonymous post (Fixers only).", inline=False)
    embed.add_field(name="!dm user_id [message]", value="Anonymous DM by user ID (Fixers only).", inline=False)
    embed.add_field(name="!roll [XdY+Z]", value="Roll dice. Example: `!roll 2d6+3`.", inline=False)
    embed.add_field(name="!helpme", value="Show this help message.", inline=False)
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


async def log_audit(user, action_desc):
    audit_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if audit_channel:
        embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Action", value=action_desc, inline=False)
        await audit_channel.send(embed=embed)
    print(f"[AUDIT] {user}: {action_desc}")


async def get_or_create_dm_thread(user: discord.User):
    log_channel = bot.get_channel(DM_INBOX_CHANNEL_ID)
    user_id = str(user.id)
    print(f"[THREAD] Checking thread for {user.name} ({user_id})")

    if user_id in dm_threads:
        try:
            thread = await bot.fetch_channel(dm_threads[user_id])
            print(f"[THREAD] Reusing thread {thread.id}")
            return thread
        except discord.NotFound:
            print("[THREAD] Thread not found, creating new one.")

    thread_name = f"{user.name}-{user.id}".replace(" ", "-").lower()[:100]
    if isinstance(log_channel, discord.TextChannel):
        thread = await log_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            reason=f"Logging DM history for {user.name} ({user.id})"
        )
    elif isinstance(log_channel, discord.ForumChannel):
        created = await log_channel.create_thread(
            name=thread_name,
            content="📥 Creating DM thread...",
            reason=f"Logging DM history for {user.name} ({user.id})"
        )
        thread = created.thread
    else:
        raise RuntimeError("DM inbox must be a TextChannel or ForumChannel.")

    dm_threads[user_id] = thread.id
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(dm_threads, f)

    print(f"[THREAD] Created thread {thread.name} ({thread.id})")
    return thread


@bot.event
async def on_ready():
    print(f'🚀 Logged in as {bot.user.name}!')


@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        print(f"[DM RECEIVED] From {message.author}: {message.content}")
        try:
            thread = await get_or_create_dm_thread(message.author)
            full_content = message.content or "*(No text content)*"
            chunks = [full_content[i:i + 1024] for i in range(0, len(full_content), 1024)]
            for chunk in chunks:
                await thread.send(f"📥 **Received from {message.author.display_name}**:\n{chunk}")
            for attachment in message.attachments:
                await thread.send(f"📎 Received attachment: {attachment.url}")
        except Exception as e:
            print(f"[ERROR] DM logging failed: {e}")


@bot.command()
@is_fixer()
async def backfill_dm_logs(ctx, channel_id: int):
    source_channel = bot.get_channel(channel_id)
    print(f"[BACKFILL] Source: {channel_id} → Target: {DM_INBOX_CHANNEL_ID}")

    if not source_channel or not hasattr(source_channel, "history"):
        await ctx.send("❌ Cannot read from that channel.")
        return

    messages = [msg async for msg in source_channel.history(limit=500, oldest_first=True)]
    print(f"[BACKFILL] Loaded {len(messages)} messages.")

    new_seen_ids = set()
    backfilled = 0

    for msg in messages:
        if msg.id in seen_msg_ids:
            continue

        content = msg.content.strip()
        print(f"[BACKFILL] Checking: {msg.author.display_name}: {content[:60]}")

        # Handle !dm commands
        if content.startswith("!dm"):
            match = re.search(r"(\d{17,20})", content)
            if match:
                user_id = match.group(1)
                try:
                    user = await bot.fetch_user(int(user_id))
                    thread = await get_or_create_dm_thread(user)
                    await thread.send(f"📤 **Backfilled message to {user.name} ({user.id})**:\n{content}")
                    dm_threads[user_id] = thread.id
                    with open(THREAD_MAP_FILE, "w") as f:
                        json.dump(dm_threads, f)
                    new_seen_ids.add(msg.id)
                    backfilled += 1
                except Exception as e:
                    print(f"[ERROR] Failed to backfill TO {user_id}: {e}")
            continue

        # Handle embed-style replies from users
        if msg.embeds:
            embed = msg.embeds[0]
            sender_field = next((f for f in embed.fields if f.name.lower() == "sender"), None)
            content_field = next((f for f in embed.fields if f.name.lower() == "content"), None)

            if sender_field and content_field:
                sender_match = re.search(r"\((\d{17,20})\)", sender_field.value)
                if sender_match:
                    user_id = sender_match.group(1)
                    try:
                        user = await bot.fetch_user(int(user_id))
                        thread = await get_or_create_dm_thread(user)
                        combined = f"📥 **Backfilled incoming reply from {user.name} ({user.id})**:\n{content_field.value}"
                        if embed.description:
                            combined += f"\n\n{embed.description}"
                        await thread.send(combined)
                        dm_threads[user_id] = thread.id
                        with open(THREAD_MAP_FILE, "w") as f:
                            json.dump(dm_threads, f)
                        new_seen_ids.add(msg.id)
                        backfilled += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to backfill FROM {user_id}: {e}")
            continue

    # Save updated seen message IDs
    if new_seen_ids:
        try:
            seen_msg_ids.update(new_seen_ids)
            with open(SEEN_MSG_ID_FILE, "w") as f:
                json.dump(list(seen_msg_ids), f)
            print(f"[BACKFILL] Saved {len(new_seen_ids)} new seen message IDs.")
        except Exception as e:
            print(f"[ERROR] Failed to save seen IDs: {e}")

    await ctx.send(f"✅ Backfill complete. Routed {backfilled} new messages.")
    print(f"[DONE] Routed {backfilled} messages.")


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


@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: str = None):
    await ctx.send("🚦 Starting rent collection...")

    LAST_RENT_FILE = "last_rent.json"
    OPEN_LOG_FILE = "business_open_log.json"

    EVICTION_CHANNEL_ID = 1379611043843539004
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)

    # Rotate open log
    if Path(OPEN_LOG_FILE).exists():
        with open(OPEN_LOG_FILE, "r") as f:
            business_open_log = json.load(f)
        month = datetime.utcnow().month
        year = datetime.utcnow().year
        backup_name = f"open_history_{month_name[month]}_{year}.json"
        Path(OPEN_LOG_FILE).rename(backup_name)
    else:
        business_open_log = {}

    with open(OPEN_LOG_FILE, "w") as f:
        json.dump({}, f)

    # Skip cooldown if running a targeted collection
    if not target_user and os.path.exists(LAST_RENT_FILE):
        with open(LAST_RENT_FILE, "r") as f:
            data = json.load(f)
            last_run = datetime.fromisoformat(data["last_run"])
            if datetime.utcnow() - last_run < timedelta(days=30):
                await ctx.send("⚠️ Rent already collected in the last 30 days.")
                return

    if not target_user:
        with open(LAST_RENT_FILE, "w") as f:
            json.dump({"last_run": datetime.utcnow().isoformat()}, f)

    role_costs = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Business Tier 1": 2000,
        "Business Tier 2": 3500,
        "Business Tier 3": 5000,
        "Business Tier 0": 0,
    }

    business_roles = {
        "Business Tier 0", "Business Tier 1", "Business Tier 2", "Business Tier 3"
    }

    members_to_process = []

    for member in ctx.guild.members:
        member_roles = [r.name for r in member.roles]
        matching_roles = [r for r in member_roles if r in role_costs]

        if target_user:
            if target_user.lower() in member.name.lower() or target_user.lower() in member.display_name.lower():
                if matching_roles:
                    members_to_process = [member]
                    break
        else:
            if matching_roles:
                members_to_process.append(member)

    if not members_to_process:
        await ctx.send("❌ No matching members found.")
        return

    for member in members_to_process:
        try:
            role_names = [r.name for r in member.roles]
            applicable_roles = [r for r in role_names if r in role_costs]

            log = [f"🔍 **Working on:** <@{member.id}>"]
            log.append(f"🧾 Raw role names: {role_names}")
            log.append(f"🏷️ Detected roles: {', '.join(applicable_roles)}")

            balance_data = await get_balance(member.id)
            if not balance_data:
                log.append("⚠️ Could not fetch balance from UnbelievaBoat.")
                await ctx.send("\n".join(log))
                continue

            cash = balance_data["cash"]
            bank = balance_data["bank"]
            total = balance_data["total"]

            log.append(f"💵 Current balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

            total_rent = 0
            total_income = 0
            changes = []

            for role in applicable_roles:
                rent = role_costs[role]
                log.append(f"🔎 Role **{role}** → Rent: ${rent}")

                # Business passive income scaling
                if role in business_roles:
                    opens = business_open_log.get(str(member.id), [])
                    opens_this_month = [
                        ts for ts in opens
                        if datetime.fromisoformat(ts).month == datetime.utcnow().month and
                           datetime.fromisoformat(ts).year == datetime.utcnow().year
                    ]
                    open_count = min(len(opens_this_month), 4)
                    open_percent = {0: 0, 1: 0.25, 2: 0.4, 3: 0.6, 4: 0.8}[open_count]

                    base = 500 if role == "Business Tier 0" else rent
                    income = int(base * open_percent)
                    total_income += income
                    changes.append(f"**{role}** → +${income} passive income ({open_count} opens)")

                if rent > 0:
                    total_rent += rent
                    changes.append(f"**{role}** → -${rent} rent")

            log.append("🔁 **Changes this cycle:**")
            log.extend([f"   • {c}" for c in changes])

            # Apply passive income
            if total_income > 0:
                income_success = await update_balance(member.id, {"cash": total_income}, reason="Passive income")
                if income_success:
                    log.append(f"➕ Added ${total_income} passive income.")
                    balance_data = await get_balance(member.id)
                    cash = balance_data["cash"]
                    bank = balance_data["bank"]
                    total = balance_data["total"]
                else:
                    log.append("❌ Failed to apply passive income.")

            log.append(f"📈 Balance after income — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

            if total < total_rent:
                log.append(f"❌ Cannot pay rent of ${total_rent}. Would result in negative balance.")
                if eviction_channel:
                    await eviction_channel.send(
                        f"🚨 <@{member.id}> — You only have ${total:,}, but your rent this cycle is ${total_rent}.\n"
                        f"You have **7 days** to pay or face eviction. Please top up your balance ASAP."
                    )
                if rent_log_channel:
                    await rent_log_channel.send(
                        f"❌ <@{member.id}> — Rent due: ${total_rent} — **FAILED** (insufficient funds)"
                    )
                log.append("⚠️ Eviction warning sent. Rent not deducted.")
            else:
                # Deduct rent from cash, then bank
                cash_to_deduct = min(cash, total_rent)
                bank_to_deduct = total_rent - cash_to_deduct

                update_payload = {}
                if cash_to_deduct > 0:
                    update_payload["cash"] = -cash_to_deduct
                if bank_to_deduct > 0:
                    update_payload["bank"] = -bank_to_deduct

                log.append(f"🧮 Subtracting ${total_rent} — "
                           f"${cash_to_deduct} from cash, ${bank_to_deduct} from bank...")

                rent_success = await update_balance(member.id, update_payload, reason="Monthly Rent")
                if rent_success:
                    updated_bal = await get_balance(member.id)
                    log.append(f"💸 Rent of ${total_rent} removed successfully.")
                    log.append(f"📊 New balance — Cash: ${updated_bal['cash']:,}, Bank: ${updated_bal['bank']:,}")

                    if rent_log_channel:
                        await rent_log_channel.send(
                            f"✅ <@{member.id}> — Rent paid: ${total_rent} — **Success**"
                        )
                else:
                    log.append("❌ Failed to subtract rent. API call unsuccessful.")
                    if rent_log_channel:
                        await rent_log_channel.send(
                            f"❌ <@{member.id}> — Rent of ${total_rent} failed to deduct. Manual review required."
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
    user_id = str(ctx.author.id)
    now = datetime.utcnow()
    now_str = now.isoformat()

    # Load or initialize
    if Path(OPEN_LOG_FILE).exists():
        with open(OPEN_LOG_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Get this user's log
    all_opens = data.get(user_id, [])
    this_month_opens = [
        datetime.fromisoformat(ts)
        for ts in all_opens
        if datetime.fromisoformat(ts).month == now.month and datetime.fromisoformat(ts).year == now.year
    ]

    if len(this_month_opens) >= 4:
        await ctx.send("❌ You’ve already used all 4 business posts for this month.")
        return

    if this_month_opens:
        last_post = max(this_month_opens)
        if (now - last_post).days < 6:
            next_allowed = last_post + timedelta(days=6)
            await ctx.send(
                f"⏳ You must wait until **{next_allowed.strftime('%A %b %d')}** to log another opening."
            )
            return

    # Log it
    all_opens.append(now_str)
    data[user_id] = all_opens
    with open(OPEN_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    await ctx.send(f"✅ Business opening logged! ({len(this_month_opens) + 1}/4 this month)")


keep_alive()
bot.run(TOKEN)