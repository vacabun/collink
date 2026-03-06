"""
auth.py — equal-love.link authentication module

Handles login and token refresh.
Uses refreshToken to automatically renew the accessToken.
"""
import json

import requests

AUTH_BASE_URL = "https://api.entertainment-platform-auth.cosm.jp"

_DEFAULT_HEADERS = {
    "user-agent": "io.cosm.fc.user.equal.love/1.2.0/iOS/26.3/iPhone",
    "accept-language": "ja",
    "accept-encoding": "gzip",
    "content-type": "application/json",
}


def login_with_google(
    id_token: str,
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
) -> dict:
    """Log in with a Google ID Token and obtain accessToken and refreshToken

    :param id_token: Google OAuth2 idToken
    :param device_uuid: Device UUID
    :param x_request_verification_key: Request verification key
    :param x_artist_group_uuid: Artist group UUID
    :return: {"accessToken": ..., "refreshToken": ..., "uuid": ..., "isVerified": ...}
    """
    headers = {
        **_DEFAULT_HEADERS,
        "x-request-verification-key": x_request_verification_key,
        "x-artist-group-uuid": x_artist_group_uuid,
        "x-device-uuid": device_uuid,
        "authorization": "Bearer ",
    }
    body = {
        "idToken": id_token,
        "createIfNotExists": True,
        "deviceUuid": device_uuid,
    }
    resp = requests.post(
        f"{AUTH_BASE_URL}/login/GOOGLE",
        headers=headers,
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(
    refresh_token: str,
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
) -> dict:
    """Use refreshToken to obtain a new accessToken

    :param refresh_token: refreshToken obtained at login
    :return: {"accessToken": ..., "refreshToken": ..., ...}
    """
    headers = {
        **_DEFAULT_HEADERS,
        "x-request-verification-key": x_request_verification_key,
        "x-artist-group-uuid": x_artist_group_uuid,
        "x-device-uuid": device_uuid,
        "authorization": "Bearer ",
    }
    body = {
        "refreshToken": refresh_token,
        "deviceUuid": device_uuid,
    }
    resp = requests.post(
        f"{AUTH_BASE_URL}/token/refresh",
        headers=headers,
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_and_save(config_path: str = "config.json") -> str:
    """Refresh the accessToken using the refreshToken in config.json and save it

    :return: New accessToken
    """
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    result = refresh_access_token(
        refresh_token=config["refresh_token"],
        device_uuid=config["x_device_uuid"],
        x_request_verification_key=config["x_request_verification_key"],
        x_artist_group_uuid=config["x_artist_group_uuid"],
    )

    config["authorization"] = result["accessToken"]
    # Update refreshToken if the server returns a new one
    if "refreshToken" in result:
        config["refresh_token"] = result["refreshToken"]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print("[auth] Token refreshed and saved to config.json")
    return config["authorization"]
