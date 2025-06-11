# NCRP Combined Bot — Cleaned and Merged
# =====================================
# This script merges DM logging, anonymous messaging, and rent collection.

import discord
from discord.ext import commands
import random
import re
import json
import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from pathlib import Path
from calendar import month_name
from typing import Optional
from typing import cast

# --- Configuration ---
TOKEN = "MTIxMzI1MjEwNjA2NTAyMzAzNw.GDvA6e.HrYYp-mdMJYpX4VGXI-p7-UbEpf93gNbQNmQqI"
AUDIT_LOG_CHANNEL_ID = 1349160856688267285
FIXER_ROLE_NAME = "Fixer"
DM_INBOX_CHANNEL_ID = 1379222007513874523
UNBELIEVABOAT_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2MzUyNzA3NTg2Mjk0IiwiaWF0IjoxNzQ4OTk0MTg2fQ.d1IYySps6p1MoLAp98-b46YukWS4vCVuSLyo-QTfEVI"
GUILD_ID = "1348601552083882108"

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

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask('')

# Keep-alive server for uptime
@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=5000)


def keep_alive():
    t = Thread(target=run)
    t.start()
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")


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
        return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None
    return commands.check(predicate)

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

# --- DM Thread Handling ---

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
        # Discord.py 2.x method to create a post in a forum
        try:
            created = await log_channel.create_thread(
                name=thread_name,
                content="📥 DM started with this user.",
                reason=f"Logging DM history for {user.name} ({user.id})",
                applied_tags=[]  # optional: include tag IDs here if your forum uses required tags
            )
            thread = created
            if hasattr(thread, "thread"):
                thread = thread.thread  # unwrap the ThreadWithMessage
        except Exception as e:
            print(f"[THREAD] Failed to create forum thread: {e}")
            raise

    else:
        raise RuntimeError("DM inbox must be a TextChannel or ForumChannel.")

    thread = cast(discord.Thread, thread)
    dm_threads[user_id] = thread.id
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(dm_threads, f)

    print(f"[THREAD] Created thread {thread.name} ({thread.id})")
    return thread


# --- Event Handlers ---

@bot.event
async def on_ready():
    if bot.user:
        print(f"🚀 Logged in as {bot.user.name}!")
    else:
        print("⚠️ Logged in, but bot.user is None (unexpected).")

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

            if isinstance(thread, (discord.Thread, discord.TextChannel)):
                print(f"[DEBUG] Thread archived: {getattr(thread, 'archived', False)}, locked: {getattr(thread, 'locked', False)}")

                # Unarchive if needed
                if getattr(thread, 'archived', False):
                    try:
                        await thread.edit(archived=False, locked=False) # type: ignore[attr-defined]
                        print("[DEBUG] Thread unarchived successfully.")
                    except Exception as e:
                        print(f"[ERROR] Failed to unarchive thread: {e}")

                for chunk in chunks:
                    if chunk.strip().startswith("!"):
                        print(f"[DEBUG] Skipped logging command message: {chunk}")
                        continue  # Let the actual command (like !roll) handle logging the result

                    try:
                        await thread.send(f"📥 **Received from {message.author.display_name}**:\n{chunk}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send chunk to thread: {e}")

                for attachment in message.attachments:
                    try:
                        await thread.send(f"📎 Received attachment: {attachment.url}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send attachment: {e}")

            else:
                print(f"[ERROR] Thread is of incompatible type: {type(thread)}")

        except Exception as e:
            print(f"[ERROR] DM logging failed: {e}")


# --- Commands ---

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
async def dm(ctx, user: discord.User, *, message=None):

    try:
        # already resolved by the command parser
        pass
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

    dm_content_parts = [message] if message else []
    if file_links:
        links_formatted = "\n".join(file_links)
        dm_content_parts.append(f"📎 **Attachments:**\n{links_formatted}")
    dm_content = "\n\n".join(dm_content_parts) if dm_content_parts else "(No text)"

    # Check if message is a bot command
    if message and message.strip().startswith("!"):
        command_text = message.strip()
        if command_text.startswith("!roll"):
            dice = command_text[len("!roll"):].strip()
            channel = await user.create_dm()
            await loggable_roll(user, channel, dice, original_sender=ctx.author)
            return

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

async def loggable_roll(author, channel, dice: str, *, original_sender=None):
    dice_pattern = r'(?:(\d*)d)?(\d+)([+-]\d+)?'
    match = re.fullmatch(dice_pattern, dice.replace(' ', ''))

    if not match:
        await channel.send('🎲 Format: `!roll XdY+Z` (Example: `!roll 2d6+3`)')
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

    await channel.send(result_message)

    # Thread logging
    thread = await get_or_create_dm_thread(author)
    if isinstance(thread, (discord.Thread, discord.TextChannel)):
        if original_sender:
            await thread.send(
                f"📤 **Sent to {author.display_name} by {original_sender.display_name}:** `!roll {dice}`\n\n{result_message}"
            )
        else:
            await thread.send(
                f"📥 **{author.display_name} used:** `!roll {dice}`\n\n{result_message}"
            )


@bot.command()
async def roll(ctx, *, dice: str):
    await loggable_roll(ctx.author, ctx.channel, dice)

