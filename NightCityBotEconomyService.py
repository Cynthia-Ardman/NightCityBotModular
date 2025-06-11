# services/economy_service.py
# Economy and UnbelievaBoat API integration
import aiohttp
import logging
from typing import Optional, Dict, Any
from NightCityBot.NightCityBotConfig import BotConfig

logger = logging.getLogger(__name__)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))

class EconomyService:
    """Service for handling economy operations through UnbelievaBoat API."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.headers = {
            "Authorization": config.UNBELIEVABOAT_API_TOKEN,
            "Content-Type": "application/json"
        }

    async def get_balance(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's balance from UnbelievaBoat API."""
        url = f"{self.config.unbelievaboat_base_url}/{user_id}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.debug(f"Retrieved balance for user {user_id}: {data}")
                        return data
                    else:
                        error_text = await resp.text()
                        logger.error(f"Failed to get balance for {user_id}: {resp.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Exception getting balance for {user_id}: {e}")
            return None

    async def update_balance(
            self,
            user_id: int,
            amount_dict: Dict[str, int],
            reason: str = "Automated transaction"
    ) -> bool:
        """Update user's balance through UnbelievaBoat API."""
        url = f"{self.config.unbelievaboat_base_url}/{user_id}"

        payload = amount_dict.copy()
        payload["reason"] = reason

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        logger.debug(f"Updated balance for user {user_id}: {payload}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Failed to update balance for {user_id}: {resp.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Exception updating balance for {user_id}: {e}")
            return False

    async def deduct_amount(
            self,
            user_id: int,
            amount: int,
            reason: str = "Deduction"
    ) -> tuple[bool, Dict[str, int]]:
        """
        Deduct amount from user's balance, preferring cash over bank.
        Returns (success, {cash_deducted, bank_deducted})
        """
        balance_data = await self.get_balance(user_id)
        if not balance_data:
            return False, {"cash": 0, "bank": 0}

        cash = balance_data.get("cash", 0)
        bank = balance_data.get("bank", 0)
        total = cash + bank

        if total < amount:
            logger.warning(f"Insufficient funds for user {user_id}: need {amount}, have {total}")
            return False, {"cash": 0, "bank": 0}

        # Calculate deduction amounts
        cash_deducted = min(cash, amount)
        bank_deducted = amount - cash_deducted

        # Prepare update payload
        update_payload = {}
        if cash_deducted > 0:
            update_payload["cash"] = -cash_deducted
        if bank_deducted > 0:
            update_payload["bank"] = -bank_deducted

        # Execute the update
        success = await self.update_balance(user_id, update_payload, reason)

        if success:
            return True, {"cash": cash_deducted, "bank": bank_deducted}
        else:
            return False, {"cash": 0, "bank": 0}

    async def add_amount(
            self,
            user_id: int,
            amount: int,
            to_cash: bool = True,
            reason: str = "Addition"
    ) -> bool:
        """Add amount to user's balance."""
        update_payload = {}
        if to_cash:
            update_payload["cash"] = amount
        else:
            update_payload["bank"] = amount

        return await self.update_balance(user_id, update_payload, reason)

    def calculate_netrunner_bonus(self, user_roles: list[str]) -> int:
        """Calculate netrunner bonus based on user roles."""
        for role, bonus in self.config.NETRUNNER_BONUSES.items():
            if role in user_roles:
                return bonus
        return 0

    def has_housing_roles(self, user_roles: list[str]) -> list[str]:
        """Get list of housing roles user has."""
        return [role for role in user_roles if role in self.config.HOUSING_ROLE_COSTS]

    def has_business_roles(self, user_roles: list[str]) -> list[str]:
        """Get list of business roles user has."""
        return [role for role in user_roles if role in self.config.BUSINESS_ROLE_COSTS]

    def has_trauma_roles(self, user_roles: list[str]) -> list[str]:
        """Get list of trauma team roles user has."""
        return [role for role in user_roles if role in self.config.TRAUMA_ROLE_COSTS]

    def calculate_housing_cost(self, user_roles: list[str]) -> int:
        """Calculate total housing cost for user."""
        housing_roles = self.has_housing_roles(user_roles)
        return sum(self.config.HOUSING_ROLE_COSTS[role] for role in housing_roles)

    def calculate_business_cost(self, user_roles: list[str]) -> int:
        """Calculate total business cost for user."""
        business_roles = self.has_business_roles(user_roles)
        return sum(self.config.BUSINESS_ROLE_COSTS[role] for role in business_roles)

    def calculate_trauma_cost(self, user_roles: list[str]) -> int:
        """Calculate trauma team subscription cost for user."""
        trauma_roles = self.has_trauma_roles(user_roles)
        if trauma_roles:
            # User should only have one trauma role, but take the highest cost
            return max(self.config.TRAUMA_ROLE_COSTS[role] for role in trauma_roles)
        return 0