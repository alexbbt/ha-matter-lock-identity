"""Listen to the Matter integration that is already running.

Unlock handling only looks at the in-memory slot table. Reading a lock is
reserved for the background refresh, because a sleepy lock can take seconds
to answer and the unlock event is already here.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DEFAULT_MAX_USERS,
    DOMAIN,
    DOOR_LOCK_CLUSTER_ID,
    EVENT_UNLOCKED,
    GET_USER_TIMED_MS,
    GET_USER_TIMEOUT_MS,
    LOCK_OPERATION_EVENT_ID,
    LOGGER,
    REFRESH_INTERVAL,
    TOTAL_USERS_ATTRIBUTE_ID,
    UNKNOWN_SLOT_RETRY,
    default_lock_name,
    is_forked_matter_lock_device,
    is_legacy_lock_device,
    user_entity_key,
)
from .device import fallback_lock_device_info, matter_lock_device
from .directory import (
    IdentityEvent,
    SlotDirectory,
    UserRecord,
    collect_slots,
    default_name,
    display_name,
    identify,
)
from .event import LockUnlockEvent
from .sensor import LockOperatorSensor, LockUserSensor

AddEntities = Callable[[list[Any]], None]


class IdentityRuntime:
    """Slot cache, person entities, and the unlock hot path."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create a runtime that has not subscribed yet."""
        self.hass = hass
        self.entry_id = entry_id
        self.directory = SlotDirectory()
        self._add_events: AddEntities | None = None
        self._add_sensors: AddEntities | None = None
        self._client: Any = None
        self._lock_names: dict[int, str] = {}
        self._locks: dict[int, LockUnlockEvent] = {}
        self._node_event_type: type | None = None
        self._operators: dict[int, LockOperatorSensor] = {}
        self._pending_events: list[LockUnlockEvent] = []
        self._pending_sensors: list[LockUserSensor | LockOperatorSensor] = []
        self._refresh_again = False
        self._refresh_lock = asyncio.Lock()
        self._sensors: dict[int, LockUserSensor] = {}
        self._stopped = False
        self._tasks: set[asyncio.Task[None]] = set()
        self._unknown_until: dict[tuple[int, int], float] = {}
        self._unsub_interval: Callable[[], None] | None = None
        self._unsubscribe: Callable[[], None] | None = None

    def bind_sensors(self, add_entities: AddEntities) -> None:
        """Register the sensor platform and flush anyone found before it loaded."""
        self._add_sensors = add_entities
        if self._pending_sensors:
            add_entities(self._pending_sensors)
            self._pending_sensors = []

    def bind_events(self, add_entities: AddEntities) -> None:
        """Register the event platform and flush locks found before it loaded."""
        self._add_events = add_entities
        if self._pending_events:
            add_entities(self._pending_events)
            self._pending_events = []

    async def async_start(self) -> None:
        """Subscribe to the existing Matter client and refresh in the background."""
        from matter_server.common.models import EventType, MatterNodeEvent

        self._node_event_type = MatterNodeEvent
        try:
            self._client = _matter_client(self.hass)
        except Exception as err:
            raise ConfigEntryNotReady("Matter is not ready") from err
        self._cleanup_stale_lock_devices()
        self._unsubscribe = self._client.subscribe_events(
            self._on_matter_event,
            event_filter=EventType.NODE_EVENT,
        )
        self._unsub_interval = async_track_time_interval(
            self.hass, self._on_interval, REFRESH_INTERVAL
        )
        self._spawn(self.async_refresh())
        LOGGER.info("Listening for Matter lock unlocks")

    async def async_stop(self) -> None:
        """Stop listening and cancel a refresh that is still running."""
        self._stopped = True
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        for task in list(self._tasks):
            task.cancel()

    async def async_refresh(self) -> None:
        """Re-read user tables. Overlapping calls run one extra pass at the end."""
        if self._stopped:
            return
        if self._refresh_lock.locked():
            self._refresh_again = True
            return
        async with self._refresh_lock:
            while not self._stopped:
                self._refresh_again = False
                try:
                    await self._refresh()
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    LOGGER.warning(
                        "Could not refresh lock users: %s", type(err).__name__
                    )
                if not self._refresh_again:
                    break

    def _on_matter_event(self, _event_type: object, data: object) -> None:
        """Receive one Matter event. May run off the Home Assistant loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is self.hass.loop:
            self._handle_event(data)
            return
        self.hass.loop.call_soon_threadsafe(self._handle_event, data)

    def _handle_event(self, data: object) -> None:
        """Identify an unlock from memory and emit it."""
        if self._stopped or self._node_event_type is None:
            return
        if not isinstance(data, self._node_event_type):
            return
        event = cast(Any, data)
        if (
            event.cluster_id != DOOR_LOCK_CLUSTER_ID
            or event.event_id != LOCK_OPERATION_EVENT_ID
        ):
            return
        identity = identify(self.directory, event.node_id, event.data or {})
        if identity is None:
            return
        self.ensure_lock(event.node_id, self._lock_names.get(event.node_id))
        if identity.user_index is not None and identity.user_unique_id is not None:
            self._unknown_until.pop((event.node_id, identity.user_index), None)
        payload = self._payload(identity)
        self._emit(event.node_id, payload)
        if (
            identity.user_index is not None
            and identity.user_unique_id is None
            and self._should_retry_unknown(event.node_id, identity.user_index)
        ):
            self._spawn(self.async_refresh())

    def ensure_lock(self, node_id: int, name: str | None) -> None:
        """Create unlock and operator entities on the Matter lock device."""
        if isinstance(name, str) and name.strip():
            label = name.strip()
        else:
            label = default_lock_name(node_id)
        self._lock_names[node_id] = label
        device_entry = matter_lock_device(self.hass, self._client, node_id)
        device_info = (
            None if device_entry is not None else fallback_lock_device_info(node_id)
        )

        event = self._locks.get(node_id)
        if event is None:
            event = LockUnlockEvent(
                node_id, device_entry=device_entry, device_info=device_info
            )
            self._locks[node_id] = event
            if self._add_events is not None:
                self._add_events([event])
            else:
                self._pending_events.append(event)
        else:
            event.set_device_link(device_entry, device_info)

        operator = self._operators.get(node_id)
        if operator is None:
            operator = LockOperatorSensor(
                node_id, device_entry=device_entry, device_info=device_info
            )
            self._operators[node_id] = operator
            if self._add_sensors is not None:
                self._add_sensors([operator])
            else:
                self._pending_sensors.append(operator)
        else:
            operator.set_device_link(device_entry, device_info)

    async def _on_interval(self, _now: object) -> None:
        await self.async_refresh()

    async def _refresh(self) -> None:
        client = self._client or _matter_client(self.hass)
        self._client = client
        locks = 0
        for node in list(client.get_nodes()):
            endpoints = [
                endpoint
                for endpoint in node.endpoints.values()
                if endpoint.has_cluster(DOOR_LOCK_CLUSTER_ID)
            ]
            if not endpoints:
                continue
            locks += 1
            self.ensure_lock(node.node_id, _lock_label(node))
            if not node.available:
                LOGGER.debug("Skipping unavailable lock node %s", node.node_id)
                continue
            merged: dict[int, UserRecord] = {}
            failed = False
            for endpoint in endpoints:
                try:
                    found = await self._read_endpoint(client, node.node_id, endpoint)
                except Exception as err:
                    failed = True
                    LOGGER.warning(
                        "Could not read users on node %s: %s",
                        node.node_id,
                        type(err).__name__,
                    )
                    break
                merged.update(found)
            if failed:
                continue
            self.directory.replace_node(node.node_id, merged)
            self._clear_resolved_unknowns(node.node_id)
        self._sync_users()
        self._cleanup_stale_lock_devices()
        LOGGER.info(
            "Refreshed lock users: %s people on %s locks",
            len(self.directory.membership()),
            locks,
        )

    async def _read_endpoint(
        self, client: Any, node_id: int, endpoint: Any
    ) -> dict[int, UserRecord]:
        from chip.clusters.Objects import DoorLock

        max_users = _max_users(endpoint)

        async def fetch(index: int) -> object:
            return await client.send_device_command(
                node_id=node_id,
                endpoint_id=endpoint.endpoint_id,
                command=DoorLock.Commands.GetUser(userIndex=index),
                timed_request_timeout_ms=GET_USER_TIMED_MS,
                interaction_timeout_ms=GET_USER_TIMEOUT_MS,
            )

        return await collect_slots(fetch, max_users)

    def _sync_users(self) -> None:
        grouped = self.directory.membership()
        for unique_id, slots in grouped.items():
            sensor = self._sensors.get(unique_id)
            if sensor is None:
                sensor = LockUserSensor(
                    unique_id,
                    default_name(unique_id, self.directory.suggested_name(unique_id)),
                )
                self._sensors[unique_id] = sensor
                sensor.set_membership(slots)
                if self._add_sensors is not None:
                    self._add_sensors([sensor])
                else:
                    self._pending_sensors.append(sensor)
            else:
                sensor.set_membership(slots)
        for unique_id, sensor in self._sensors.items():
            if unique_id not in grouped:
                sensor.set_membership([])

    def _payload(self, identity: IdentityEvent) -> dict[str, Any]:
        user_name = None
        if identity.user_unique_id is not None:
            user_name = self._name_for(identity.user_unique_id)
        return {
            "node_id": identity.node_id,
            "lock_name": self._lock_names.get(
                identity.node_id, default_lock_name(identity.node_id)
            ),
            "identified": identity.identified,
            "user_unique_id": identity.user_unique_id,
            "user_name": user_name,
            "user_index": identity.user_index,
            "method": identity.method,
            "credential_type": identity.credential_type,
            "credential_index": identity.credential_index,
            "source_node": identity.source_node,
        }

    def _emit(self, node_id: int, payload: dict[str, Any]) -> None:
        entity = self._locks.get(node_id)
        if entity is not None and entity.hass is not None:
            entity.publish(payload)
        operator = self._operators.get(node_id)
        if operator is not None:
            operator.publish(payload)
        self.hass.bus.async_fire(EVENT_UNLOCKED, payload)
        if payload["identified"]:
            LOGGER.info(
                "Unlock on node %s identified as %s", node_id, payload["user_name"]
            )
        else:
            LOGGER.debug(
                "Unlock on node %s has no person (slot %s, method %s)",
                node_id,
                payload["user_index"],
                payload["method"],
            )

    def _name_for(self, user_unique_id: int) -> str:
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, user_entity_key(user_unique_id)
        )
        if entity_id is not None:
            entry = registry.async_get(entity_id)
            if entry is not None:
                return display_name(entry.name, entry.original_name, user_unique_id)
        sensor = self._sensors.get(user_unique_id)
        if sensor is not None:
            return sensor.fallback_name
        return default_name(
            user_unique_id, self.directory.suggested_name(user_unique_id)
        )

    def _should_retry_unknown(self, node_id: int, slot: int) -> bool:
        key = (node_id, slot)
        now = time.monotonic()
        if now < self._unknown_until.get(key, 0.0):
            return False
        self._unknown_until[key] = now + UNKNOWN_SLOT_RETRY.total_seconds()
        return True

    def _clear_resolved_unknowns(self, node_id: int) -> None:
        for key in list(self._unknown_until):
            if key[0] == node_id and self.directory.unique_id_for(*key) is not None:
                self._unknown_until.pop(key, None)

    def _cleanup_stale_lock_devices(self) -> None:
        """Remove empty fallback and forked Matter lock devices we created."""
        registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        for device in list(registry.devices.values()):
            if device.config_entry_id != self.entry_id:
                continue
            identifiers = device.identifiers
            if not (
                is_legacy_lock_device(identifiers)
                or is_forked_matter_lock_device(identifiers)
            ):
                continue
            if er.async_entries_for_device(entity_registry, device.id):
                continue
            registry.async_remove_device(device.id)

    def _spawn(self, coro: Any) -> None:
        task = self.hass.async_create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


def _matter_client(hass: HomeAssistant) -> Any:
    from homeassistant.components.matter.helpers import get_matter

    return get_matter(hass).matter_client


def _lock_label(node: Any) -> str | None:
    try:
        name = node.name
    except Exception:
        return None
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _max_users(endpoint: Any) -> int:
    try:
        value = endpoint.get_attribute_value(
            DOOR_LOCK_CLUSTER_ID, TOTAL_USERS_ATTRIBUTE_ID
        )
    except Exception:
        return DEFAULT_MAX_USERS
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return DEFAULT_MAX_USERS
    return min(value, 1000)
