import json
import os
import requests
import time
from urllib.parse import urlparse

def get_content_from_wayback(url, timestamp, retries=5):
    wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"
    attempt = 0
    while attempt < retries:
        response = requests.get(wayback_url)
        # Check for rate limit (HTTP 429)
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
            attempt += 1
        elif response.status_code == 200:
            return response
        else:
            print(f"Failed to fetch {wayback_url}. Status code: {response.status_code}")
            return None
    return None

def save_content(data, url, content_type):
    parsed_url = urlparse(url)
    folder_name = os.path.join("downloaded_data", parsed_url.netloc, parsed_url.path.strip('/'))
    os.makedirs(folder_name, exist_ok=True)

    if content_type.startswith('text/html'):
        with open(os.path.join(folder_name, 'index.html'), 'w', encoding='utf-8') as file:
            file.write(data.text)
    elif content_type.startswith('application/json'):
        with open(os.path.join(folder_name, 'data.json'), 'w', encoding='utf-8') as file:
            json.dump(data.json(), file, ensure_ascii=False, indent=4)
    elif content_type.startswith('image/'):
        img_data = data.content
        img_extension = content_type.split('/')[1]
        with open(os.path.join(folder_name, f'image.{img_extension}'), 'wb') as file:
            file.write(img_data)
    else:
        with open(os.path.join(folder_name, 'content.txt'), 'wb') as file:
            file.write(data.content)


with open('metadata.json', 'r', encoding='utf-8') as f:
    entries = json.load(f)

for entry in entries:
    # Extract information
    url = entry[2]
    timestamp = entry[1]
    content_type = entry[3]

    print(f"Processing: {url}, Timestamp: {timestamp}, Content Type: {content_type}")

    response = get_content_from_wayback(url, timestamp)

    if response:
        save_content(response, url, content_type)
        print(f"Saved content for {url}")
    else:
        print(f"Failed to fetch content for {url}. Skipping.")
