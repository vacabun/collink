import requests

# API base URL
BASE_URL = "https://v3.api.equal-love.link.cosm.jp"

# Default request headers
_DEFAULT_HEADERS = {
    "user-agent": "io.cosm.fc.user.equal.love/1.2.0/iOS/26.3/iPhone",
    "accept-language": "ja",
    "accept-encoding": "gzip",
    "host": "v3.api.equal-love.link.cosm.jp",
}


class EqualLoveClient:
    """equal-love.link (cosm) fan club API client"""

    def __init__(
        self,
        authorization: str,
        x_request_verification_key: str,
        x_artist_group_uuid: str,
        x_device_uuid: str,
    ):
        """
        :param authorization: JWT access token (without "Bearer " prefix)
        :param x_request_verification_key: Request verification key (e.g. rvk_XXXXXXXX)
        :param x_artist_group_uuid: Artist group UUID
        :param x_device_uuid: Device UUID (e.g. ios_XXXXXXXX)
        """
        self.device_uuid = x_device_uuid
        self.session = requests.Session()
        self.session.headers.update({
            **_DEFAULT_HEADERS,
            "authorization": f"Bearer {authorization}",
            "x-request-verification-key": x_request_verification_key,
            "x-artist-group-uuid": x_artist_group_uuid,
            "x-device-uuid": x_device_uuid,
        })

    # ------------------------------------------------------------------
    # GET /user/v2/talk-room
    # ------------------------------------------------------------------
    def get_talk_rooms(self, page: int = 1) -> dict:
        """Fetch the list of talk rooms (includes artist info, unread count, etc.)

        :param page: Page number (default: 1)
        :return: API response JSON. data.talkRooms contains the room list.
        """
        resp = self.session.get(
            f"{BASE_URL}/user/v2/talk-room",
            params={"page": page},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # GET /user/v1/campaign
    # ------------------------------------------------------------------
    def get_campaign(self) -> dict:
        """Fetch current campaign info (no parameters)

        :return: API response JSON. data contains campaign details.
        """
        resp = self.session.get(f"{BASE_URL}/user/v1/campaign")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # GET /user/v1/alarms/list/{device_uuid}
    # ------------------------------------------------------------------
    def get_alarms(self, device_uuid: str = None) -> dict:
        """Fetch the alarm settings list for a device

        :param device_uuid: Device UUID. Uses the value from __init__ if None.
        :return: API response JSON. data contains the alarm settings list.
        """
        uuid = device_uuid or self.device_uuid
        resp = self.session.get(f"{BASE_URL}/user/v1/alarms/list/{uuid}")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # GET /user/v2/chat/{talk_room_id}
    # ------------------------------------------------------------------
    def get_chat(
        self,
        talk_room_id: int,
        page: int = 1,
        page_size: int = 25,
        has_media: bool = False,
        is_favorite: bool = False,
        is_sent_fan_letter: bool = False,
        date_search_in_secs: int = 0,
        page_start_id: int = 0,
        order_by: int = 1,
    ) -> dict:
        """Fetch the message list for a specific talk room

        :param talk_room_id: Talk room ID
        :param page: Page number (default: 1)
        :param page_size: Items per page (default: 25)
        :param has_media: Only return messages with media (default: False)
        :param is_favorite: Only return favorited messages (default: False)
        :param is_sent_fan_letter: Only return sent fan letters (default: False)
        :param date_search_in_secs: Search start point in Unix seconds (default: 0)
        :param page_start_id: Pagination cursor. Pass nextPageId from previous response (default: 0)
        :param order_by: Sort order (default: 1)
        :return: API response JSON. data contains the message list.
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "hasMedia": str(has_media).lower(),
            "isFavorite": str(is_favorite).lower(),
            "isSentFanLetter": str(is_sent_fan_letter).lower(),
            "dateSearchInSecs": date_search_in_secs,
            "pageStartId": page_start_id,
            "orderBy": order_by,
        }
        resp = self.session.get(
            f"{BASE_URL}/user/v2/chat/{talk_room_id}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
