import json
import os
import hashlib
from pathlib import Path

from flask import Flask, render_template, request

from ttlock_api import register_user, get_access_token, TTLockError

app = Flask(__name__)
app.secret_key = "change-this-secret"  # used by Flask; static is fine here

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/data/config.json"))


def default_config() -> dict:
    return {
        "api_base_url": "https://api.sciener.com",  # or https://euapi.ttlock.com
        "redirect_uri": "",
        "client_id": "",
        "client_secret": "",
        "username": "",
        "password_md5": "",
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
            data = default_config()
    else:
        data = default_config()

    # ensure all keys exist
    base = default_config()
    base.update(data)
    return base


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


@app.route("/", methods=["GET"])
def index():
    cfg = load_config()
    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password="",
        register_error="",
        token_error="",
    )


@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    cfg = load_config()

    cfg["api_base_url"] = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    cfg["redirect_uri"] = request.form.get("redirect_uri", "").strip()
    cfg["client_id"] = request.form.get("client_id", "").strip()
    cfg["client_secret"] = request.form.get("client_secret", "").strip()
    cfg["username"] = request.form.get("username", "").strip()
    cfg["password_md5"] = request.form.get("password_md5", "").strip()

    save_config(cfg)

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password="",
        register_error="Settings saved.",
        token_error="",
    )


@app.route("/hash_password", methods=["POST"])
def hash_password_route():
    cfg = load_config()
    plain = request.form.get("plain_password", "")
    plain = plain.strip()

    hashed = ""
    if plain:
        hashed = hashlib.md5(plain.encode("utf-8")).hexdigest()
        cfg["password_md5"] = hashed
        save_config(cfg)

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=hashed,
        register_error="",
        token_error="",
    )


@app.route("/register_user", methods=["POST"])
def register_user_route():
    cfg = load_config()

    # allow overriding API URL and username from the form
    api_base_url = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    username = request.form.get("username", "").strip() or cfg["username"]
    password_md5 = request.form.get("password_md5", "").strip() or cfg["password_md5"]

    cfg["api_base_url"] = api_base_url
    cfg["username"] = username
    cfg["password_md5"] = password_md5

    register_error = ""
    register_resp_raw = ""

    if not (cfg["client_id"] and cfg["client_secret"] and cfg["username"] and cfg["password_md5"]):
        register_error = "Missing required fields (client_id, client_secret, username, password_md5)."
    else:
        try:
            result = register_user(
                base_url=cfg["api_base_url"],
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                username=cfg["username"],
                password_md5=cfg["password_md5"],
            )
            # API returns a username (could be prefixed, e.g. ccajg_higgson1)
            cfg["username"] = result.get("username", cfg["username"])
            register_resp_raw = json.dumps(result, indent=2)
        except TTLockError as e:
            register_error = str(e)
        except Exception as e:
            register_error = f"Unexpected error: {e}"

    cfg["raw_register_response"] = register_resp_raw
    save_config(cfg)

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error=register_error,
        token_error="",
    )


@app.route("/get_token", methods=["POST"])
def get_token_route():
    cfg = load_config()

    api_base_url = request.form.get("api_base_url", "").strip() or cfg["api_base_url"]
    redirect_uri = request.form.get("redirect_uri", "").strip() or cfg["redirect_uri"]
    username = request.form.get("username", "").strip() or cfg["username"]
    password_md5 = request.form.get("password_md5", "").strip() or cfg["password_md5"]

    cfg["api_base_url"] = api_base_url
    cfg["redirect_uri"] = redirect_uri
    cfg["username"] = username
    cfg["password_md5"] = password_md5

    token_error = ""
    token_resp_raw = ""

    if not (cfg["client_id"] and cfg["client_secret"] and cfg["username"] and cfg["password_md5"]):
        token_error = "Missing required fields (client_id, client_secret, username, password_md5)."
    else:
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
        except TTLockError as e:
            token_error = str(e)
        except Exception as e:
            token_error = f"Unexpected error: {e}"

    cfg["raw_token_response"] = token_resp_raw
    save_config(cfg)

    return render_template(
        "index.html",
        cfg=cfg,
        hashed_password=cfg.get("password_md5", ""),
        register_error="",
        token_error=token_error,
    )


if __name__ == "__main__":
    # For local dev only; Docker uses gunicorn
    app.run(host="0.0.0.0", port=8000, debug=True)
