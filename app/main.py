import json
import os
import hashlib
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template, request, jsonify

from ttlock_api import (
    register_user,
    get_access_token,
    list_locks,
    operate_lock,
    TTLockError,
)

app = Flask(__name__)
app.secret_key = "change-this-secret"

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/data/config.json"))
LOG_PATH = Path(os.environ.get("LOG_PATH", "/data/app.log"))

# --------------------------------------------------------------------
# Logging
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
        "locks": [],
        "last_lock_error": "",
        "last_lock_action_result": "",
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
# Routes – UI
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

    try:
        cfg["api_base_url"] = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
        cfg["redirect_uri"] = request.form.get("redirect_uri", "").strip()
        cfg["client_id"] = request.form.get("client_id", "").strip()
        cfg["client_secret"] = request.form.get("client_secret", "").strip()

        save_config(cfg)
        log_event("Settings updated (API base URL, redirect URI, client credentials)")
        status_msg = "Settings saved."
    except Exception as e:
        status_msg = f"Error saving settings: {e}"
        log_event(status_msg, logging.ERROR)

    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password="",
        register_error=status_msg,
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
            register_error = f"Register failed: {e}"
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
            token_error = f"Token failed: {e}"
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


@app.route("/fetch_locks", methods=["POST"])
def fetch_locks_route():
    cfg = load_config()

    lock_error = ""
    if not cfg.get("access_token"):
        lock_error = "No access token available. Complete Steps 1–4 or use the Shortcut."
        log_event(f"Fetch locks aborted: {lock_error}", logging.WARNING)
    else:
        log_event("Attempting to fetch lock list from TTLock")
        try:
            result = list_locks(
                base_url=cfg["api_base_url"],
                access_token=cfg["access_token"],
            )
            locks = result.get("list", [])
            cfg["locks"] = locks
            cfg["last_lock_error"] = ""
            log_event(f"Fetched {len(locks)} locks from TTLock")
        except TTLockError as e:
            lock_error = f"Lock list failed: {e}"
            cfg["last_lock_error"] = lock_error
            log_event(lock_error, logging.ERROR)
        except Exception as e:
            lock_error = f"Unexpected error: {e}"
            cfg["last_lock_error"] = lock_error
            log_event(lock_error, logging.ERROR)

    save_config(cfg)
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error=lock_error,
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/control_lock", methods=["POST"])
def control_lock_route():
    cfg = load_config()

    lock_id = request.form.get("lock_id", "").strip()
    action = request.form.get("action", "").strip().lower()

    action_error = ""
    result_text = ""

    if not cfg.get("access_token"):
        action_error = "No access token available. Complete token step or fast setup first."
        log_event(f"Control lock aborted: {action_error}", logging.WARNING)
    elif not lock_id:
        action_error = "No lock selected."
        log_event(f"Control lock aborted: {action_error}", logging.WARNING)
    elif action not in ("lock", "unlock"):
        action_error = f"Invalid action '{action}'."
        log_event(f"Control lock aborted: {action_error}", logging.WARNING)
    else:
        log_event(f"Attempting to {action} lock {lock_id}")
        try:
            result = operate_lock(
                base_url=cfg["api_base_url"],
                access_token=cfg["access_token"],
                lock_id=int(lock_id),
                action=action,
            )
            result_text = json.dumps(result, indent=2)
            action_error = ""
            log_event(f"{action.capitalize()} command sent successfully for lock {lock_id}")
        except TTLockError as e:
            action_error = f"{action.capitalize()} failed: {e}"
            result_text = ""
            log_event(action_error, logging.ERROR)
        except Exception as e:
            action_error = f"Unexpected error: {e}"
            result_text = ""
            log_event(action_error, logging.ERROR)

    cfg["last_lock_error"] = action_error
    cfg["last_lock_action_result"] = result_text
    save_config(cfg)

    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error=action_error,
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


@app.route("/fast_setup", methods=["POST"])
def fast_setup_route():
    """
    Shortcut: user already has username/password/token and wants to jump to locks.
    """
    cfg = load_config()

    base_url = request.form.get("fast_api_base_url", "").strip() or cfg["api_base_url"]
    username = request.form.get("fast_username", "").strip()
    plain_password = request.form.get("fast_plain_password", "").strip()
    password_md5 = request.form.get("fast_password_md5", "").strip()
    access_token = request.form.get("fast_access_token", "").strip()
    refresh_token = request.form.get("fast_refresh_token", "").strip()

    cfg["api_base_url"] = base_url

    if username:
        cfg["username"] = username

    # If given plain password, override MD5
    if plain_password:
        password_md5 = hashlib.md5(plain_password.encode("utf-8")).hexdigest()
        log_event(f"Fast setup: generated MD5 hash for username '{cfg['username']}'")

    if password_md5:
        cfg["password_md5"] = password_md5

    if access_token:
        cfg["access_token"] = access_token

    if refresh_token:
        cfg["refresh_token"] = refresh_token

    message = ""
    error = ""

    if cfg.get("access_token"):
        log_event("Fast setup: attempting to verify access token by fetching locks")
        try:
            result = list_locks(
                base_url=cfg["api_base_url"],
                access_token=cfg["access_token"],
            )
            cfg["locks"] = result.get("list", [])
            cfg["last_lock_error"] = ""
            count = len(cfg["locks"])
            message = f"Verification successful. Found {count} locks. You can use Step 5 & 6 now."
            log_event(f"Fast setup verification succeeded, {count} locks found")
        except TTLockError as e:
            error = f"Verification failed (TTLock error): {e}"
            cfg["last_lock_error"] = error
            log_event(error, logging.ERROR)
        except Exception as e:
            error = f"Verification failed (unexpected error): {e}"
            cfg["last_lock_error"] = error
            log_event(error, logging.ERROR)
    else:
        message = "Credentials saved. Add an access token to verify and fetch locks."
        log_event("Fast setup: saved credentials without access token (no verification)")

    save_config(cfg)
    curl_example = build_curl_example(cfg)
    log_tail = get_log_tail()

    combined_msg = error or message

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error=combined_msg,
        token_error="",
        curl_register_example=curl_example,
        log_tail=log_tail,
    )


# --------------------------------------------------------------------
# JSON API for external integrations
# --------------------------------------------------------------------
@app.route("/api/locks", methods=["GET"])
def api_locks():
    cfg = load_config()
    if not cfg.get("locks") and cfg.get("access_token"):
        try:
            result = list_locks(
                base_url=cfg["api_base_url"],
                access_token=cfg["access_token"],
            )
            cfg["locks"] = result.get("list", [])
            save_config(cfg)
            log_event(f"/api/locks auto-fetched {len(cfg['locks'])} locks")
        except Exception as e:
            log_event(f"/api/locks error fetching locks: {e}", logging.ERROR)

    return jsonify({"locks": cfg.get("locks", [])})


@app.route("/api/locks/<int:lock_id>/<action>", methods=["POST"])
def api_operate_lock(lock_id: int, action: str):
    cfg = load_config()

    if not cfg.get("access_token"):
        return jsonify({"success": False, "error": "No access token"}), 400

    try:
        result = operate_lock(
            base_url=cfg["api_base_url"],
            access_token=cfg["access_token"],
            lock_id=lock_id,
            action=action,
        )
        log_event(f"/api/locks/{lock_id}/{action} succeeded")
        return jsonify({"success": True, "result": result})
    except TTLockError as e:
        log_event(f"/api/locks/{lock_id}/{action} TTLockError: {e}", logging.ERROR)
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        log_event(f"/api/locks/{lock_id}/{action} unexpected error: {e}", logging.ERROR)
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
