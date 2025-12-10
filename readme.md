# TTLock Helper (Home Assistant Integration)

This custom integration talks to a separate `ttlock-helper` Docker container
(which wraps the TTLock API) and exposes your TTLock devices as `lock` entities
in Home Assistant.

## Requirements

- The `ttlock-helper` container running and reachable from Home Assistant.
- The helper must have:
  - API base URL set (`https://api.ttlock.com`)
  - Valid `clientId` / `clientSecret`
  - A working TTLock user and `access_token`

## Installation

1. Copy `custom_components/ttlock_helper` into your Home Assistant `config` folder.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **TTLock Helper**.
5. Enter the base URL of your helper, e.g. `http://192.168.1.50:8005`.

## Usage

- After configuration, your TTLock devices appear as `lock` entities.
- Lock/unlock calls are forwarded to the helper:
  - `POST /api/locks/<lock_id>/lock`
  - `POST /api/locks/<lock_id>/unlock`
- The helper internally talks to TTLock cloud.
