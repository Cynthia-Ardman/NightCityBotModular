import discord
from discord.ext import commands
from datetime import timedelta, datetime
import re
import requests

TOKEN = "MTIxMzI1MjEwNjA2NTAyMzAzNw.Gc6p6b.KAdYaG-iy9glo3P2nnJbWlbwjStqW4kWk6ULAg"
GUILD_ID = 1348601552083882108  # Replace with source guild ID
NUM_OF_NEW_EVENTS = 2  # Number of subsequent events to create
EVENT_ID = 1369497252325752833        # Replace with event ID you want to copy

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found.")
        await bot.close()
        return

    original_event = await bot.http.request(
        discord.http.Route("GET", "/guilds/{guild_id}/scheduled-events/{event_id}", guild_id=GUILD_ID, event_id=EVENT_ID)
    )

    image_hash = original_event.get('image')
    image_bytes = None

    if image_hash:
        image_url = f"https://cdn.discordapp.com/guild-events/{EVENT_ID}/{image_hash}.webp?size=2048"
        response = requests.get(image_url)
        if response.status_code == 200:
            image_bytes = response.content

    original_name = original_event['name']
    match = re.search(r'(.*?Session\s)(\d+)', original_name)
    if not match:
        print("Event name format unexpected.")
        await bot.close()
        return

    name_prefix, session_number = match.groups()
    session_number = int(session_number)

    original_start_time = datetime.fromisoformat(original_event['scheduled_start_time'])
    original_end_time = datetime.fromisoformat(original_event['scheduled_end_time']) if original_event.get('scheduled_end_time') else None

    for i in range(1, NUM_OF_NEW_EVENTS + 1):
        new_session_number = session_number + i
        new_name = f"{name_prefix}{new_session_number}"

        new_start_time = original_start_time + timedelta(weeks=i)
        new_end_time = original_end_time + timedelta(weeks=i) if original_end_time else None

        entity_type = discord.EntityType(original_event['entity_type'])
        privacy_level = discord.PrivacyLevel(original_event['privacy_level'])

        kwargs = {
            "name": new_name,
            "description": original_event['description'],
            "start_time": new_start_time,
            "end_time": new_end_time,
            "entity_type": entity_type,
            "privacy_level": privacy_level,
            "image": image_bytes
        }

        if entity_type == discord.EntityType.external:
            kwargs["location"] = original_event.get('entity_metadata', {}).get('location')
        else:  # internal event
            channel_id = original_event.get('channel_id')
            kwargs["channel"] = guild.get_channel(channel_id)

        new_event = await guild.create_scheduled_event(**kwargs)
        print(f"Created event: {new_event.name} - {new_event.url}")

    await bot.close()

bot.run(TOKEN)

