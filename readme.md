# TTLock Helper – Docker + Home Assistant Bridge

This project provides a **local bridge between the TTLock cloud API and Home Assistant** using a lightweight Docker container.  
It allows you to **control TTLock smart locks from Home Assistant without exposing your TTLock credentials directly to Home Assistant**.

The system consists of:

1. A **Docker container** that authenticates with the TTLock cloud and exposes a simple local REST API.
2. A **Home Assistant custom integration** that connects to this local API and creates native `lock` entities.

---

## What This Does

- Authenticates with the **TTLock cloud API**
- Stores and refreshes **access tokens locally**
- Retrieves all locks linked to your TTLock account
- Exposes **local HTTP endpoints** for:
  - Lock
  - Unlock
  - Status polling
- Home Assistant connects **only to your local container**
- Locks appear as **native Home Assistant `lock` entities**
- Works without Nabu Casa or direct cloud exposure from Home Assistant

---

## Architecture Overview

Home Assistant → TTLock Helper (Docker) → TTLock Cloud API

yaml
Copy code

- Home Assistant talks to the helper via local HTTP
- The helper talks to TTLock’s official cloud API
- Credentials are stored only inside the Docker container

---

## Requirements

- Docker & Docker Compose
- Home Assistant (2024.0.0+)
- A TTLock account with at least one lock

---

## Step 1 – Clone the Repository


git clone https://github.com/Wheresitat/ttdocker.git
cd ttdocker
Step 2 – Configure TTLock Credentials
Create the configuration directory:

bash
Copy code
mkdir -p data
Create the config file:

bash
Copy code
nano data/config.json
Paste the following and update with your real credentials:

json
Copy code
{
  "client_id": "YOUR_TTLOCK_CLIENT_ID",
  "client_secret": "YOUR_TTLOCK_CLIENT_SECRET",
  "username": "YOUR_TTLOCK_EMAIL",
  "password": "YOUR_TTLOCK_PASSWORD"
}
Save and exit.

Step 3 – Start the Docker Container
From inside the repo directory:

bash
Copy code
docker compose up -d --build
Check logs:

bash
Copy code
docker logs -f ttlock-helper
The API will be available at:

cpp
Copy code
http://<DOCKER_HOST_IP>:8005
Step 4 – Verify the Helper is Working
From a browser or curl:

bash
Copy code
curl http://<DOCKER_HOST_IP>:8005/api/locks
You should receive a JSON list of your TTLock devices.

Step 5 – Install the Home Assistant Integration
Copy the integration into Home Assistant:

bash
Copy code
cp -r custom_components/ttlock_helper /config/custom_components/
Restart Home Assistant.

Step 6 – Add the Integration in Home Assistant
Go to Settings → Devices & Services

Click Add Integration

Search for TTLock Helper

Enter the base URL for your Docker container:

cpp
Copy code
http://<DOCKER_HOST_IP>:8005
Submit

Your locks will now appear as native Home Assistant lock entities.

Available API Endpoints
These are exposed locally by the Docker helper:

Endpoint	Method	Description
/api/locks	GET	List all locks
/api/locks/<lock_id>/lock	POST	Lock a specific lock
/api/locks/<lock_id>/unlock	POST	Unlock a specific lock

Logging & Data Storage
Logs are written to:

bash
Copy code
./data/app.log
Configuration is stored in:

arduino
Copy code
./data/config.json
Both persist across container restarts.

Security Notes
TTLock credentials never enter Home Assistant

Only your local Docker container holds credentials

Home Assistant communicates only via your LAN

Do NOT expose this container publicly via port forwarding

Updating
To update to the latest version:

bash
Copy code
git pull
docker compose down
docker compose up -d --build
Troubleshooting
Container keeps restarting
Check logs:

bash
Copy code
docker logs ttlock-helper
Verify config.json is valid JSON

Confirm TTLock credentials are correct

Locks show as unknown in Home Assistant
Ensure the helper API is reachable from Home Assistant

Verify /api/locks returns valid results

Restart Home Assistant after any changes

