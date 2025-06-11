import discord
from discord.ext import commands
import random
import re

TOKEN = "MTIxMzI1MjEwNjA2NTAyMzAzNw.GDvA6e.HrYYp-mdMJYpX4VGXI-p7-UbEpf93gNbQNmQqI"
AUDIT_LOG_CHANNEL_ID = 1320924575286169625
FIXER_ROLE_NAME = "@everyone"
DM_INBOX_CHANNEL_ID = 1320924575286169625  # Replace with your DM inbox channel ID

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.dm_messages = True  # Enable DM handling

bot = commands.Bot(command_prefix='!', intents=intents)

# Check if user has fixer role
def is_fixer():
    async def predicate(ctx):
        return discord.utils.get(ctx.author.roles, name=FIXER_ROLE_NAME) is not None
    return commands.check(predicate)

# Audit logging function
async def log_audit(user, action_desc):
    audit_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if audit_channel:
        embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Action", value=action_desc, inline=False)
        await audit_channel.send(embed=embed)

# On Ready event
@bot.event
async def on_ready():
    print(f'🚀 Logged in as {bot.user.name}!')

# Handle incoming DM messages to bot
@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        dm_inbox = bot.get_channel(DM_INBOX_CHANNEL_ID)
        if dm_inbox:
            embed = discord.Embed(title="📥 New DM Received", color=discord.Color.orange())
            embed.add_field(name="Sender", value=f"{message.author} ({message.author.id})", inline=False)
            embed.add_field(name="Content", value=message.content, inline=False)
            await dm_inbox.send(embed=embed)
            await log_audit(message.author, f"📥 **DM received:**\n{message.content}")

# Reply anonymously to DM (Fixers Only)
@bot.command()
@is_fixer()
async def reply(ctx, user: discord.User, *, message):
    try:
        await user.send(message)
        await ctx.message.delete()
        confirm = await ctx.send(f'✅ Reply sent anonymously to {user.display_name}.', delete_after=5)
        await log_audit(ctx.author, f"📤 **Anonymous reply sent:**\nRecipient: {user} ({user.id})\nMessage: {message}")
    except discord.Forbidden:
        await ctx.send('❌ Cannot DM that user (Privacy Settings).', delete_after=5)
        await log_audit(ctx.author, f"❌ **Failed anonymous reply:**\nRecipient: {user} ({user.id})\nReason: Privacy settings.")

# Anonymous channel post (Fixers Only)
@bot.command()
@is_fixer()
async def post(ctx, channel: discord.TextChannel, *, message):
    await channel.send(message)
    await ctx.message.delete()
    await log_audit(ctx.author, f"📢 **Anonymous channel post:**\nChannel: {channel.mention}\nMessage: {message}")

# Anonymous DM (Fixers Only)
@bot.command()
@is_fixer()
async def dm(ctx, user: discord.User, *, message):
    try:
        await user.send(message)
        await ctx.message.delete()
        await ctx.send(f'✅ DM sent anonymously to {user.display_name}.', delete_after=5)
        await log_audit(ctx.author, f"📤 **Anonymous DM sent:**\nRecipient: {user} ({user.id})\nMessage: {message}")
    except discord.Forbidden:
        await ctx.send('❌ Cannot DM that user (Privacy Settings).', delete_after=5)
        await log_audit(ctx.author, f"❌ **Failed anonymous DM:**\nRecipient: {user} ({user.id})\nReason: Privacy settings.")

# Dice rolling (Everyone)
@bot.command()
async def roll(ctx, *, dice: str):
    dice_pattern = r'(\d+)d(\d+)([+-]\d+)?'
    match = re.fullmatch(dice_pattern, dice.replace(' ', ''))
    if not match:
        await ctx.send('🎲 Use format: `!roll XdY+Z` (Example: `!roll 2d6+3`)')
        await log_audit(ctx.author, f"❌ **Invalid dice roll attempt:** `{dice}`")
        return

    dice_count, dice_sides, modifier = match.groups()
    dice_count, dice_sides = int(dice_count), int(dice_sides)
    modifier = int(modifier) if modifier else 0

    rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
    total = sum(rolls) + modifier

    rolls_formatted = ' + '.join(map(str, rolls))
    mod_text = f" {'+' if modifier >= 0 else '-'} {abs(modifier)}" if modifier else ''
    result_message = f'🎲 **Result:** ({rolls_formatted}){mod_text} = **{total}**'

    await ctx.send(result_message)
    await log_audit(ctx.author, f"🎲 **Dice rolled:** `{dice}`\nResult: {result_message}")

# Help command
@bot.command()
async def helpme(ctx):
    embed = discord.Embed(title="🤖 NCRP Bot Help", color=discord.Color.green())
    embed.add_field(name="!post #channel [message] (Fixers Only)", value="Post anonymously to a channel.", inline=False)
    embed.add_field(name="!dm @user [message] (Fixers Only)", value="Send anonymous DM to user.", inline=False)
    embed.add_field(name="!reply @user [message] (Fixers Only)", value="Reply anonymously to user who DM'd bot.", inline=False)
    embed.add_field(name="!roll [XdY+Z]", value="Roll dice (e.g., `!roll 2d6+3`).", inline=False)
    embed.add_field(name="!helpme", value="Show this help message.", inline=False)
    await ctx.send(embed=embed)
    await log_audit(ctx.author, "**Help command used**")

# Error handling
@post.error
@dm.error
@reply.error
async def fixer_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission for this command.", delete_after=5)
        await log_audit(ctx.author, f"❌ **Permission Denied:** {ctx.message.content}")
    else:
        await ctx.send(f"⚠️ Error: {str(error)}", delete_after=10)
        await log_audit(ctx.author, f"⚠️ **Error:** {str(error)}")

bot.run(TOKEN)