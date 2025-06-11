import requests
import time

GROUP_ID = 'grp_75b4673a-6156-4d41-a61d-1f7411043922'
AUTH_COOKIE = 'authcookie_0b9d5f14-5cec-493d-b222-74a296931ee3'
EXCLUDED_ROLE_ID = 'grol_20e582b8-4397-49d1-a0b6-c35e5b7c8f5e'

headers = {
    'Cookie': f'auth={AUTH_COOKIE}',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Referer': f'https://vrchat.com/home/group/{GROUP_ID}/members',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin'
}

all_members = []
offset = 0
limit = 25  # VRChat uses 25 per page

print("Fetching group members, please wait...")

while True:
    url = f'https://vrchat.com/api/1/groups/{GROUP_ID}/members?n={limit}&offset={offset}'
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching members at offset {offset}: {response.status_code} - {response.text}")
        break

    batch = response.json()

    if not batch:
        print("No more data received, stopping.")
        break

    all_members.extend(batch)
    print(f"Fetched {len(batch)} members, total fetched: {len(all_members)}")

    if len(batch) < limit:
        print("Reached end of data.")
        break

    offset += limit
    time.sleep(1)  # slight delay to prevent rate limiting

print(f"\nTotal members fetched: {len(all_members)}")

filtered_members = [
    member for member in all_members
    if member['roleIds'] and not (len(member['roleIds']) == 1 and member['roleIds'][0] == EXCLUDED_ROLE_ID)
]

print("\nMembers with special roles (excluding the specified role):")
for member in filtered_members:
    username = member['user']['displayName']
    roles = member['roleIds']
    print(f'{username} - Roles: {roles}')

print(f"\nTotal filtered members: {len(filtered_members)}")
