from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TTLockCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TTLock gateway binary sensors from a config entry."""
    coordinator: TTLockCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TTLockGatewayBinarySensor] = []

    for lock in coordinator.data:
        lock_id = lock.get("lockId")
        if lock_id is None:
            continue
        entities.append(TTLockGatewayBinarySensor(coordinator, entry.entry_id, lock_id))

    _LOGGER.debug("Adding %d TTLock gateway sensors", len(entities))
    async_add_entities(entities)


class TTLockGatewayBinarySensor(
    CoordinatorEntity[TTLockCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if lock has a gateway configured."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: TTLockCoordinator,
        entry_id: str,
        lock_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{lock_id}_gateway"

    @property
    def _lock_data(self) -> dict[str, Any] | None:
        for lock in self.coordinator.data:
            if lock.get("lockId") == self._lock_id:
                return lock
        return None

    @property
    def name(self) -> str | None:
        data = self._lock_data
        base = "TTLock"
        if data:
            base = data.get("lockAlias") or base
        return f"{base} Gateway"

    @property
    def is_on(self) -> bool | None:
        data = self._lock_data
        if not data:
            return None
        has_gateway = data.get("hasGateway")
        if has_gateway is None:
            return None
        try:
            return int(has_gateway) == 1
        except (TypeError, ValueError):
            return None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach gateway sensor to the same device as the lock/helper."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="TTLock Helper",
            manufacturer="TTLock",
            model="TTLock Cloud",
        )
