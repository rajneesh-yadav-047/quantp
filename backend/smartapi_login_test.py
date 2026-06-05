import os
import json
import sys
import requests
from dotenv import load_dotenv

load_dotenv()


def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_totp() -> str:
    return input("Enter current TOTP: ").strip()


def main() -> int:
    try:
        client_code = get_env("SMARTAPI_CLIENT_CODE")
        password = get_env("SMARTAPI_PASSWORD")
        totp = get_totp()
        api_key = get_env("SMARTAPI_API_KEY")
    except RuntimeError as exc:
        print(str(exc))
        return 2

    url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
    payload = {
        "clientcode": client_code,
        "password": password,
        "totp": totp,
        "state": "local_test"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": os.getenv("SMARTAPI_CLIENT_LOCAL_IP", "127.0.0.1"),
        "X-ClientPublicIP": os.getenv("SMARTAPI_CLIENT_PUBLIC_IP", "127.0.0.1"),
        "X-MACAddress": os.getenv("SMARTAPI_MAC_ADDRESS", "00:00:00:00:00:00"),
        "X-PrivateKey": api_key,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
    except Exception as exc:
        print(f"Request failed: {exc}")
        return 1

    print(json.dumps({"status_code": response.status_code, "response": data}, indent=2))

    if response.ok and data.get("status") is True:
        print("Login succeeded.")
        return 0

    print("Login failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
