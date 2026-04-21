"""
auth.py — equal-love.link authentication module

Handles login and token refresh.
Uses username/password login and refreshToken to renew the accessToken.
"""
import json
import re
from typing import Optional

import requests

AUTH_BASE_URL = "https://api.entertainment-platform-auth.cosm.jp"
AUTH_CACHE_PATH = "auth_cache.json"

_DEFAULT_HEADERS = {
    "user-agent": "io.cosm.fc.user.equal.love/1.3.0/iOS/26.4.1/iPhone",
    "accept-language": "ja",
    "accept-encoding": "gzip",
    "content-type": "application/json",
}


def _build_headers(
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
    authorization: Optional[str] = None,
) -> dict:
    headers = {
        **_DEFAULT_HEADERS,
        "x-request-verification-key": x_request_verification_key,
        "x-artist-group-uuid": x_artist_group_uuid,
        "x-device-uuid": device_uuid,
    }
    if authorization and not _is_placeholder(authorization):
        headers["authorization"] = f"Bearer {authorization}"
    return headers


def _save_config(config: dict, config_path: str) -> None:
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _load_json_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"<.*>", value.strip()))


def _has_value(config: dict, key: str) -> bool:
    value = config.get(key)
    return bool(value) and not _is_placeholder(value)


def validate_auth_config(config: dict) -> None:
    required_fields = [
        "x_request_verification_key",
        "x_artist_group_uuid",
        "x_device_uuid",
    ]
    missing = [field for field in required_fields if not _has_value(config, field)]
    if missing:
        raise ValueError(f"config.json is missing required fields: {', '.join(missing)}")


def load_auth_cache(cache_path: str = AUTH_CACHE_PATH) -> dict:
    try:
        cache = _load_json_file(cache_path)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"{cache_path} is not valid JSON: {e}") from e

    return cache if isinstance(cache, dict) else {}


def _extract_legacy_cache(config: dict) -> dict:
    legacy_cache = {}
    for key in ["authorization", "refresh_token", "user_uuid", "is_verified"]:
        if _has_value(config, key):
            legacy_cache[key] = config[key]
    return legacy_cache


def load_runtime_auth(
    config_path: str = "config.json",
    cache_path: str = AUTH_CACHE_PATH,
) -> dict:
    config = _load_json_file(config_path)
    cache = load_auth_cache(cache_path)
    runtime_auth = {**config, **cache}

    if not cache:
        runtime_auth.update(_extract_legacy_cache(config))

    return runtime_auth


def _extract_auth_payload(result: dict) -> dict:
    payload = result.get("data")
    if isinstance(payload, dict) and "accessToken" in payload:
        return payload
    return result


def _save_auth_payload(payload: dict, cache_path: str) -> str:
    cache = load_auth_cache(cache_path)
    cache["authorization"] = payload["accessToken"]

    if payload.get("refreshToken"):
        cache["refresh_token"] = payload["refreshToken"]
    if payload.get("uuid"):
        cache["user_uuid"] = payload["uuid"]
    if "isVerified" in payload:
        cache["is_verified"] = payload["isVerified"]

    _save_config(cache, cache_path)

    return cache["authorization"]


def login_with_password(
    username: str,
    password: str,
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
    authorization: Optional[str] = None,
) -> dict:
    """Log in with username and password and obtain accessToken and refreshToken."""
    resp = requests.post(
        f"{AUTH_BASE_URL}/login",
        headers=_build_headers(
            device_uuid=device_uuid,
            x_request_verification_key=x_request_verification_key,
            x_artist_group_uuid=x_artist_group_uuid,
            authorization=authorization,
        ),
        json={
            "username": username,
            "password": password,
            "deviceUuid": device_uuid,
        },
    )
    resp.raise_for_status()
    return resp.json()


def login_with_google(
    id_token: str,
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
    authorization: Optional[str] = None,
) -> dict:
    """Log in with a Google ID Token and obtain accessToken and refreshToken

    :param id_token: Google OAuth2 idToken
    :param device_uuid: Device UUID
    :param x_request_verification_key: Request verification key
    :param x_artist_group_uuid: Artist group UUID
    :return: {"accessToken": ..., "refreshToken": ..., "uuid": ..., "isVerified": ...}
    """
    body = {
        "idToken": id_token,
        "createIfNotExists": True,
        "deviceUuid": device_uuid,
    }
    resp = requests.post(
        f"{AUTH_BASE_URL}/login/GOOGLE",
        headers=_build_headers(
            device_uuid=device_uuid,
            x_request_verification_key=x_request_verification_key,
            x_artist_group_uuid=x_artist_group_uuid,
            authorization=authorization,
        ),
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(
    refresh_token: str,
    device_uuid: str,
    x_request_verification_key: str,
    x_artist_group_uuid: str,
    authorization: Optional[str] = None,
) -> dict:
    """Use refreshToken to obtain a new accessToken

    :param refresh_token: refreshToken obtained at login
    :return: {"accessToken": ..., "refreshToken": ..., ...}
    """
    body = {
        "refreshToken": refresh_token,
        "deviceUuid": device_uuid,
    }
    resp = requests.post(
        f"{AUTH_BASE_URL}/token/refresh",
        headers=_build_headers(
            device_uuid=device_uuid,
            x_request_verification_key=x_request_verification_key,
            x_artist_group_uuid=x_artist_group_uuid,
            authorization=authorization,
        ),
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def login_and_save(
    config_path: str = "config.json",
    cache_path: str = AUTH_CACHE_PATH,
) -> str:
    """Log in with username/password from config.json and save tokens to auth_cache.json."""
    config = _load_json_file(config_path)
    cache = load_auth_cache(cache_path)

    username = config.get("username")
    password = config.get("password")
    if not username or not password:
        raise ValueError("config.json must contain username and password for password login")

    validate_auth_config(config)

    result = login_with_password(
        username=username,
        password=password,
        device_uuid=config["x_device_uuid"],
        x_request_verification_key=config["x_request_verification_key"],
        x_artist_group_uuid=config["x_artist_group_uuid"],
        authorization=cache.get("authorization") or config.get("authorization"),
    )

    authorization = _save_auth_payload(
        payload=_extract_auth_payload(result),
        cache_path=cache_path,
    )
    print(f"[auth] Logged in with username/password and saved tokens to {cache_path}")
    return authorization


def refresh_and_save(
    config_path: str = "config.json",
    cache_path: str = AUTH_CACHE_PATH,
) -> str:
    """Refresh the accessToken using the cached refreshToken and save it

    :return: New accessToken
    """
    config = _load_json_file(config_path)
    cache = load_auth_cache(cache_path)
    validate_auth_config(config)
    refresh_token = cache.get("refresh_token") or config.get("refresh_token")
    if not refresh_token:
        raise ValueError(f"{cache_path} is missing refresh_token")

    result = refresh_access_token(
        refresh_token=refresh_token,
        device_uuid=config["x_device_uuid"],
        x_request_verification_key=config["x_request_verification_key"],
        x_artist_group_uuid=config["x_artist_group_uuid"],
        authorization=cache.get("authorization") or config.get("authorization"),
    )

    authorization = _save_auth_payload(
        payload=_extract_auth_payload(result),
        cache_path=cache_path,
    )
    print(f"[auth] Token refreshed and saved to {cache_path}")
    return authorization
