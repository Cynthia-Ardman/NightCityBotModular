import discord
from discord.ext import commands

TOKEN = "MTIxMzI1MjEwNjA2NTAyMzAzNw.Gc6p6b.KAdYaG-iy9glo3P2nnJbWlbwjStqW4kWk6ULAg"
SOURCE_GUILD_ID = 1348601552083882108  # Replace with source guild ID
EVENT_ID = 1358601484236882082        # Replace with event ID you want to copy

intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild = bot.get_guild(SOURCE_GUILD_ID)
    if not guild:
        print("Source guild not found.")
        await bot.close()
        return

    try:
        event = await bot.http.request(
            discord.http.Route("GET", "/guilds/{guild_id}/scheduled-events/{event_id}", guild_id=SOURCE_GUILD_ID, event_id=EVENT_ID)
        )
    except discord.NotFound:
        print("Event not found (double-check your IDs).")
        await bot.close()
        return
    except discord.HTTPException as e:
        print(f"HTTP error retrieving event: {e}")
        await bot.close()
        return

    print("✅ Past Event Retrieved:")
    print(f"Name: {event['name']}")
    print(f"Description: {event['description']}")
    print(f"Start Time: {event['scheduled_start_time']}")
    print(f"End Time: {event.get('scheduled_end_time')}")
    print(f"Location: {event.get('entity_metadata', {}).get('location')}")
    print(f"Event Type: {event['entity_type']}")

    image_hash = event.get('image')
    if image_hash:
        image_url = f"https://cdn.discordapp.com/guild-events/{EVENT_ID}/{image_hash}.webp?size=2048"
        print(f"High-quality Cover Image URL: {image_url}")
    else:
        print("No cover image set for this event.")

    await bot.close()

bot.run(TOKEN)
