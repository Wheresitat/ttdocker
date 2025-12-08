import json
import os
import hashlib
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template, request

from ttlock_api import register_user, get_access_token, TTLockError

app = Flask(__name__)
app.secret_key = "change-this-secret"

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/data/config.json"))
LOG_PATH = Path(os.environ.get("LOG_PATH", "/data/app.log"))

# --------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------
logger = logging.getLogger("ttlock_helper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_event(message: str, level: int = logging.INFO) -> None:
    logger.log(level, message)


def get_log_tail(lines: int = 200) -> str:
    if not LOG_PATH.exists():
        return ""
    try:
        with LOG_PATH.open("r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except Exception:
        return ""
    return "".join(all_lines[-lines:])


# --------------------------------------------------------------------
# Config helpers
# --------------------------------------------------------------------
def default_config() -> dict:
    # Default API URL is https://api.ttlock.com
    return {
        "api_base_url": "https://api.ttlock.com",
        "redirect_uri": "",
        "client_id": "",
        "client_secret": "",
        "username": "",
        "password_md5": "",
        "last_date_ms": "",
        "access_token": "",
        "refresh_token": "",
        "raw_register_response": "",
        "raw_token_response": "",
    }


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            log_event("Failed to read config file, using defaults", logging.WARNING)
            data = default_config()
    else:
        data = default_config()

    base = default_config()
    base.update(data)
    return base


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# --------------------------------------------------------------------
# Curl builder for /v3/user/register
# --------------------------------------------------------------------
def build_curl_example(cfg: dict) -> str:
    """
    Build a curl command for /v3/user/register using current config.
    Only returns a non-empty string if all required fields are present.
    """
    required = ["client_id", "client_secret", "username", "password_md5", "last_date_ms"]
    if not all(cfg.get(k) for k in required):
        return ""

    base_url = cfg.get("api_base_url", "https://api.ttlock.com").rstrip("/")
    url = f"{base_url}/v3/user/register"

    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    username = cfg["username"]
    password_md5 = cfg["password_md5"]
    date_ms = cfg["last_date_ms"]

    curl = (
        "curl --location -g --request POST '{url}' \\\n"
        "  --header 'Content-Type: application/x-www-form-urlencoded' \\\n"
        "  --data-urlencode 'clientId={client_id}' \\\n"
        "  --data-urlencode 'clientSecret={client_secret}' \\\n"
        "  --data-urlencode 'username={username}' \\\n"
        "  --data-urlencode 'password={password}' \\\n"
        "  --data-urlencode 'date={date}'"
    ).format(
        url=url,
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password_md5,
        date=date_ms,
    )

    return curl


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    cfg = load_config()
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()
    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password="",
        register_error="",
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/hash_password", methods=["POST"])
def hash_password_route():
    cfg = load_config()

    username = request.form.get("username", "").strip()
    plain = request.form.get("plain_password", "").strip()

    if username:
        cfg["username"] = username

    hashed = cfg.get("password_md5", "")
    if plain:
        hashed = hashlib.md5(plain.encode("utf-8")).hexdigest()
        cfg["password_md5"] = hashed
        log_event(f"Generated MD5 hash for username '{cfg['username']}'")

    # Generate current date in ms for use in curl / register
    now_ms = int(time.time() * 1000)
    cfg["last_date_ms"] = str(now_ms)
    log_event(f"Generated date ms: {cfg['last_date_ms']}")

    save_config(cfg)
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=hashed,
        register_error="",
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    cfg = load_config()

    cfg["api_base_url"] = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    cfg["redirect_uri"] = request.form.get("redirect_uri", "").strip()
    cfg["client_id"] = request.form.get("client_id", "").strip()
    cfg["client_secret"] = request.form.get("client_secret", "").strip()

    save_config(cfg)
    log_event("Settings updated (API base URL, redirect URI, client credentials)")

    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password="",
        register_error="Settings saved.",
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/register_user", methods=["POST"])
def register_user_route():
    cfg = load_config()

    api_base_url = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    cfg["api_base_url"] = api_base_url

    register_error = ""
    register_resp_raw = ""

    if not (cfg["client_id"] and cfg["client_secret"] and cfg["username"] and cfg["password_md5"]):
        register_error = "Missing required fields (client_id, client_secret, username, password_md5)."
        log_event(f"Register user aborted: {register_error}", logging.WARNING)
    else:
        log_event(f"Attempting to register user '{cfg['username']}'")
        try:
            result = register_user(
                base_url=cfg["api_base_url"],
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                username=cfg["username"],
                password_md5=cfg["password_md5"],
            )
            cfg["username"] = result.get("username", cfg["username"])
            register_resp_raw = json.dumps(result, indent=2)
            log_event(f"User registered successfully, returned username: {cfg['username']}")
        except TTLockError as e:
            register_error = str(e)
            log_event(f"TTLockError during register_user: {register_error}", logging.ERROR)
        except Exception as e:
            register_error = f"Unexpected error: {e}"
            log_event(register_error, logging.ERROR)

    cfg["raw_register_response"] = register_resp_raw
    save_config(cfg)
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error=register_error,
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/get_token", methods=["POST"])
def get_token_route():
    cfg = load_config()

    api_base_url = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    redirect_uri = request.form.get("redirect_uri", "").strip() or cfg["redirect_uri"]

    cfg["api_base_url"] = api_base_url
    cfg["redirect_uri"] = redirect_uri

    token_error = ""
    token_resp_raw = ""

    if not (cfg["client_id"] and cfg["client_secret"] and cfg["username"] and cfg["password_md5"]):
        token_error = "Missing required fields (client_id, client_secret, username, password_md5)."
        log_event(f"Get token aborted: {token_error}", logging.WARNING)
    else:
        log_event(f"Attempting to get access token for user '{cfg['username']}'")
        try:
            result = get_access_token(
                base_url=cfg["api_base_url"],
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                username=cfg["username"],
                password_md5=cfg["password_md5"],
                redirect_uri=cfg["redirect_uri"],
            )
            cfg["access_token"] = result.get("access_token", "")
            cfg["refresh_token"] = result.get("refresh_token", "")
            token_resp_raw = json.dumps(result, indent=2)
            log_event("Access token retrieved successfully")
        except TTLockError as e:
            token_error = str(e)
            log_event(f"TTLockError during get_access_token: {token_error}", logging.ERROR)
        except Exception as e:
            token_error = f"Unexpected error: {e}"
            log_event(token_error, logging.ERROR)

    cfg["raw_token_response"] = token_resp_raw
    save_config(cfg)
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error="",
        token_error=token_error,
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
