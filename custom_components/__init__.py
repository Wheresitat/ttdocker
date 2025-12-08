from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_BASE_URL
from .coordinator import TTLockCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["lock"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used, config flow only)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TTLock Helper from a config entry."""
    base_url = entry.data[CONF_BASE_URL]

    coordinator = TTLockCoordinator(hass, base_url)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
