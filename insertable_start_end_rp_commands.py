
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
    await ctx.send(f"✅ RP channel created: {channel.mention}")


@bot.command()
@commands.has_permissions(administrator=True)
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
