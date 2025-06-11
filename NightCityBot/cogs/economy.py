import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from utils.permissions import is_fixer
from utils.constants import (
    ROLE_COSTS_BUSINESS,
    ROLE_COSTS_HOUSING,
    BASELINE_LIVING_COST,
    TIER_0_INCOME_SCALE,
    OPEN_PERCENT
)
from utils.helpers import load_json_file, save_json_file
import config
from services.unbelievaboat import UnbelievaBoatAPI
from services.trauma_team import TraumaTeamService


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.unbelievaboat = UnbelievaBoatAPI(config.UNBELIEVABOAT_API_TOKEN)
        self.trauma_service = TraumaTeamService(bot)

    def calculate_passive_income(self, role: str, open_count: int) -> int:
        """Calculate passive income based on role and number of shop opens."""
        if role == "Business Tier 0":
            return TIER_0_INCOME_SCALE.get(open_count, 0)

        base_rent = ROLE_COSTS_BUSINESS.get(role, 500)
        return int(base_rent * OPEN_PERCENT[open_count])

    async def apply_passive_income(
            self,
            member: discord.Member,
            applicable_roles: List[str],
            business_open_log: Dict,
            log: List[str]
    ) -> tuple[Optional[int], Optional[int]]:
        """Apply passive income based on business opens and roles."""
        total_income = 0

        member_id_str = str(member.id)
        opens_this_month = [
            ts for ts in business_open_log.get(member_id_str, [])
            if datetime.fromisoformat(ts).month == datetime.utcnow().month and
               datetime.fromisoformat(ts).year == datetime.utcnow().year
        ]
        open_count = min(len(opens_this_month), 4)

        for role in applicable_roles:
            if "Housing Tier" in role:
                continue

            income = self.calculate_passive_income(role, open_count)
            log.append(f"💰 Passive income for {role}: ${income} ({open_count} opens)")
            total_income += income

        if total_income > 0:
            success = await self.unbelievaboat.update_balance(
                member.id,
                {"cash": total_income},
                reason="Passive income"
            )
            if success:
                updated = await self.unbelievaboat.get_balance(member.id)
                log.append(f"➕ Added ${total_income} passive income.")
                if updated:
                    return updated["cash"], updated["bank"]

        current = await self.unbelievaboat.get_balance(member.id)
        if current:
            return current["cash"], current["bank"]
        return None, None

    @commands.command()
    @commands.has_permissions(send_messages=True)
    async def open_shop(self, ctx):
        """Log a business opening (Sunday only)."""
        if ctx.channel.id != config.BUSINESS_ACTIVITY_CHANNEL_ID:
            await ctx.send("❌ You can only log business openings in the designated business activity channel.")
            return

        now = datetime.utcnow()
        if now.weekday() != 6:
            await ctx.send("❌ Business openings can only be logged on Sundays.")
            return

        user_id = str(ctx.author.id)
        now_str = now.isoformat()

        data = await load_json_file(config.OPEN_LOG_FILE, default={})

        all_opens = data.get(user_id, [])
        this_month_opens = [
            datetime.fromisoformat(ts)
            for ts in all_opens
            if datetime.fromisoformat(ts).month == now.month and
               datetime.fromisoformat(ts).year == now.year
        ]

        if any(ts.date() == now.date() for ts in this_month_opens):
            await ctx.send("❌ You've already logged a business opening today.")
            return

        if len(this_month_opens) >= 4:
            await ctx.send("❌ You've already used all 4 business posts for this month.")
            return

        all_opens.append(now_str)
        data[user_id] = all_opens
        await save_json_file(config.OPEN_LOG_FILE, data)

        await ctx.send(f"✅ Business opening logged! ({len(this_month_opens) + 1}/4 this month)")

    # Add other economy-related commands (collect_rent, collect_housing, etc.)
    # [Rest of the economy commands would go here]