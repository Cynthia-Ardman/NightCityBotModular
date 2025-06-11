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
from typing import Optional, List
from typing import cast

# --- Configuration ---
TOKEN = "MTM3OTUyNzc4OTQzNDI0MTExNA.GTC6-z.HzfIqRu9Zqb5I2QTHGNPEL3M7haCEKPTghH458"
AUDIT_LOG_CHANNEL_ID = 1379611043843539004
FIXER_ROLE_NAME = "Fixer"
DM_INBOX_CHANNEL_ID = 1379611043843539004
UNBELIEVABOAT_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2NDQ1MTE2NDkyMDI2IiwiaWF0IjoxNzQ5MTc3NjMxfQ.Hgn611UEILLF1ogVDxlQpHivT89ArroJnAliouHE7P4"
GUILD_ID = "1320924574761746473"

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
                print(
                    f"[DEBUG] Thread archived: {getattr(thread, 'archived', False)}, locked: {getattr(thread, 'locked', False)}")

                # Unarchive if needed
                if getattr(thread, 'archived', False):
                    try:
                        await thread.edit(archived=False, locked=False)  # type: ignore[attr-defined]
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


# --- Trauma Team Subscription Processing ---

TRAUMA_ROLE_COSTS = {
    "Trauma Team Silver": 1000,
    "Trauma Team Gold": 2000,
    "Trauma Team Plat": 4000,
    "Trauma Team Diamond": 10000
}

TRAUMA_TEAM_ROLE_ID = 1380341033124102254
TRAUMA_FORUM_CHANNEL_ID = 1366880900599517214


async def process_trauma_team_payment(member, cash, bank, log: Optional[List[str]] = None):
    trauma_channel = bot.get_channel(TRAUMA_FORUM_CHANNEL_ID)
    if not isinstance(trauma_channel, discord.ForumChannel):
        if log is not None:
            log.append("⚠️ TT forum channel not found.")
        return

    trauma_cost = 0
    trauma_role = None
    for role in member.roles:
        if role.name in TRAUMA_ROLE_COSTS:
            trauma_cost = TRAUMA_ROLE_COSTS[role.name]
            trauma_role = role.name
            break

    if not trauma_role:
        return  # No trauma tier, skip

    # Mention role and compute new balances
    total_balance = cash + bank
    if log is not None:
        log.append(f"🔎 {trauma_role} → Subscription: ${trauma_cost}")
        log.append("💊 Processing Trauma Team subscription...")

    # Locate thread
    thread_name_suffix = f"- {member.id}"
    target_thread = None
    for thread in trauma_channel.threads:
        if thread.name.endswith(thread_name_suffix):
            target_thread = thread
            break

    if not target_thread:
        if log is not None:
            log.append(f"⚠️ Could not locate Trauma Team thread for <@{member.id}>")
        return

    if total_balance < trauma_cost:
        mention = f"<@&{TRAUMA_TEAM_ROLE_ID}>"
        if log is not None:
            log.append(f"❌ Cannot pay {trauma_role} Subscription of ${trauma_cost}. Would result in negative balance.")
        if log is not None:
            log.append(
                "⚠️ Subscription cancellation notice sent to user's #tt-plans-payment thread, Trauma team notified.")
        await target_thread.send(
            f"❌ {trauma_role} Payment by <@{member.id}> for`${trauma_cost}`, **FAILED** (insufficient funds). ❌"
            f"\n## {mention} This customers subscripton is now SUSPENDED."
        )
        return

    # Deduct
    update_payload = {}
    cash_used = min(cash, trauma_cost)
    bank_used = trauma_cost - cash_used

    if cash_used > 0:
        update_payload["cash"] = -cash_used
    if bank_used > 0:
        update_payload["bank"] = -bank_used
    if log is not None:
        log.append(
            f"🧮 Subtracting Trauma Team Subscription ${trauma_cost} — ${cash_used} from cash, ${bank_used} from bank...")

    success = await update_balance(member.id, update_payload, reason="Trauma Team Subscription")
    if success:
        if log is not None:
            log.append("✅ Trauma Team subscription payment completed. Notice Sent to user's #tt-plans-payment thread.")
            await target_thread.send(
                f"✅ **Payment Successful** for <@{member.id}> — paid `${trauma_cost}` for **{trauma_role}** coverage."
            )
    else:
        if log is not None:
            log.append("⚠️ Failed to apply Trauma Team payment, manual review needed.")
            await target_thread.send(
                f"⚠️ **Deduction failed** despite available funds for <@{member.id}>."
            )


