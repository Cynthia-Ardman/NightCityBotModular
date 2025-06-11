
async def process_housing_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel, role_costs_housing):
    housing_total = 0
    for role in roles:
        if "Housing Tier" in role:
            amount = role_costs_housing.get(role, 0)
            housing_total += amount
            log.append(f"🔎 Housing Role {role} → Rent: ${amount}")

    if housing_total == 0:
        return cash, bank

    total = cash + bank
    if total < housing_total:
        log.append(f"❌ Cannot pay housing rent of ${housing_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — You only have ${total}, but your housing rent this cycle is ${housing_total}.
"
                f"You have **7 days** to pay or face eviction."
            )
        if rent_log_channel:
            await rent_log_channel.send(
                f"❌ <@{member.id}> — Housing Rent due: ${housing_total} — **FAILED** (insufficient funds)"
            )
        log.append(f"⚠️ Housing rent skipped for <@{member.id}> due to insufficient funds.")
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
    else:
        log.append("❌ Failed to deduct housing rent despite having sufficient funds.")
    return cash, bank


async def process_business_rent(member, roles, cash, bank, log, rent_log_channel, eviction_channel, role_costs_business):
    business_total = 0
    for role in roles:
        if "Business Tier" in role:
            amount = role_costs_business.get(role, 0)
            business_total += amount
            log.append(f"🔎 Business Role {role} → Rent: ${amount}")

    if business_total == 0:
        return cash, bank

    total = cash + bank
    if total < business_total:
        log.append(f"❌ Cannot pay business rent of ${business_total}. Would result in negative balance.")
        if eviction_channel:
            await eviction_channel.send(
                f"🚨 <@{member.id}> — You only have ${total}, but your business rent this cycle is ${business_total}.
"
                f"You have **7 days** to pay or face eviction."
            )
        if rent_log_channel:
            await rent_log_channel.send(
                f"❌ <@{member.id}> — Business Rent due: ${business_total} — **FAILED** (insufficient funds)"
            )
        log.append(f"⚠️ Business rent skipped for <@{member.id}> due to insufficient funds.")
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
    else:
        log.append("❌ Failed to deduct business rent despite having sufficient funds.")
    return cash, bank
