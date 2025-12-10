from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up TTLock battery sensors from a config entry."""
    coordinator: TTLockCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TTLockBatterySensor] = []

    for lock in coordinator.data:
        lock_id = lock.get("lockId")
        if lock_id is None:
            continue
        entities.append(TTLockBatterySensor(coordinator, entry.entry_id, lock_id))

    _LOGGER.debug("Adding %d TTLock battery sensors", len(entities))
    async_add_entities(entities)


class TTLockBatterySensor(CoordinatorEntity[TTLockCoordinator], SensorEntity):
    """Battery level sensor for TTLock."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TTLockCoordinator,
        entry_id: str,
        lock_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{lock_id}_battery"

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
        return f"{base} Battery"

    @property
    def native_value(self) -> int | None:
        data = self._lock_data
        if not data:
            return None
        value = data.get("electricQuantity")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def device_info(self) -> DeviceInfo:
        data = self._lock_data or {}
        model = data.get("modelNum") or "TTLock"
        manufacturer = "TTLock"
        base_name = data.get("lockAlias") or f"TTLock {self._lock_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._lock_id))},
            name=base_name,
            manufacturer=manufacturer,
            model=model,
        )
