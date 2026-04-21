import json
import sys
from requests import HTTPError
from src.auth import AUTH_CACHE_PATH, load_runtime_auth, login_and_save, refresh_and_save, validate_auth_config
from src.collink import main


def _load_config(path: str = "config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _retry_download() -> None:
    print("[retry] Retrying download...\n")
    main()
    sys.exit(0)


def _try_password_login() -> None:
    print("[auth] Trying username/password login...")
    login_and_save()
    _retry_download()


if __name__ == "__main__":
    try:
        config = _load_config()
        validate_auth_config(config)
        runtime_auth = load_runtime_auth()
        if not runtime_auth.get("authorization"):
            print(f"\n[auth] Access token missing in {AUTH_CACHE_PATH}. Trying username/password login...")
            _try_password_login()
        main()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"\n[error] Invalid config: {e}")
        sys.exit(1)
    except HTTPError as e:
        if e.response.status_code == 401:
            print("\n[auth] Token expired — refreshing with refreshToken...")
            try:
                refresh_and_save()
                _retry_download()
            except (HTTPError, KeyError, ValueError) as re:
                print("[auth] Refresh failed. Falling back to username/password login...")
                try:
                    _try_password_login()
                except HTTPError as le:
                    status = le.response.status_code if le.response is not None else "unknown"
                    print(f"[error] Login failed ({status}).")
                except (KeyError, ValueError) as le:
                    print(f"[error] Login failed: {le}")
        else:
            print(f"\n[error] HTTP {e.response.status_code}: {e}")
        sys.exit(1)
