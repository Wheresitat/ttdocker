import time
import requests


class TTLockError(Exception):
    pass


def _build_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"


def register_user(base_url: str, client_id: str, client_secret: str,
                  username: str, password_md5: str) -> dict:
    """
    Calls /v3/user/register to register a TTLock user.

    base_url example:
      - https://api.sciener.com
      - https://api.ttlock.com
      - https://euapi.ttlock.com
    """
    url = _build_url(base_url, "/v3/user/register")
    now_ms = int(time.time() * 1000)

    data = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "username": username,
        "password": password_md5,
        "date": str(now_ms),
    }

    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if not resp.ok:
        raise TTLockError(
            f"Register failed: HTTP {resp.status_code} - {resp.text}"
        )

    try:
        body = resp.json()
    except Exception:
        raise TTLockError(f"Register failed: Non-JSON response: {resp.text}")

    # API usually returns {"username": "xxx"} on success
    if "username" not in body:
        raise TTLockError(f"Register failed: {body}")

    return body


def get_access_token(base_url: str, client_id: str, client_secret: str,
                     username: str, password_md5: str,
                     redirect_uri: str | None = None) -> dict:
    """
    Calls /oauth2/token (password grant) to get access token.

    Docs: https://euopen.ttlock.com/doc/oauth2  :contentReference[oaicite:0]{index=0}
    """
    url = _build_url(base_url, "/oauth2/token")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "password",
        "username": username,
        "password": password_md5,
    }

    if redirect_uri:
        data["redirect_uri"] = redirect_uri

    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if not resp.ok:
        raise TTLockError(
            f"Token failed: HTTP {resp.status_code} - {resp.text}"
        )

    try:
        body = resp.json()
    except Exception:
        raise TTLockError(f"Token failed: Non-JSON response: {resp.text}")

    # Expect access_token, refresh_token, expires_in etc.
    if "access_token" not in body:
        raise TTLockError(f"Token failed: {body}")

    return body
