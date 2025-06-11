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
        except Exception as e:
            print(f"[THREAD] Failed to create forum thread: {e}")
            raise

    else:
        raise RuntimeError("DM inbox must be a TextChannel or ForumChannel.")

    dm_threads[user_id] = thread.id
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(dm_threads, f)

    print(f"[THREAD] Created thread {thread.name} ({thread.id})")
    return thread
