import os
import json
import re
import discord

# ─── CONFIG ────────────────────────────────────────────────────────────────
# (Hard-coded – replace with environment vars or literals as you prefer)
TOKEN      = "MTIxMzI1MjEwNjA2NTAyMzAzNw.GDvA6e.HrYYp-mdMJYpX4VGXI-p7-UbEpf93gNbQNmQqI"
CHANNEL_ID = 1366901669316657224

# ─── SCRIPT ───────────────────────────────────────────────────────────────
class ThreadDumper(discord.Client):
    FIELD_NAMES = [
        "Name",
        "Age",
        "Pronouns",
        "Occupation",
        "Psychological Profile",
        "Physical Description",
        "Chrome/Implants",
        "Skills/Abilities",
        "Weapons/Armor/Equipment",
        "Character Concept/ Back story",
        # add any others you want to catch…
    ]

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)

    def parse_character_info(self, messages):
        """
        Scan each message.content line-by-line for “Field: value” pairs
        matching one of our FIELD_NAMES. Returns a dict of whatever it finds.
        """
        info = {}
        pattern = re.compile(rf"^({'|'.join(map(re.escape, self.FIELD_NAMES))})\s*:\s*(.+)$")
        for msg in messages:
            for line in msg["content"].splitlines():
                m = pattern.match(line)
                if m:
                    field, val = m.group(1), m.group(2).strip()
                    # if multi-line values are needed, you could accumulate here
                    info[field] = val
        return info

    async def on_ready(self):
        print(f'✅ Logged in as {self.user} — fetching channel {CHANNEL_ID}…')

        channel = await self.fetch_channel(CHANNEL_ID)
        if channel is None or not hasattr(channel, "threads"):
            print(f'❌ Channel not found or doesn’t support threads.')
            await self.close()
            return

        threads = list(channel.threads)
        archived = [thr async for thr in channel.archived_threads(limit=None)]
        threads += archived

        output = {"threads": []}

        for thread in threads:
            print(f'  • Dumping "{thread.name}" ({thread.id})…')
            # pull messages first
            msgs = []
            async for msg in thread.history(limit=None, oldest_first=True):
                msgs.append({
                    "message_id":         msg.id,
                    "author_id":          msg.author.id,
                    "author_name":        msg.author.name,
                    "message_created_at": msg.created_at.isoformat(),
                    "content":            msg.content,
                    "attachments":        [a.url for a in msg.attachments],
                })

            # structure the thread object
            thread_obj = {
                "thread_id":         thread.id,
                "thread_name":       thread.name,
                "thread_owner_id":   thread.owner_id,
                "thread_created_at": thread.created_at.isoformat(),
                "message_count":     len(msgs),
                "messages":          msgs,
                # **new** parsed fields
                "parsed_fields":     self.parse_character_info(msgs),
            }

            output["threads"].append(thread_obj)

        # write out
        with open("threads.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print("✅ threads.json written with parsed_fields")
        await self.close()

# ─── ENTRYPOINT ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ThreadDumper().run(TOKEN)