import discord
from discord.ext import commands
from typing import Optional
import config
from utils.permissions import is_fixer


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_fixer()
    async def post(self, ctx, destination: str, *, message: Optional[str] = None):
        """Posts a message to the specified channel or thread."""
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
                fake_ctx = await self.bot.get_context(fake_msg)
                fake_ctx.channel = dest_channel
                fake_ctx.author = ctx.author
                setattr(fake_ctx, "original_author", ctx.author)

                await self.bot.invoke(fake_ctx)
                await ctx.send(f"✅ Executed `{command_text}` in {dest_channel.mention}.")
            else:
                await dest_channel.send(content=message, files=files)
                await ctx.send(f"✅ Posted anonymously to {dest_channel.mention}.")
        else:
            await ctx.send("❌ Provide a message or attachment.")

    @commands.command(name="help")
    async def block_help(self, ctx):
        await ctx.send("❌ `!help` is disabled. Use `!helpme` or `!helpfixer` instead.")

    @commands.command(name="helpme")
    async def helpme(self, ctx):
        """Display help for regular users."""
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

        # Add other help fields...

        embed.set_footer(text="Use !roll, pay your rent, stay alive.")
        await ctx.send(embed=embed)

    @commands.command(name="helpfixer")
    async def helpfixer(self, ctx):
        """Display help for fixers."""
        embed = discord.Embed(
            title="🛠️ NCRP Bot — Fixer & Admin Help",
            description="Advanced commands for messaging, RP management, rent, and testing.",
            color=discord.Color.purple()
        )

        # Add fixer help fields...

        embed.set_footer(text="Fixer tools by MedusaCascade | v1.2")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ Unknown command.")
            await self.log_audit(ctx.author, f"❌ Unknown command: {ctx.message.content}")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("❌ Permission denied.")
            await self.log_audit(ctx.author, f"❌ Permission denied: {ctx.message.content}")
        else:
            await ctx.send(f"⚠️ Error: {str(error)}")
            await self.log_audit(ctx.author, f"⚠️ Error: {ctx.message.content} → {str(error)}")

    async def log_audit(self, user, action_desc):
        """Log an audit entry to the audit channel."""
        audit_channel = self.bot.get_channel(config.AUDIT_LOG_CHANNEL_ID)

        if isinstance(audit_channel, discord.TextChannel):
            embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Action", value=action_desc, inline=False)
            await audit_channel.send(embed=embed)
        else:
            print(f"[AUDIT] Skipped: Channel {config.AUDIT_LOG_CHANNEL_ID} is not a TextChannel")

        print(f"[AUDIT] {user}: {action_desc}")