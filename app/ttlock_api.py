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
    /v3/user/register
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

    if "username" not in body:
        raise TTLockError(f"Register failed: {body}")

    return body


def get_access_token(base_url: str, client_id: str, client_secret: str,
                     username: str, password_md5: str,
                     redirect_uri: str | None = None) -> dict:
    """
    /oauth2/token (grant_type=password)
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

    if "access_token" not in body:
        raise TTLockError(f"Token failed: {body}")

    return body


def list_locks(base_url: str, access_token: str,
               page_no: int = 1, page_size: int = 100) -> dict:
    """
    /v3/lock/list

    Returns:
    {
      "list": [
        {
          "lockId": 123456,
          "lockAlias": "Front Door",
          "electricQuantity": 95,
          ...
        },
        ...
      ]
    }
    """
    url = _build_url(base_url, "/v3/lock/list")
    now_ms = int(time.time() * 1000)

    data = {
        "accessToken": access_token,
        "pageNo": page_no,
        "pageSize": page_size,
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
            f"Lock list failed: HTTP {resp.status_code} - {resp.text}"
        )

    try:
        body = resp.json()
    except Exception:
        raise TTLockError(f"Lock list failed: Non-JSON response: {resp.text}")

    if "list" not in body:
        raise TTLockError(f"Lock list failed: {body}")

    return body


def operate_lock(base_url: str, access_token: str,
                 lock_id: int, action: str) -> dict:
    """
    /v3/lock/lock or /v3/lock/unlock
    """
    action = action.lower()
    if action not in ("lock", "unlock"):
        raise TTLockError(f"Invalid action: {action}")

    path = "/v3/lock/lock" if action == "lock" else "/v3/lock/unlock"
    url = _build_url(base_url, path)
    now_ms = int(time.time() * 1000)

    data = {
        "accessToken": access_token,
        "lockId": int(lock_id),
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
            f"{action.capitalize()} failed: HTTP {resp.status_code} - {resp.text}"
        )

    try:
        body = resp.json()
    except Exception:
        raise TTLockError(f"{action.capitalize()} failed: Non-JSON response: {resp.text}")

    return body
