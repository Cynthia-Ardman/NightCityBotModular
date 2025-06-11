
@bot.command()
@commands.has_permissions(administrator=True)
async def collect_rent(ctx, *, target_user: Optional[discord.Member] = None):
    await ctx.send("🚦 Starting rent collection...")

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

    role_costs = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000,
        "Business Tier 0": 0,
    }

    business_roles = {"Business Tier 0", "Business Tier 1", "Business Tier 2", "Business Tier 3"}

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

        if not matching_roles:
            await ctx.send(f"❎ Skipped <@{member.id}> — no rent-related roles.")
            continue

        members_to_process.append(member)

    if not members_to_process:
        await ctx.send("❌ No matching members found.")
        return

    for member in members_to_process:
        try:
            role_names = [r.name for r in member.roles]
            applicable_roles = [r for r in role_names if r in role_costs]
            trauma_roles = [r.name for r in member.roles if r.name in TRAUMA_ROLE_COSTS]

            log = [f"🔍 **Working on:** <@{member.id}>"]
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

            total_income = 0
            rent_entries = []
            to_deduct = {}
            housing_rent = 0
            business_rent = 0
            trauma_cost = 0
            trauma_role = None

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
                    income = int(rent * open_percent)
                    total_income += income
                    rent_entries.append(f"• {role} → +${income} passive income ({open_count} opens)")
                    business_rent += rent
                else:
                    housing_rent += rent
                rent_entries.append(f"• {role} → -${rent} rent")

            for role in trauma_roles:
                trauma_cost = TRAUMA_ROLE_COSTS[role]
                trauma_role = role
                rent_entries.append(f"• {role} → ${trauma_cost} subscription")

            log.append("🔁 **Changes this cycle:**")
            log.extend([f"   {e}" for e in rent_entries])

            if total_income > 0:
                income_success = await update_balance(member.id, {"cash": total_income}, reason="Passive income")
                if income_success:
                    balance_data = await get_balance(member.id)
                    if balance_data:
                        cash = balance_data["cash"]
                        bank = balance_data["bank"]
                        total = cash + bank
                        log.append(f"➕ Added ${total_income} passive income.")
                        log.append(f"📈 Balance after income — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${total:,}")

            final_deductions = {}
            running_total = cash + bank

            if running_total >= housing_rent:
                final_deductions["housing"] = housing_rent
                running_total -= housing_rent
            else:
                log.append(f"❌ Cannot pay housing rent of ${housing_rent}. Would result in negative balance.")

            if running_total >= business_rent:
                final_deductions["business"] = business_rent
                running_total -= business_rent
            else:
                log.append(f"❌ Cannot pay business rent of ${business_rent}. Would result in negative balance.")

            if trauma_cost and running_total >= trauma_cost:
                final_deductions["trauma"] = trauma_cost
                running_total -= trauma_cost
            elif trauma_cost:
                log.append(f"❌ Cannot pay {trauma_role} Subscription of ${trauma_cost}. Would result in negative balance.")
                log.append("⚠️ Subscription cancellation notice sent to user's #tt-plans-payment thread, Trauma team notified.")
                # forum log will still be triggered below

            # Only one update_balance call
            update_payload = {}
            original_cash, original_bank = cash, bank
            for label, amount in final_deductions.items():
                deduct_from_cash = min(cash, amount)
                deduct_from_bank = amount - deduct_from_cash
                if deduct_from_cash:
                    update_payload["cash"] = update_payload.get("cash", 0) - deduct_from_cash
                    cash -= deduct_from_cash
                if deduct_from_bank:
                    update_payload["bank"] = update_payload.get("bank", 0) - deduct_from_bank
                    bank -= deduct_from_bank
                log.append(f"🧮 Subtracting {label} ${amount} — ${deduct_from_cash} from cash, ${deduct_from_bank} from bank...")
                log.append(f"📈 Balance after {label} — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash+bank:,}")
                if label == "housing":
                    log.append("✅ Housing Rent collection completed. Notice Sent to #rent")
                elif label == "business":
                    log.append("✅ Business collection completed. Notice Sent to #rent")

            if update_payload:
                await update_balance(member.id, update_payload, reason="Consolidated Rent & Trauma Payment")

            await process_trauma_team_payment(member, cash, bank, log=log)
            log.append(f"📊 New balance — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash+bank:,}")

            await ctx.send("\n".join(log))

        except Exception as e:
            await ctx.send(f"❌ Error processing <@{member.id}>: `{e}`")

    await ctx.send("✅ Rent collection completed.")
