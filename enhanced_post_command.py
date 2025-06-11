
@bot.command()
@is_fixer()
async def post(ctx, destination: str, *, message=None):
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
            # Simulate command in the target channel
            fake_msg = ctx.message
            fake_msg.content = command_text
            fake_ctx = await bot.get_context(fake_msg)
            fake_ctx.channel = dest_channel
            fake_ctx.author = ctx.author
            await bot.invoke(fake_ctx)
            await ctx.send(f"✅ Executed `{command_text}` in {dest_channel.mention}.")
        else:
            await dest_channel.send(content=message, files=files)
            await ctx.send(f"✅ Posted anonymously to {dest_channel.mention}.")
    else:
        await ctx.send("❌ Provide a message or attachment.")
