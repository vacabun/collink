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

from src.auth import load_runtime_auth
from src.equal_love_client import EqualLoveClient

# Output directory
OUTPUT_DIR = "messages"
# Delay between requests (seconds) to avoid hammering the server
REQUEST_INTERVAL = 0.5
PROGRESS_BAR_WIDTH = 24
_SPINNER_FRAMES = ("|", "/", "-", "\\")


def load_config(path: str = "config.json") -> dict:
    """Load runtime credentials from config.json plus auth_cache.json if present."""
    return load_runtime_auth(config_path=path)


def _room_dir(talk_room_id: int, room_name: str) -> str:
    safe_name = room_name.replace(" ", "_").replace("/", "-")
    return os.path.join(OUTPUT_DIR, f"{talk_room_id:02d}_{safe_name}")


def _progress_bar(current: int, total: int, width: int = PROGRESS_BAR_WIDTH) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"

    filled = int(width * current / total)
    if current > 0:
        filled = max(1, filled)
    filled = min(width, filled)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _print_subscription_overview(rooms: list[dict]) -> list[dict]:
    accessible_rooms = [room for room in rooms if room.get("isAccessible")]
    locked_rooms = [room for room in rooms if not room.get("isAccessible")]

    print("Subscribed / accessible rooms:")
    if accessible_rooms:
        for index, room in enumerate(accessible_rooms, start=1):
            print(f"  {index:>2}. {room['name']} (ID: {room['id']})")
    else:
        print("   none")

    if locked_rooms:
        print("\nLocked rooms:")
        for room in locked_rooms:
            print(f"  - {room['name']}")

    print("")
    return accessible_rooms


def _render_room_progress(
    room_index: int,
    total_rooms: int,
    room_name: str,
    page_num: int,
    total_messages: int,
    media_total: int,
    next_page_id: int,
    done: bool = False,
) -> None:
    completed_rooms = room_index - 1 + int(done)
    bar = _progress_bar(completed_rooms, total_rooms)
    spinner = "done" if done else _SPINNER_FRAMES[(page_num - 1) % len(_SPINNER_FRAMES)]
    status = (
        f"\r  {bar} room {min(room_index, total_rooms):>2}/{total_rooms:<2} {spinner} "
        f"{room_name} | page {page_num:<3} | messages {total_messages:<6} "
        f"| media {media_total:<4} | nextPageId {next_page_id:<8}"
    )
    print(status, end="" if not done else "\n", flush=True)


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
    room_index: int = 1,
    total_rooms: int = 1,
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
                    else:
                        media["localPath"] = os.path.join("media", filename)
                    media_total += 1
                # Append to JSON array
                if not first_msg:
                    f.write(",\n")
                f.write(json.dumps(msg, ensure_ascii=False, indent=2))
                first_msg = False

            f.flush()
            total += len(data)
            next_page_id = resp.get("nextPageId", 0)
            _render_room_progress(
                room_index=room_index,
                total_rooms=total_rooms,
                room_name=room_name,
                page_num=page_num,
                total_messages=total,
                media_total=media_total,
                next_page_id=next_page_id,
            )

            if next_page_id == 0:
                break

            page_num += 1
            time.sleep(REQUEST_INTERVAL)

        f.write("\n]\n")

    _render_room_progress(
        room_index=room_index,
        total_rooms=total_rooms,
        room_name=room_name,
        page_num=page_num,
        total_messages=total,
        media_total=media_total,
        next_page_id=0,
        done=True,
    )
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
    accessible_rooms = _print_subscription_overview(rooms)
    total_accessible = len(accessible_rooms)

    results = []
    accessible_index = 0
    for room in rooms:
        room_id = room["id"]
        room_name = room["name"]

        if not room.get("isAccessible"):
            print(f"[skip] {room_name} — subscription required")
            results.append({"room": room_name, "status": "skipped", "count": 0})
            continue

        accessible_index += 1
        print(f"[downloading] {room_name} (ID: {room_id})")
        room_dir, total = download_and_save(
            client,
            room_id,
            room_name,
            room_info=room,
            room_index=accessible_index,
            total_rooms=total_accessible,
        )
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
