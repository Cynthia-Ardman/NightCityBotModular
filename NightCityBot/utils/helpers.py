from typing import Optional, List
import re
from datetime import datetime
import discord
from pathlib import Path
import json
import config

def build_channel_name(usernames, max_length=100):
    """Builds a Discord channel name for a group RP."""
    full_name = "text-rp-" + "-".join(f"{name}-{uid}" for name, uid in usernames)
    if len(full_name) <= max_length:
        return re.sub(r"[^a-z0-9\-]", "", full_name.lower())

    simple_name = "text-rp-" + "-".join(name for name, _ in usernames)
    if len(simple_name) > max_length:
        simple_name = simple_name[:max_length]

    return re.sub(r"[^a-z0-9\-]", "", simple_name.lower())

async def load_json_file(file_path: Path, default=None):
    """Safely load a JSON file with fallback to default value."""
    try:
        if file_path.exists():
            async with aiofiles.open(file_path, 'r') as f:
                return json.loads(await f.read())
    except Exception as e:
        print(f"Error loading {file_path.name}: {e}")
    return default if default is not None else {}

async def save_json_file(file_path: Path, data):
    """Safely save data to a JSON file."""
    try:
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
        return True
    except Exception as e:
        print(f"Error saving {file_path.name}: {e}")
        return False