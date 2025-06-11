# config.py
# Configuration management for NCRP Bot
import os
from typing import Dict
from dataclasses import dataclass, field

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))

@dataclass
class BotConfig:
    """Central configuration class for the bot."""

    # Bot token - NEVER commit this to version control
    TOKEN: str = "MTM3OTUyNzc4OTQzNDI0MTExNA.GvXqPH.VoumI0nbwNBD2VPIySMRVrpjdI0BNQd3N2ZTYM"

    # Guild and channel IDs
    GUILD_ID: int = 1320924574761746473
    AUDIT_LOG_CHANNEL_ID = 1341160960924319804
    GROUP_AUDIT_LOG_CHANNEL_ID = 1366880900599517214
    DM_INBOX_CHANNEL_ID = 1366880900599517214
    RENT_LOG_CHANNEL_ID: int = 1379615621167321189
    EVICTION_CHANNEL_ID: int = 1379611043843539004
    TRAUMA_FORUM_CHANNEL_ID: int = 1366880900599517214
    BUSINESS_ACTIVITY_CHANNEL_ID: int = 1379623117994852443

    # Role IDs and names
    FIXER_ROLE_NAME: str = "Fixer"
    FIXER_ROLE_ID: int = 1379437060389339156
    TRAUMA_TEAM_ROLE_ID: int = 1380341033124102254

    # API tokens
    UNBELIEVABOAT_API_TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2NDQ1MTE2NDkyMDI2IiwiaWF0IjoxNzQ5MTc3NjMxfQ.Hgn611UEILLF1ogVDxlQpHivT89ArroJnAliouHE7P4"

    # File paths for persistent data
    SEEN_MSG_ID_FILE: str = "data/backfill_seen_ids.json"
    THREAD_MAP_FILE: str = "data/thread_map.json"
    OPEN_LOG_FILE: str = "data/business_open_log.json"
    LAST_RENT_FILE: str = "data/last_rent.json"

    # Economic constants
    FLAT_MONTHLY_FEE: int = 500

    # Role costs
    HOUSING_ROLE_COSTS: dict = field(default_factory=dict) = {
        "Housing Tier 1": 1000,# config.py
# Configuration management for NCRP Bot
import os
from typing import Dict
from dataclasses import dataclass, field

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))

@dataclass
class BotConfig:
    """Central configuration class for the bot."""

    # Bot token - NEVER commit this to version control
    TOKEN: str = "MTM3OTUyNzc4OTQzNDI0MTExNA.GvXqPH.VoumI0nbwNBD2VPIySMRVrpjdI0BNQd3N2ZTYM"

    # Guild and channel IDs
    GUILD_ID: int = 1320924574761746473
    AUDIT_LOG_CHANNEL_ID = 1341160960924319804
    GROUP_AUDIT_LOG_CHANNEL_ID = 1366880900599517214
    DM_INBOX_CHANNEL_ID = 1366880900599517214
    RENT_LOG_CHANNEL_ID: int = 1379615621167321189
    EVICTION_CHANNEL_ID: int = 1379611043843539004
    TRAUMA_FORUM_CHANNEL_ID: int = 1366880900599517214
    BUSINESS_ACTIVITY_CHANNEL_ID: int = 1379623117994852443

    # Role IDs and names
    FIXER_ROLE_NAME: str = "Fixer"
    FIXER_ROLE_ID: int = 1379437060389339156
    TRAUMA_TEAM_ROLE_ID: int = 1380341033124102254

    # API tokens
    UNBELIEVABOAT_API_TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzc5NjA2NDQ1MTE2NDkyMDI2IiwiaWF0IjoxNzQ5MTc3NjMxfQ.Hgn611UEILLF1ogVDxlQpHivT89ArroJnAliouHE7P4"

    # File paths for persistent data
    SEEN_MSG_ID_FILE: str = "data/backfill_seen_ids.json"
    THREAD_MAP_FILE: str = "data/thread_map.json"
    OPEN_LOG_FILE: str = "data/business_open_log.json"
    LAST_RENT_FILE: str = "data/last_rent.json"

    # Economic constants
    FLAT_MONTHLY_FEE: int = 500

    # Role costs
    HOUSING_ROLE_COSTS: Dict[str, int] = field(default_factory=lambda: = {
        "Housing Tier 1": 1000,
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000
    }

    BUSINESS_ROLE_COSTS: Dict[str, int] = {
        "Business Tier 0": 0,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000
    }

    TRAUMA_ROLE_COSTS: Dict[str, int] = {
        "Trauma Team Silver": 1000,
        "Trauma Team Gold": 2000,
        "Trauma Team Plat": 4000,
        "Trauma Team Diamond": 10000
    }

    # Business income scaling
    TIER_0_INCOME_SCALE: Dict[int, int] = {
        1: 150,
        2: 250,
        3: 350,
        4: 500
    }

    # Netrunner bonuses
    NETRUNNER_BONUSES: Dict[str, int] = {
        "Netrunner Level 2": 1,
        "Netrunner Level 3": 2
    }

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable not set")

        if not self.UNBELIEVABOAT_API_TOKEN:
            raise ValueError("UNBELIEVABOAT_API_TOKEN environment variable not set")

        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Ensure log directory exists
        os.makedirs("logs", exist_ok=True)

    @property
    def unbelievaboat_base_url(self) -> str:
        """Get UnbelievaBoat API base URL."""
        return f"https://unbelievaboat.com/api/v1/guilds/{self.GUILD_ID}/users"
        "Housing Tier 2": 2000,
        "Housing Tier 3": 3000
    }

    BUSINESS_ROLE_COSTS: Dict[str, int] = {
        "Business Tier 0": 0,
        "Business Tier 1": 2000,
        "Business Tier 2": 3000,
        "Business Tier 3": 5000
    }

    TRAUMA_ROLE_COSTS: Dict[str, int] = {
        "Trauma Team Silver": 1000,
        "Trauma Team Gold": 2000,
        "Trauma Team Plat": 4000,
        "Trauma Team Diamond": 10000
    }

    # Business income scaling
    TIER_0_INCOME_SCALE: Dict[int, int] = {
        1: 150,
        2: 250,
        3: 350,
        4: 500
    }

    # Netrunner bonuses
    NETRUNNER_BONUSES: Dict[str, int] = {
        "Netrunner Level 2": 1,
        "Netrunner Level 3": 2
    }

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable not set")

        if not self.UNBELIEVABOAT_API_TOKEN:
            raise ValueError("UNBELIEVABOAT_API_TOKEN environment variable not set")

        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Ensure log directory exists
        os.makedirs("logs", exist_ok=True)

    @property
    def unbelievaboat_base_url(self) -> str:
        """Get UnbelievaBoat API base URL."""
        return f"https://unbelievaboat.com/api/v1/guilds/{self.GUILD_ID}/users"