
@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: Optional[str] = None):
    await ctx.send("🚦 Starting rent collection...")

    LAST_RENT_FILE = "last_rent.json"
    OPEN_LOG_FILE = "business_open_log.json"

    EVICTION_CHANNEL_ID = 1379611043843539004
    RENT_LOG_CHANNEL_ID = 1379615621167321189
    eviction_channel = ctx.guild.get_channel(EVICTION_CHANNEL_ID)
    rent_log_channel = ctx.guild.get_channel(RENT_LOG_CHANNEL_ID)

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
            if target_user.lower() in member.name.lower() or target_user.lower() in member.display_name.lower():
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
            cash, bank = await process_housing_rent(member, applicable_roles, cash, bank, log, rent_log_channel, eviction_channel)

            # Process business rent
            cash, bank = await process_business_rent(member, applicable_roles, cash, bank, log, rent_log_channel, eviction_channel)

            # Process trauma team
            await process_trauma_team_payment(member, cash, bank, log)

            log.append(f"📊 Final balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash + bank:,}")
            await ctx.send("\n".join(log))

        except Exception as e:
            await ctx.send(f"❌ Error processing <@{member.id}>: `{e}`")

    await ctx.send("✅ Rent collection completed.")
