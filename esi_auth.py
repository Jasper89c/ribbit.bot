# esi_auth.py

import base64
import time
import requests
import os

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")


TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net/latest"

SESSION = requests.Session()


def get_access_token():
    """Exchange refresh token for a new access token."""
    pair = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded = base64.b64encode(pair.encode("ascii")).decode("ascii")

    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }

    r = requests.post(TOKEN_URL, headers=headers, data=data)
    r.raise_for_status()
    token = r.json()["access_token"]

    SESSION.headers.update({"Authorization": f"Bearer {token}"})
    return token


def esi_get(url, params=None, retries=10):
    """Bulletproof ESI GET with retry, backoff, and token refresh."""
    backoff = 1

    for attempt in range(retries):
        r = SESSION.get(url, params=params)

        if r.status_code == 200:
            return r.json()

        if r.status_code == 401:
            get_access_token()
            continue

        if r.status_code == 404:
            return None

        if r.status_code in (420, 429):
            wait = int(r.headers.get("X-Esi-Error-Limit-Reset", 5))
            time.sleep(wait)
            continue

        if r.status_code in (500, 503, 520):
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        return None

    return None
