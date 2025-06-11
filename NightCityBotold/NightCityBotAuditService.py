# NightCityBotAuditService.py

import discord
from NightCityBotold.NightCityBotConfig import AUDIT_LOG_CHANNEL_ID

async def setup(bot):
    await bot.add_cog(AuditCog(bot))

async def log_audit(bot, user, action_desc):
    audit_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)

    if isinstance(audit_channel, discord.TextChannel):
        embed = discord.Embed(title="📝 Audit Log", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Action", value=action_desc, inline=False)
        await audit_channel.send(embed=embed)
    else:
        print(f"[AUDIT] Skipped: Channel {AUDIT_LOG_CHANNEL_ID} is not a TextChannel")

    print(f"[AUDIT] {user}: {action_desc}")
