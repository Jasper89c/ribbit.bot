# esi_auth.py

import os
import aiohttp
import asyncio
import base64

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net/latest"

_session: aiohttp.ClientSession | None = None
_access_token: str | None = None
_lock = asyncio.Lock()


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def refresh_access_token() -> str:
    global _access_token
    async with _lock:
        # Double‑check inside lock
        if _access_token is not None:
            return _access_token

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

        session = await get_session()
        async with session.post(TOKEN_URL, headers=headers, data=data) as r:
            r.raise_for_status()
            js = await r.json()
            _access_token = js["access_token"]
            return _access_token


async def get_access_token() -> str:
    global _access_token
    if _access_token is None:
        return await refresh_access_token()
    return _access_token


async def esi_get(path: str, params: dict | None = None, retries: int = 8):
    """
    Async ESI GET with retry, backoff, and token refresh.
    path: '/corporations/...'
    """
    url = f"{ESI_BASE}{path}"
    backoff = 1

    for _ in range(retries):
        token = await get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        session = await get_session()
        try:
            async with session.get(url, headers=headers, params=params, timeout=20) as r:
                status = r.status

                if status == 200:
                    return await r.json()

                if status == 401:
                    # token expired → refresh and retry
                    _ = await refresh_access_token()
                    continue

                if status == 404:
                    return None

                if status in (420, 429):
                    wait = int(r.headers.get("X-Esi-Error-Limit-Reset", "5"))
                    await asyncio.sleep(wait)
                    continue

                if status in (500, 503, 520):
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue

                # Other errors: log and bail
                text = await r.text()
                print(f"ESI error {status} for {url}: {text}")
                return None

        except asyncio.TimeoutError:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

    print(f"ESI failed after {retries} retries for {url}")
    return None


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
