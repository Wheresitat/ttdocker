from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_BASE_URL, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TTLockCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch locks from TTLock helper."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="TTLock Helper Coordinator",
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _async_update_data(self):
        """Fetch data from the helper."""
        url = f"{self._base_url}/api/locks"
        _LOGGER.debug("Fetching locks from %s", url)

        session: aiohttp.ClientSession = self.hass.helpers.aiohttp_client.async_get_clientsession()

        try:
            with async_timeout.timeout(10):
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status} error when fetching locks")
                    data = await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with TTLock helper: {err}") from err

        # Expecting data: {"locks": [ {...}, {...} ]}
        locks = data.get("locks", [])
        _LOGGER.debug("Got %d locks from helper", len(locks))
        return locks

    async def async_lock_action(self, lock_id: int, action: str) -> None:
        """Send lock/unlock command via helper."""
        url = f"{self._base_url}/api/locks/{lock_id}/{action}"
        _LOGGER.debug("Calling %s", url)

        session: aiohttp.ClientSession = self.hass.helpers.aiohttp_client.async_get_clientsession()

        async with async_timeout.timeout(10):
            async with session.post(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(f"HTTP {resp.status} when {action} lock {lock_id}: {text}")
                data = await resp.json()
                if not data.get("success", False):
                    raise UpdateFailed(f"{action} failed for lock {lock_id}: {data}")
