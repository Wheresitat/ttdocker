# TTLock Helper – Docker UI + Home Assistant Integration

## 🔐 Why This Project Exists

TTLock smart locks are powerful devices, but their cloud API is:

- Difficult to authenticate against  
- Poorly documented  
- Not directly compatible with Home Assistant  
- Missing real-time state reporting  
- Hard to integrate without writing your own backend  

Most people just want:

✔ A way to **register TTLock users**  
✔ A way to **get access tokens**  
✔ A way to **see their locks in Home Assistant**  
✔ A way to **control locks locally**  
✔ Battery status  
✔ Gateway status  

This project solves all of that.

---

## 🌟 What This Project Does

This repository provides **THREE major components**:

### 1️⃣ A **Docker Web UI**  
A simple interface that walks you step-by-step through:

- Creating/registering TTLock usernames  
- Hashing passwords (MD5)  
- Generating timestamps  
- Getting access tokens  
- Fetching lock lists  
- Locking / unlocking locks  
- Viewing logs  
- Shortcut mode (paste existing credentials)

No more curl commands. No more API guessing.  
Everything is visual and local.

---

### 2️⃣ A **Local REST API Layer**

The Docker helper exposes simple endpoints:

GET /api/locks
POST /api/locks/<id>/lock
POST /api/locks/<id>/unlock

yaml
Copy code

This insulates Home Assistant and other apps from the messy TTLock API.

---

### 3️⃣ A **Home Assistant (HACS) Integration**

The integration:

- Auto-discovers locks from the helper  
- Creates HA `lock.<name>` entities  
- Creates battery sensors (`sensor.<lock>_battery`)  
- Creates gateway state sensors (`binary_sensor.<lock>_gateway`)  
- Uses optimistic state for lock/unlock  
- Refreshes automatically via a coordinator  

This gives you full automation power inside Home Assistant.

---

## 🏗 How the System Works (High-Level Architecture)

cpp
Copy code
      ┌─────────────────────────┐
      │     TTLock Cloud API     │
      │  (complex, OAuth, messy) │
      └──────────────┬──────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ TTLock Helper (Docker Container) │
│ - Web UI (Flask) │
│ - Stores config & tokens │
│ - Calls TTLock APIs │
│ - Exposes clean local REST endpoints │
└──────────────┬─────────────────────────┘
│
▼
┌──────────────────────────────┐
│ Home Assistant Integration │
│ - lock entities │
│ - battery sensors │
│ - gateway sensors │
│ - automations │
└──────────────────────────────┘

yaml
Copy code

Your Home Assistant **never** deals with TTLock directly —  
the helper container handles authentication, token refreshing, API calls, and lock commands.

---

# 🚀 1. Installation – Git Clone + Docker Setup

This is the simplest and recommended installation.

### Step 1 — Clone the repository

