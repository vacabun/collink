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
| `X-Request-Verification-Key` | Per-device request signing key (`rvk_...`) |
| `X-Artist-Group-UUID` | Identifies which artist's fan club |
| `X-Device-UUID` | Identifies the device (`ios_...`) |

Login is done via Google OAuth2: the app sends a Google `idToken` to `/login/GOOGLE` and receives an `accessToken` + `refreshToken` pair. When the access token expires, the refresh token can be used to get a new one.

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
├── config.json              # Your credentials (git-ignored)
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

Open the equal-love.link app on your phone while running a packet capture (e.g. [Proxyman](https://proxyman.io) or [mitmproxy](https://mitmproxy.org)). Look for any authenticated request and extract the four headers listed above.

### 3. Create `config.json`

Copy the template and fill in your values:

```bash
cp config.template.json config.json
```

```json
{
  "authorization": "<JWT access token (the string after Bearer)>",
  "refresh_token": "<refresh token obtained at login>",
  "x_request_verification_key": "<rvk_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX>",
  "x_artist_group_uuid": "<XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX>",
  "x_device_uuid": "<ios_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX>"
}
```

`config.json` is listed in `.gitignore` and will never be committed.

### 4. Run

```bash
python main.py
```

The script will:
1. Fetch all talk rooms
2. Skip rooms that require a subscription you don't have (`isAccessible: false`)
3. Download all messages page by page for each accessible room
4. Download all media files (images, videos) into `media/`
5. Save everything under `messages/{id}_{room_name}/`

Progress is printed per page:

```
[downloading] 大谷 映美里 (ID: 1)
  page   1  messages:    50  media:   12  nextPageId: 347766
  page   2  messages:   100  media:   23  nextPageId: 302541
  ...
  done: 3,842 messages  →  messages/01_大谷 映美里/
```

### Token expiry

If the JWT is expired, `main.py` catches the `401` error and automatically calls `refresh_and_save()` to get a new token using the stored `refresh_token`, then prompts you to re-run. If the refresh token is also expired, you'll need to capture a fresh token from the app.

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
| `POST` | `/login/GOOGLE` | Login with Google idToken |
| `POST` | `/token/refresh` | Refresh access token |

---

## Notes

- Requests are throttled to one every 0.5 seconds (`REQUEST_INTERVAL`) to avoid hammering the server.
- Media files are skipped if they already exist locally (safe to re-run after interruption).
- The tool only reads data — it never posts, likes, or modifies anything.
