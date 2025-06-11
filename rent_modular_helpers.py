
async def apply_passive_income(member, applicable_roles, business_open_log, log):
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
            return updated["cash"], updated["bank"]
        else:
            log.append("❌ Failed to apply passive income.")
    return None, None


async def process_housing_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel):
    housing_total = 0
    for role in roles:
        if "Housing Tier" in role:
            amount = role_costs.get(role, 0)
            housing_total += amount
            log.append(f"🔎 Housing Role {role} → Rent: ${amount}")

    if housing_total == 0:
        return cash, bank

    total = cash + bank
    if total < housing_total:
        log.append(f"❌ Cannot pay housing rent of ${housing_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — Insufficient funds for housing rent (${housing_total})."
            )
        if rent_log_channel:
            await rent_log_channel.send(
                f"❌ <@{member.id}> — Housing Rent due: ${housing_total} — **FAILED**"
            )
        log.append("⚠️ Housing rent not deducted.")
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
    return cash, bank


async def process_business_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel):
    business_total = 0
    for role in roles:
        if "Business Tier" in role:
            amount = role_costs.get(role, 0)
            business_total += amount
            log.append(f"🔎 Business Role {role} → Rent: ${amount}")

    if business_total == 0:
        return cash, bank

    total = cash + bank
    if total < business_total:
        log.append(f"❌ Cannot pay business rent of ${business_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — Insufficient funds for business rent (${business_total})."
            )
        if rent_log_channel:
            await rent_log_channel.send(
                f"❌ <@{member.id}> — Business Rent due: ${business_total} — **FAILED**"
            )
        log.append("⚠️ Business rent not deducted.")
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
        log.append(f"🧮 Subtracted business rent ${business_total} — ${deduct_cash} from cash, ${deduct_bank} from bank.")
        log.append(f"📈 Balance after business rent — Cash: ${cash:,}, Bank: ${bank:,}, Total: ${cash + bank:,}")
        log.append("✅ Business Rent collection completed. Notice Sent to #rent")
        if rent_log_channel:
            await rent_log_channel.send(f"✅ <@{member.id}> — Business Rent paid: ${business_total}")
    return cash, bank
