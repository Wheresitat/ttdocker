from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import TTLockCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TTLock locks from a config entry."""
    coordinator: TTLockCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TTLockLockEntity] = []

    for lock in coordinator.data:
        lock_id = lock.get("lockId")
        if lock_id is None:
            continue
        entities.append(TTLockLockEntity(coordinator, entry.entry_id, lock_id))

    _LOGGER.debug("Adding %d TTLock lock entities", len(entities))
    async_add_entities(entities)


class TTLockLockEntity(CoordinatorEntity[TTLockCoordinator], LockEntity):
    """Representation of a TTLock lock via helper."""

    def __init__(
        self,
        coordinator: TTLockCoordinator,
        entry_id: str,
        lock_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{lock_id}"
        self._attr_assumed_state = True

    @property
    def _lock_data(self) -> dict[str, Any] | None:
        for lock in self.coordinator.data:
            if lock.get("lockId") == self._lock_id:
                return lock
        return None

    @property
    def name(self) -> str | None:
        data = self._lock_data
        if not data:
            return f"TTLock {self._lock_id}"
        return data.get("lockAlias") or f"TTLock {self._lock_id}"

    @property
    def device_info(self) -> DeviceInfo:
        data = self._lock_data or {}
        model = data.get("modelNum") or "TTLock"
        manufacturer = "TTLock"
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._lock_id))},
            name=self.name,
            manufacturer=manufacturer,
            model=model,
        )

    @property
    def is_locked(self) -> bool | None:
        data = self._lock_data
        if not data:
            return None

        state = data.get("isLocked")
        if state is None:
            return None
        return bool(state)

    async def async_lock(self, **kwargs):
        _LOGGER.debug("Locking TTLock %s", self._lock_id)
        await self.coordinator.async_lock_action(self._lock_id, "lock")
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        _LOGGER.debug("Unlocking TTLock %s", self._lock_id)
        await self.coordinator.async_lock_action(self._lock_id, "unlock")
        await self.coordinator.async_request_refresh()