async def apply_passive_income(member, applicable_roles, business_open_log, log: List[str]):
    total_income = 0
    for role in applicable_roles:
        if role in business_open_log:
            opens = business_open_log.get(str(member.id), [])
            opens_this_month = [
                ts for ts in opens
                if datetime.fromisoformat(ts).month == datetime.utcnow().month and
                   datetime.fromisoformat(ts).year == datetime.utcnow().year
            ]
            open_count = min(len(opens_this_month), 4)
            open_percent = {0: 0, 1: 0.25, 2: 0.4, 3: 0.6, 4: 0.8}[open_count]
            income = int(500 * open_percent)
            total_income += income
            log.append(f"💰 Passive income for {role}: ${income} ({open_count} opens)")

    if total_income > 0:
        success = await update_balance(member.id, {"cash": total_income}, reason="Passive income")
        if success:
            updated = await get_balance(member.id)
            log.append(f"➕ Added ${total_income} passive income.")
            if updated:
                return updated["cash"], updated["bank"]
            else:
                log.append("❌ Failed to fetch updated balance after applying passive income.")
                return None, None
        else:
            log.append("❌ Failed to apply passive income.")
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

    total = cash + bank
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
        log.append(f"📈 Balance after housing rent — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash + bank:,}")
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

    total = cash + bank
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
        log.append(f"📈 Balance after business rent — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash + bank:,}")
        log.append("✅ Business Rent collection completed. Notice Sent to #rent")
        if rent_log_channel:
            await rent_log_channel.send(f"✅ <@{member.id}> — Business Rent paid: ${business_total}")
    else:
        log.append("❌ Failed to deduct business rent despite having sufficient funds.")
    return cash, bank


# --- Rent Collection Command ---


@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: Optional[discord.Member] = None):
    await ctx.send("🚦 Starting rent collection...")

    LAST_RENT_FILE = "last_rent.json"
    OPEN_LOG_FILE = "business_open_log.json"

    EVICTION_CHANNEL_ID = 1379611043843539004
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)

    role_costs_housing = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000
    }

    role_costs_business = {
        "Business Tier 0": 0,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000
    }

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

    members_to_process = []
    for member in ctx.guild.members:
        member_roles = [r.name for r in member.roles]
        if target_user:
            if target_user and member.id == target_user.id:
                members_to_process = [member]
                break
        else:
            if any("Tier" in r for r in member_roles):
                members_to_process.append(member)

    if not members_to_process:
        await ctx.send("❌ No matching members found.")
        return

    for member in members_to_process:
        try:
            log = [f"🔍 **Working on:** <@{member.id}>"]
            role_names = [r.name for r in member.roles]
            applicable_roles = [r for r in role_names if "Tier" in r]
            trauma_roles = [r.name for r in member.roles if r.name in TRAUMA_ROLE_COSTS]

            log.append(f"🧾 Raw role names: {role_names}")
            combined_roles = applicable_roles + trauma_roles
            log.append(f"🏷️ Detected roles: {', '.join(combined_roles)}")

            balance_data = await get_balance(member.id)
            if not balance_data:
                log.append("⚠️ Could not fetch balance from UnbelievaBoat.")
                await ctx.send("\n".join(log))
                continue

            cash = balance_data["cash"]
            bank = balance_data["bank"]
            total = cash + bank
            log.append(f"💵 Current balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

            # Apply passive income
            updated_cash, updated_bank = await apply_passive_income(member, applicable_roles, business_open_log, log)
            if updated_cash is not None:
                cash, bank = updated_cash, updated_bank
                total = cash + bank

            # Process housing rent
            pre_housing_cash, pre_housing_bank = cash, bank
            cash, bank = await process_housing_rent(member, applicable_roles, cash, bank, log, rent_log_channel,
                                                    eviction_channel, role_costs_housing)

            if (cash, bank) == (pre_housing_cash, pre_housing_bank):
                log.append(f"⚠️ Housing rent skipped for <@{member.id}> due to insufficient funds.")

            # Process business rent
            pre_business_cash, pre_business_bank = cash, bank
            cash, bank = await process_business_rent(member, applicable_roles, cash, bank, log, rent_log_channel,
                                                     eviction_channel, role_costs_business)

            if (cash, bank) == (pre_business_cash, pre_business_bank):
                log.append(f"⚠️ Business rent skipped for <@{member.id}> due to insufficient funds.")

            # Process trauma team
            await process_trauma_team_payment(member, cash, bank, log)

            final_balance = await get_balance(member.id)
            if final_balance:
                log.append(
                    f"📊 Final balance — Cash: ${final_balance['cash']:,}, Bank: ${final_balance['bank']:,}, Total: ${final_balance['cash'] + final_balance['bank']:,}")
            else:
                log.append("⚠️ Could not confirm final balance.")

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


if __name__ == "__main__":
    keep_alive()
