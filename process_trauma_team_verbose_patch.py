
# --- Trauma Team Subscription Processing ---

TRAUMA_ROLE_COSTS = {
    "Trauma Team Silver": 1000,
    "Trauma Team Gold": 2000,
    "Trauma Team Plat": 4000,
    "Trauma Team Diamond": 10000
}

TRAUMA_TEAM_ROLE_ID = 1348661300334563328
TRAUMA_FORUM_CHANNEL_ID = 1351070651313557545

async def process_trauma_team_payment(member, cash, bank, log: list = None):
    trauma_channel = bot.get_channel(TRAUMA_FORUM_CHANNEL_ID)
    if not isinstance(trauma_channel, discord.ForumChannel):
        if log is not None:
            log.append("⚠️ TT forum channel not found.")
        return

    trauma_cost = 0
    trauma_role = None
    for role in member.roles:
        if role.name in TRAUMA_ROLE_COSTS:
            trauma_cost = TRAUMA_ROLE_COSTS[role.name]
            trauma_role = role.name
            break

    if not trauma_role:
        return  # No trauma tier, skip

    # Mention role and compute new balances
    total_balance = cash + bank
    log.append(f"🔎 {trauma_role} → Subscription: ${trauma_cost}")
    log.append("💊 Processing Trauma Team subscription...")

    # Locate thread
    thread_name_suffix = f"- {member.id}"
    target_thread = None
    for thread in trauma_channel.threads:
        if thread.name.endswith(thread_name_suffix):
            target_thread = thread
            break

    if not target_thread:
        log.append(f"⚠️ Could not locate Trauma Team thread for <@{member.id}>")
        return

    if total_balance < trauma_cost:
        mention = f"<@&{TRAUMA_TEAM_ROLE_ID}>"
        log.append(f"❌ Cannot pay {trauma_role} Subscription of ${trauma_cost}. Would result in negative balance.")
        log.append("⚠️ Subscription cancellation notice sent to user's #tt-plans-payment thread, Trauma team notified.")
        await target_thread.send(
            f"❌ **Payment Failed** for <@{member.id}> — needed `${trauma_cost}`, only has `${total_balance}`.
"
            f"{mention} please review their coverage."
        )
        return

    # Deduct
    update_payload = {}
    cash_used = min(cash, trauma_cost)
    bank_used = trauma_cost - cash_used

    if cash_used > 0:
        update_payload["cash"] = -cash_used
    if bank_used > 0:
        update_payload["bank"] = -bank_used

    log.append(f"🧮 Subtracting Trauma Team Subscription ${trauma_cost} — ${cash_used} from cash, ${bank_used} from bank...")

    success = await update_balance(member.id, update_payload, reason="Trauma Team Subscription")
    if success:
        log.append("✅ Trauma Team subscription payment completed. Notice Sent to user's #tt-plans-payment thread.")
        await target_thread.send(
            f"✅ **Payment Successful** for <@{member.id}> — paid `${trauma_cost}` for **{trauma_role}** coverage."
        )
    else:
        log.append("⚠️ Failed to apply Trauma Team payment, manual review needed.")
        await target_thread.send(
            f"⚠️ **Deduction failed** despite available funds for <@{member.id}>."
        )