@bot.command(name="helpme")
async def helpme(ctx):
    embed = discord.Embed(
        title="🧠 NCRP Combined Bot — Help Menu",
        description="Use `!command` followed by the required arguments. This bot handles anonymous messaging, rent systems, and RP tooling.",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="📨 Messaging (Fixers only)",
        value=(
            "`!post [channel/thread] [message]`\n"
            "→ Anonymously post a message to any visible channel or thread.\n"
            "→ Attach video/picture/files to your message. They will be sent and also logged.\n"
            "`!dm [@user] [message]`\n"
            "→ Anonymously send a DM. If the message is a bot command (like `!roll`), the command will execute in the user's DM and log the result.\n"
            "→ Attach video/picture/files to your message. They will be sent and also logged.\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🎲 RP Utilities",
        value=(
            "`!roll [XdY+Z]`\n"
            "→ Roll dice in any channel or DM. Rolls inside DMs are logged to your private thread."
        ),
        inline=False
    )

    embed.add_field(
        name="💸 Rent & Business (Admins & Shop Owners)",
        value=(
            "`!collect_rent [@user] (optional)`\n"
            "→ Deduct rent from everyone or a specific user. Checks cash/bank balance and logs to eviction and rent channels. Can only be run once every 30 days.\n"
            "`!open_shop`\n"
            "→ Logs a business opening. Can only be used once per Sunday (UTC), up to 4 total times per month. Using this command gives you passive income based on the number of times you've opened your shop this month."
        ),
        inline=False
    )

    embed.add_field(
        name="📝 Notes & Behavior",
        value=(
            "• All messages and commands sent via `!dm` are logged in a private forum thread tied to that user.\n"
            "• Bot auto-unarchives threads if needed to log content.\n"
            "• Messages starting with `!` in DMs are treated as commands and will not be logged directly — only their results are.\n"
            "• All audit logs go to a dedicated channel and include who issued commands."
        ),
        inline=False
    )

    embed.set_footer(text="Bot by MedusaCascade | v1.0 — Use responsibly.")

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


# --- Rent Collection Command ---

@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: Optional[discord.Member] = None):

    await ctx.send("🚦 Starting rent collection...")

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

    # Skip cooldown if targeted
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
        "Housing Tier 3": 3000,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
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
            if member.id == target_user.id:
                if matching_roles:
                    members_to_process = [member]
                    break
                else:
                    await ctx.send(f"❎ Skipped <@{member.id}> — no rent-related roles.")
                    return
            continue

        # Not targeting a specific user
        if not matching_roles:
            await ctx.send(f"❎ Skipped <@{member.id}> — no rent-related roles.")
            continue

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

            if total_income > 0:
                income_success = await update_balance(member.id, {"cash": total_income}, reason="Passive income")
                if income_success:
                    log.append(f"➕ Added ${total_income} passive income.")
                    balance_data = await get_balance(member.id)
                    if balance_data:
                        cash = balance_data["cash"]
                        bank = balance_data["bank"]
                        total = balance_data["total"]
                    else:
                        log.append("❌ Failed to fetch updated balance after passive income.")
                        continue  # or return / skip the rest of this loop
                else:
                    log.append("❌ Failed to apply passive income.")

            log.append(f"📈 Balance after income — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

            if total < total_rent:
                log.append(f"❌ Cannot pay rent of ${total_rent}. Would result in negative balance.")
                if eviction_channel:
                    await eviction_channel.send(
                        f"🚨 <@{member.id}> — You only have ${total:,}, but your rent this cycle is ${total_rent}."
                        f"You have **7 days** to pay or face eviction. Please top up your balance ASAP."
                    )
                if rent_log_channel:
                    await rent_log_channel.send(
                        f"❌ <@{member.id}> — Rent due: ${total_rent} — **FAILED** (insufficient funds)"
                    )
                log.append("⚠️ Eviction warning sent. Rent not deducted.")
            else:
                cash_to_deduct = min(cash, total_rent)
                bank_to_deduct = total_rent - cash_to_deduct

                update_payload = {}
                if cash_to_deduct > 0:
                    update_payload["cash"] = -cash_to_deduct
                if bank_to_deduct > 0:
                    update_payload["bank"] = -bank_to_deduct

                log.append(f"🧮 Subtracting ${total_rent} — ${cash_to_deduct} from cash, ${bank_to_deduct} from bank...")

                rent_success = await update_balance(member.id, update_payload, reason="Monthly Rent")
                if rent_success:
                    updated_bal = await get_balance(member.id)
                    if updated_bal:
                        log.append(f"📊 New balance — Cash: ${updated_bal['cash']:,}, Bank: ${updated_bal['bank']:,}")
                    else:
                        log.append("⚠️ Rent removed, but failed to fetch updated balance.")
                    if rent_log_channel:
                        await rent_log_channel.send(
                            f"✅ <@{member.id}> — Rent paid: ${total_rent} — **Success**"
                        )
                else:
                    log.append("❌ Failed to subtract rent.")
                    if rent_log_channel:
                        await rent_log_channel.send(
                            f"❌ <@{member.id}> — Rent of ${total_rent} failed. Manual review needed."
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

    await ctx.send(f"✅ Business opening logged! ({len(this_month_opens)+1}/4 this month)")


if __name__ == "__main__":
    keep_alive()
    asyncio.get_event_loop().run_forever()
