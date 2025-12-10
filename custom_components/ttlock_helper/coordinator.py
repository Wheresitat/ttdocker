from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_BASE_URL, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TTLockCoordinator(DataUpdateCoordinator[list[dict]]):
    """Coordinator to fetch locks from TTLock helper and send actions."""

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

    async def _async_update_data(self) -> list[dict]:
        """Fetch data from the helper (lock list)."""
        url = f"{self._base_url}/api/locks"
        _LOGGER.debug("Fetching locks from %s", url)

        session: aiohttp.ClientSession = async_get_clientsession(self.hass)

        try:
            async with async_timeout.timeout(10):
                async with session.get(url) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        raise UpdateFailed(
                            f"HTTP {resp.status} error when fetching locks: {text}"
                        )
                    try:
                        data = await resp.json()
                    except Exception as err:
                        raise UpdateFailed(
                            f"Non-JSON response when fetching locks: {text}"
                        ) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with TTLock helper: {err}") from err

        locks = data.get("locks", [])
        _LOGGER.debug("Got %d locks from helper", len(locks))
        return locks

    async def async_lock_action(self, lock_id: int, action: str) -> None:
        """
        Send lock/unlock command via helper.

        We intentionally do NOT raise UpdateFailed here (that's for polling).
        Instead we:
        - Treat any 2xx result as success.
        - Raise HomeAssistantError only on real HTTP problems.
        """
        action = action.lower()
        if action not in ("lock", "unlock"):
            raise HomeAssistantError(f"Invalid action '{action}' for TTLock")

        url = f"{self._base_url}/api/locks/{lock_id}/{action}"
        _LOGGER.debug("Calling TTLock helper action %s for lock %s at %s", action, lock_id, url)

        session: aiohttp.ClientSession = async_get_clientsession(self.hass)

        try:
            async with async_timeout.timeout(15):
                async with session.post(url) as resp:
                    text = await resp.text()
                    if resp.status < 200 or resp.status >= 300:
                        # Real error from helper – surface to HA
                        _LOGGER.error(
                            "HTTP %s when calling %s for lock %s: %s",
                            resp.status,
                            action,
                            lock_id,
                            text,
                        )
                        raise HomeAssistantError(
                            f"TTLock helper HTTP {resp.status}: {text}"
                        )

                    # Try to parse JSON, but don't fail the action if shape is unexpected.
                    try:
                        data = await resp.json()
                        _LOGGER.debug(
                            "TTLock helper %s for lock %s returned: %s",
                            action,
                            lock_id,
                            data,
                        )
                    except Exception:
                        # Not fatal – the lock already acted if status was 2xx.
                        _LOGGER.debug(
                            "TTLock helper %s for lock %s returned non-JSON: %s",
                            action,
                            lock_id,
                            text,
                        )

        except HomeAssistantError:
            # Already logged, re-raise clean HA error
            raise
        except Exception as err:
            # Generic network/timeout/other failure
            _LOGGER.error(
                "Error when sending %s command to TTLock helper for lock %s: %s",
                action,
                lock_id,
                err,
            )
            raise HomeAssistantError(
                f"Error talking to TTLock helper: {err}"
            ) from err