```bash
git clone https://github.com/Wheresitat/ttlockdockerHA.git
cd ttlockdockerHA
Your folder structure will look like:

css
Copy code
ttlockdockerHA/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py
│   ├── ttlock_api.py
│   └── templates/
│       └── index.html
└── custom_components/
    └── ttlock_helper/
Step 2 — Start the helper container
bash
Copy code
docker compose up -d
Monitor logs:

bash
Copy code
docker logs -f ttlock-helper
Step 3 — Open the web UI
Visit:

cpp
Copy code
http://<docker-host>:8005
Example:

cpp
Copy code
http://192.168.1.50:8005
You now have access to the TTLock Helper UI.

🧭 2. How to Use the Web UI
The interface guides you through every step TTLock requires.

🔹 Step 1 — Create Username & Password
TTLock requires:

Username (letters + numbers only)

Password (MD5 hashed)

Timestamp (ms)

The UI generates the correct MD5 hash and timestamp.

🔹 Step 2 — Enter TTLock Developer Credentials
You must provide:

API Base URL (https://api.ttlock.com)

Client ID

Client Secret

Click Save Settings.

🔹 Step 3 — Register the User
Click:

sql
Copy code
Register User
TTLock responds with a new internal username, such as:

nginx
Copy code
xyz123_myuser
⚠ Use this username for token requests — not your original one.

🔹 Step 4 — Get Access Token
Click:

pgsql
Copy code
Get Access Token
The helper stores:

access_token

refresh_token

🔹 Step 5 — Fetch Locks
Click:

sql
Copy code
Fetch Locks
You will see:

json
Copy code
{
  "lockId": 7421666,
  "lockAlias": "gym back door lock",
  "electricQuantity": 75,
  "hasGateway": 1
}
🔹 Step 6 — Control Locks
Choose:

Lock

Unlock

Click Send Command.

The helper stores a local isLocked value so HA can reflect state.

🔹 Shortcut Mode
If you already know:

Username

Password (plain or MD5)

Access token

Paste them at the top → click Verify → skip straight to Steps 5 & 6.

🌐 3. REST API Documentation
The helper exposes simple endpoints for scripts and HA.

List locks
bash
Copy code
GET /api/locks
Lock a door
bash
Copy code
POST /api/locks/<id>/lock
Unlock
bash
Copy code
POST /api/locks/<id>/unlock
All responses are JSON.

🏠 4. Home Assistant Integration (HACS)
The repository includes a full custom integration:
custom_components/ttlock_helper.

You can install it using HACS:

Step 1: Add custom repository
HACS → Integrations → Custom Repositories
Add:

bash
Copy code
https://github.com/Wheresitat/ttlockdockerHA
Category: Integration

Step 2: Install integration
HACS → Integrations → TTLock Helper → Install

Step 3: Restart Home Assistant
Step 4: Add the Integration
Home Assistant → Settings → Devices & Services → Add Integration
Search: TTLock Helper

Enter:

cpp
Copy code
http://<docker-host>:8005
Example:

cpp
Copy code
http://192.168.1.50:8005
Step 5: Done!
You now get:

5.1 Lock Entity
csharp
Copy code
lock.gym_back_door
Supports:

lock.lock

lock.unlock

5.2 Battery Level Sensor
From electricQuantity:

Copy code
sensor.gym_back_door_battery
Value: 0–100%

5.3 Gateway Presence Sensor
From hasGateway:

Copy code
binary_sensor.gym_back_door_gateway
on → lock has gateway

off → no gateway configured

🤖 5. Example Automations
Low Battery Alert
yaml
Copy code
trigger:
  - platform: numeric_state
    entity_id: sensor.gym_back_door_battery
    below: 20
action:
  - service: notify.mobile_app
    data:
      message: "The gym back door lock battery is below 20%!"
Auto-lock after 5 minutes
yaml
Copy code
trigger:
  - platform: state
    entity_id: lock.gym_back_door
    to: "unlocked"
    for: "00:05:00"
action:
  - service: lock.lock
    target:
      entity_id: lock.gym_back_door
Gateway Offline Alert
yaml
Copy code
trigger:
  - platform: state
    entity_id: binary_sensor.gym_back_door_gateway
    to: "off"
action:
  - service: notify.mobile_app
    data:
      message: "The TTLock gateway is no longer detected for the gym back door."
🛠 6. Troubleshooting
Lock shows “Unknown” state in HA
This is expected until you issue a lock or unlock command.
TTLock does NOT provide real-time lock state.

“existing registered users”
The username is already in use. Choose a unique username.

“invalid account or invalid password”
Use the returned TTLock username from Step 3 (not the raw one you typed).

Cannot fetch locks
Check:

client_id and client_secret are correct

Token was successfully generated

Check logs in the Web UI (bottom of the page)

No devices appear in Home Assistant
Check:

arduino
Copy code
http://<docker-host>:8005/api/locks
If no locks appear, fix the helper first.

❤️ Final Notes
This project greatly simplifies TTLock automation:

Local

Reliable

Fast

Fully integrated into Home Assistant

No cloud-to-cloud delay

Easy UI for configuration

If you want additional features:

✔ Door open/closed sensors
✔ Auto-refresh tokens
✔ Per-lock pin code management
✔ Doorbell keypad events
✔ Lock history / event logs
