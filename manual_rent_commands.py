
@bot.command()
@commands.has_permissions(administrator=True)
async def collect_housing(ctx, user: discord.Member):
    """Manually collect housing rent from a single user"""
    log = [f"🏠 Manual Housing Rent Collection for <@{user.id}>"]
    role_costs_housing = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000
    }
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    EVICTION_CHANNEL_ID = 1379611043843539004
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)

    role_names = [r.name for r in user.roles]
    log.append(f"🧾 Roles: {role_names}")

    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = cash + bank
    log.append(f"💵 Balance — Cash: ${cash}, Bank: ${bank}, Total: ${total}")

    cash, bank = await process_housing_rent(user, role_names, cash, bank, log, rent_log_channel, eviction_channel, role_costs_housing)

    final = await get_balance(user.id)
    if final:
        log.append(f"📊 Final balance — Cash: ${final['cash']}, Bank: ${final['bank']}, Total: ${final['cash'] + final['bank']}")
    await ctx.send("\n".join(log))


@bot.command()
@commands.has_permissions(administrator=True)
async def collect_business(ctx, user: discord.Member):
    """Manually collect business rent from a single user"""
    log = [f"🏢 Manual Business Rent Collection for <@{user.id}>"]
    role_costs_business = {
        "Business Tier 0": 0,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000
    }
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    EVICTION_CHANNEL_ID = 1379611043843539004
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)

    role_names = [r.name for r in user.roles]
    log.append(f"🧾 Roles: {role_names}")

    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = cash + bank
    log.append(f"💵 Balance — Cash: ${cash}, Bank: ${bank}, Total: ${total}")

    cash, bank = await process_business_rent(user, role_names, cash, bank, log, rent_log_channel, eviction_channel, role_costs_business)

    final = await get_balance(user.id)
    if final:
        log.append(f"📊 Final balance — Cash: ${final['cash']}, Bank: ${final['bank']}, Total: ${final['cash'] + final['bank']}")
    await ctx.send("\n".join(log))


@bot.command()
@commands.has_permissions(administrator=True)
async def collect_trauma(ctx, user: discord.Member):
    """Manually collect Trauma Team subscription"""
    log = [f"💊 Manual Trauma Team Subscription Processing for <@{user.id}>"]
    balance_data = await get_balance(user.id)
    if not balance_data:
        log.append("❌ Could not fetch balance.")
        await ctx.send("\n".join(log))
        return

    cash = balance_data["cash"]
    bank = balance_data["bank"]
    total = cash + bank
    log.append(f"💵 Balance — Cash: ${cash}, Bank: ${bank}, Total: ${total}")

    await process_trauma_team_payment(user, cash, bank, log)
    final = await get_balance(user.id)
    if final:
        log.append(f"📊 Final balance — Cash: ${final['cash']}, Bank: ${final['bank']}, Total: ${final['cash'] + final['bank']}")
    await ctx.send("\n".join(log))
