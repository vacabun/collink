"""
collink.py — equal-love.link full message & media downloader
"collink" = clone link
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta

import requests as _requests

# Japan Standard Time (JST = UTC+9)
_JST = timezone(timedelta(hours=9))

from src.equal_love_client import EqualLoveClient

# Output directory
OUTPUT_DIR = "messages"
# Delay between requests (seconds) to avoid hammering the server
REQUEST_INTERVAL = 0.5


def load_config(path: str = "config.json") -> dict:
    """Load credentials from config file"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _room_dir(talk_room_id: int, room_name: str) -> str:
    safe_name = room_name.replace(" ", "_").replace("/", "-")
    return os.path.join(OUTPUT_DIR, f"{talk_room_id:02d}_{safe_name}")


def _download_media(url: str, dest_path: str) -> bool:
    """Download a media file from a CDN signed URL (no auth required)"""
    try:
        r = _requests.get(url, timeout=30)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"    [media download failed] {os.path.basename(dest_path)}: {e}")
        return False


def download_and_save(
    client: EqualLoveClient,
    talk_room_id: int,
    room_name: str,
    room_info: dict = None,
    page_size: int = 50,
) -> tuple[str, int]:
    """Download messages and media, saving to disk page by page.

    Output structure:
        messages/{id}_{name}/
            info.json        # talk room metadata
            messages.json    # all messages (with localPath field added)
            media/           # downloaded images and videos

    :return: (output directory path, total message count)
    """
    room_dir = _room_dir(talk_room_id, room_name)
    media_dir = os.path.join(room_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    # Save talk room metadata
    if room_info:
        with open(os.path.join(room_dir, "info.json"), "w", encoding="utf-8") as f:
            json.dump(room_info, f, ensure_ascii=False, indent=2)

    messages_path = os.path.join(room_dir, "messages.json")
    total = 0
    media_total = 0
    page_num = 1
    next_page_id = 0
    first_msg = True

    with open(messages_path, "w", encoding="utf-8") as f:
        f.write("[\n")

        while True:
            resp = client.get_chat(
                talk_room_id=talk_room_id,
                page=1,
                page_size=page_size,
                page_start_id=next_page_id,
            )
            data = resp.get("data", [])

            if not data:
                break

            for msg in data:
                # Add human-readable date in JST
                posted = msg.get("postedDate", 0)
                if posted:
                    msg["postedDateStr"] = datetime.fromtimestamp(posted, tz=_JST).strftime("%Y-%m-%d %H:%M:%S JST")

                # Download media files
                for media in msg.get("chatMedia", []):
                    ext = media.get("fileExtension", "bin")
                    filename = f"{media['id']}.{ext}"
                    dest = os.path.join(media_dir, filename)
                    if not os.path.exists(dest):
                        url = media.get("url", "")
                        if url and _download_media(url, dest):
                            media["localPath"] = os.path.join("media", filename)
                            media_total += 1
                    else:
                        media["localPath"] = os.path.join("media", filename)

                # Append to JSON array
                if not first_msg:
                    f.write(",\n")
                f.write(json.dumps(msg, ensure_ascii=False, indent=2))
                first_msg = False

            f.flush()
            total += len(data)
            next_page_id = resp.get("nextPageId", 0)
            print(f"  page {page_num:>3}  messages: {total:>5}  media: {media_total:>4}  nextPageId: {next_page_id}")

            if next_page_id == 0:
                break

            page_num += 1
            time.sleep(REQUEST_INTERVAL)

        f.write("\n]\n")

    return room_dir, total


def main():
    # Load credentials
    config = load_config()
    client = EqualLoveClient(
        authorization=config["authorization"],
        x_request_verification_key=config["x_request_verification_key"],
        x_artist_group_uuid=config["x_artist_group_uuid"],
        x_device_uuid=config["x_device_uuid"],
    )

    # Fetch talk room list
    print("Fetching talk room list...")
    rooms_resp = client.get_talk_rooms()
    rooms = rooms_resp.get("data", {}).get("talkRooms", [])
    print(f"  Found {len(rooms)} talk rooms\n")

    results = []
    for room in rooms:
        room_id = room["id"]
        room_name = room["name"]

        if not room.get("isAccessible"):
            print(f"[skip] {room_name} — subscription required")
            results.append({"room": room_name, "status": "skipped", "count": 0})
            continue

        print(f"[downloading] {room_name} (ID: {room_id})")
        room_dir, total = download_and_save(client, room_id, room_name, room_info=room)
        print(f"  done: {total:,} messages  →  {room_dir}/\n")
        results.append({"room": room_name, "status": "done", "count": total, "dir": room_dir})

    # Print summary
    print("\n========== Download Summary ==========")
    for r in results:
        if r["status"] == "done":
            print(f"  ✓ {r['room']:<14} {r['count']:>5,} messages  →  {r['dir']}/")
        else:
            print(f"  - {r['room']:<14} {r['status']}")


if __name__ == "__main__":
    main()
