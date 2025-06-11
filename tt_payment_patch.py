
# --- Trauma Team Subscription Processing ---

TRAUMA_ROLE_COSTS = {
    "Trauma Team Silver": 1000,
    "Trauma Team Gold": 2000,
    "Trauma Team Plat": 4000,
    "Trauma Team Diamond": 10000
}

TRAUMA_TEAM_ROLE_ID = 1348661300334563328
TRAUMA_FORUM_CHANNEL_ID = 1351070651313557545

async def process_trauma_team_payment(member, cash, bank):
    trauma_channel = bot.get_channel(TRAUMA_FORUM_CHANNEL_ID)
    if not isinstance(trauma_channel, discord.ForumChannel):
        print("[ERROR] Trauma Team forum channel not found or wrong type.")
        return

    # Determine trauma tier (highest matching role)
    trauma_cost = 0
    trauma_role = None
    for role in member.roles:
        if role.name in TRAUMA_ROLE_COSTS:
            trauma_cost = TRAUMA_ROLE_COSTS[role.name]
            trauma_role = role.name
            break  # assume only one TT role per user

    if not trauma_role:
        return  # no TT subscription, nothing to do

    # Find the user's TT thread
    thread_name_suffix = f"- {member.id}"
    target_thread = None
    for thread in trauma_channel.threads:
        if thread.name.endswith(thread_name_suffix):
            target_thread = thread
            break

    if not target_thread:
        print(f"[ERROR] TT thread not found for {member.display_name} ({member.id})")
        return

    # Determine payment method
    total_balance = cash + bank
    if total_balance < trauma_cost:
        mention = f"<@&{TRAUMA_TEAM_ROLE_ID}>"
        await target_thread.send(
            f"❌ **Payment Failed** for <@{member.id}> — "
            f"needed `${trauma_cost}`, only has `${total_balance}`.
"
            f"{mention} please review their coverage."
        )
        return

    # Deduct from cash then bank
    to_deduct = trauma_cost
    update_payload = {}
    cash_used = min(cash, to_deduct)
    bank_used = to_deduct - cash_used

    if cash_used > 0:
        update_payload["cash"] = -cash_used
    if bank_used > 0:
        update_payload["bank"] = -bank_used

    success = await update_balance(member.id, update_payload, reason="Trauma Team Subscription")
    if success:
        await target_thread.send(
            f"✅ **Payment Successful** for <@{member.id}> — "
            f"paid `${trauma_cost}` for **{trauma_role}** coverage."
        )
    else:
        await target_thread.send(
            f"⚠️ **Failed to deduct** `${trauma_cost}` from <@{member.id}>'s account despite sufficient funds."
        )
