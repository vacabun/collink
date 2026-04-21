# collink

A archival tool for downloading all messages and media from [＝LOVE LINK](https://equal-love.link.cosm.jp/). **"collink" = clone link.**

---

## How it works

### Platform overview

＝LOVE LINK is a fan club platform. Artists host private "talk rooms" where fans can receive messages, photos, and videos via a subscription. The mobile app communicates with a REST API at:

```
https://v3.api.equal-love.link.cosm.jp
```

Authentication is handled by a separate service:

```
https://api.entertainment-platform-auth.cosm.jp
```

### Authentication

The app uses **JWT Bearer tokens** with a short expiry (~2 weeks). Every request requires four headers:

| Header | Description |
|---|---|
| `Authorization` | `Bearer <JWT access token>` |
| `X-Request-Verification-Key` | Per-device request verification key (`rvk_...`) |
| `X-Artist-Group-UUID` | Identifies which artist's fan club |
| `X-Device-UUID` | Identifies the device (`ios_...`) |

Login is done via username/password: the app sends `username`, `password`, and `deviceUuid` to `/login` and receives an `accessToken` + `refreshToken` pair. When the access token expires, the refresh token can be used to get a new one. If refresh also fails, this tool can log in again with the saved username/password and write the new tokens to `auth_cache.json`.

The tokens are stored in a separate local cache file, `auth_cache.json`, instead of `config.json`. On the first successful login, the tool creates this cache automatically and reuses it on later runs.

If the cache does not contain an `authorization` token, the login request does not send an `Authorization` header at all. If a cached token exists, it is sent as `Bearer <token>`.

### Pagination

The chat API uses **cursor-based pagination**, not page-number-based. The response includes a `nextPageId` field. To fetch the next page, pass `pageStartId=<nextPageId>` with `page=1`. When `nextPageId` is `0`, all messages have been retrieved.

```
GET /user/v2/chat/{talk_room_id}?page=1&pageSize=50&pageStartId=<cursor>
```

### Media

Message attachments (images, videos) are served from a Google Cloud Storage CDN via signed URLs embedded in the API response. These URLs are publicly accessible for a limited time — no auth header needed.

---

## Project structure

```
equal-love-helper/
├── main.py                  # Entry point; handles 401 auto-refresh
├── config.json              # Static login/device config (git-ignored)
├── auth_cache.json          # Generated token cache (git-ignored)
├── config.template.json     # Credential template to commit
├── src/
│   ├── equal_love_client.py # API client (talk rooms, chat, alarms)
│   ├── collink.py           # Download orchestrator (messages + media)
│   └── auth.py              # Login and token refresh
└── messages/                # Downloaded output (git-ignored)
    └── {id}_{room_name}/
        ├── info.json        # Talk room metadata
        ├── messages.json    # All messages with localPath added
        └── media/           # Downloaded images and videos
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests
```

### 2. Get your credentials

Open the equal-love.link app on your phone while running a packet capture (e.g. [Proxyman](https://proxyman.io) or [mitmproxy](https://mitmproxy.org)). Look for the login request:

- From `POST /login`, extract `username` and `password`
- From authenticated requests, extract `x_request_verification_key` and `x_artist_group_uuid`
- `x_device_uuid` is generated automatically at runtime; you do not need to capture or store it

### 3. Create `config.json`

Copy the template and fill in your values:

```bash
cp config.template.json config.json
```

```json
{
  "username": "<login username or email>",
  "password": "<login password>",
  "x_request_verification_key": "<required request verification key>",
  "x_artist_group_uuid": "<required artist group UUID>"
}
```

`config.json` is listed in `.gitignore` and will never be committed.

`x_device_uuid` is generated in memory for the current run. A fresh value is created when password login happens, and the same value is reused for the rest of that run.

`authorization` and `refresh_token` no longer need to be stored in `config.json`. After the first successful login, they are written to `auth_cache.json`.

### 4. Run

```bash
python3 main.py
```

The script will:
1. Fetch all talk rooms
2. Print which rooms are currently accessible to your account
3. Skip rooms that require a subscription you don't have (`isAccessible: false`)
4. Download all messages page by page for each accessible room
5. Download all media files (images, videos) into `media/`
6. Save everything under `messages/{id}_{room_name}/`

Before downloading, it prints an overview like:

```
Subscribed / accessible rooms:
   1. 大谷 映美里 (ID: 1)
   2. 佐々木 舞香 (ID: 2)

Locked rooms:
  - 野口 衣織
```

### Token expiry

If the JWT is expired, `main.py` catches the `401` error and automatically calls `refresh_and_save()` to get a new token using the cached `refresh_token`, then retries the download. If the refresh token is also expired, it falls back to username/password login, saves the new tokens to `auth_cache.json`, and retries again.

During download, progress is shown as a terminal status line for the overall room queue plus the live state of the current room:

```
[########----------------] room  1/3  / 大谷 映美里 | page 2   | messages 100    | media 23   | nextPageId 302541
```

This is an activity/status indicator rather than a true per-room percentage, because the API does not expose the total number of messages in a room up front.

---

## Output format

### `messages.json`

A standard JSON array of message objects as returned by the API, with two fields added by this tool:

- `postedDateStr` — human-readable timestamp in JST, e.g. `"2025-03-01 12:34:56 JST"`
- `chatMedia[].localPath` — relative path to the downloaded file, e.g. `"media/12345.jpg"`

### `info.json`

The talk room metadata object exactly as returned by the `/user/v2/talk-room` endpoint.

---

## API endpoints used

| Method | Path | Description |
|---|---|---|
| `GET` | `/user/v2/talk-room` | List all talk rooms |
| `GET` | `/user/v2/chat/{id}` | Fetch messages for a room (paginated) |
| `GET` | `/user/v1/campaign` | Current campaign info |
| `GET` | `/user/v1/alarms/list/{device_uuid}` | Alarm/notification settings |
| `POST` | `/login` | Login with username/password |
| `POST` | `/token/refresh` | Refresh access token |

---

## Notes

- Requests are throttled to one every 0.5 seconds (`REQUEST_INTERVAL`) to avoid hammering the server.
- Media files are skipped if they already exist locally (safe to re-run after interruption).
- The tool only reads data — it never posts, likes, or modifies anything.
