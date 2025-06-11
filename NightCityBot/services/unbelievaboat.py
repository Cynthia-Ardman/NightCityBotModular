import aiohttp
from typing import Dict, Optional
import config

class UnbelievaBoatAPI:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = f"https://unbelievaboat.com/api/v1/guilds/{config.GUILD_ID}"
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json"
        }

    async def get_balance(self, user_id: int) -> Optional[Dict]:
        """Get a user's balance from UnbelievaBoat."""
        url = f"{self.base_url}/users/{user_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def update_balance(
        self,
        user_id: int,
        amount_dict: Dict,
        reason: str = "Automated rent/income"
    ) -> bool:
        """Update a user's balance on UnbelievaBoat."""
        url = f"{self.base_url}/users/{user_id}"
        payload = amount_dict.copy()
        payload["reason"] = reason

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=self.headers, json=payload) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ PATCH failed: {resp.status} — {error}")
                return resp.status == 200