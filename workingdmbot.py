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