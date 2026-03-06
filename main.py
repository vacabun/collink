import sys
from requests import HTTPError
from src.auth import refresh_and_save
from src.collink import main

if __name__ == "__main__":
    try:
        main()
    except HTTPError as e:
        if e.response.status_code == 401:
            print("\n[auth] Token expired — refreshing with refreshToken...")
            try:
                refresh_and_save()
                print("[retry] Run again: python main.py\n")
            except HTTPError as re:
                print(f"[error] Token refresh failed ({re.response.status_code}).")
                print("  refreshToken may also be expired. Please log in again.")
        else:
            print(f"\n[error] HTTP {e.response.status_code}: {e}")
        sys.exit(1)
