"""Map per-lock slots to a stable person id.

The unlock event only carries the slot number on that lock. The stable id is
the Matter UserUniqueID, which is the same person on every lock they belong
to. Slot numbers are not. This module is the lookup used when a lock opens,
so it never talks to the lock.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .const import PLACEHOLDER_USER_ID, UNLOCK_OPERATION_TYPES

OPERATION_SOURCES = {
    0: "unspecified",
    1: "manual",
    2: "proprietary",
    3: "keypad",
    4: "automatic",
    5: "button",
    6: "schedule",
    7: "remote",
    8: "rfid",
    9: "biometric",
    10: "aliro",
}

CREDENTIAL_TYPES = {
    0: "programming_pin",
    1: "pin",
    2: "rfid",
    3: "fingerprint",
    4: "finger_vein",
    5: "face",
    6: "aliro_issuer",
    7: "aliro_endpoint",
    8: "aliro_endpoint",
}


@dataclass(frozen=True, slots=True)
class UserRecord:
    """One occupied slot that belongs to a real person."""

    unique_id: int
    suggested_name: str | None


@dataclass(frozen=True, slots=True)
class IdentityEvent:
    """An unlock, resolved as far as the in-memory table allows."""

    node_id: int
    user_index: int | None
    user_unique_id: int | None
    method: str
    credential_type: str | None
    credential_index: int | None
    source_node: int | None

    @property
    def identified(self) -> bool:
        """Return True when a person id was found."""
        return self.user_unique_id is not None


class SlotDirectory:
    """Slot table for every lock, keyed by Matter node id and user index."""

    def __init__(self) -> None:
        """Start with an empty table."""
        self._slots: dict[tuple[int, int], int] = {}
        self._names: dict[int, str] = {}

    def replace_node(self, node_id: int, slots: dict[int, UserRecord]) -> None:
        """Replace every slot known for one lock.

        Slots that disappeared are dropped. A person who still exists on
        another lock is kept. Unique id 0 is ignored.
        """
        self._slots = {
            key: unique_id
            for key, unique_id in self._slots.items()
            if key[0] != node_id
        }
        for slot, user in slots.items():
            if slot <= 0 or user.unique_id <= PLACEHOLDER_USER_ID:
                continue
            self._slots[(node_id, slot)] = user.unique_id
            if user.suggested_name and not self._names.get(user.unique_id):
                self._names[user.unique_id] = user.suggested_name

    def unique_id_for(self, node_id: int, user_index: int | None) -> int | None:
        """Return the person id for a slot, or None when it is unknown."""
        if user_index is None:
            return None
        return self._slots.get((node_id, user_index))

    def suggested_name(self, user_unique_id: int) -> str | None:
        """Return a name the lock itself provided, if it ever did."""
        return self._names.get(user_unique_id)

    def membership(self) -> dict[int, list[tuple[int, int]]]:
        """Return each person id and the lock slots they occupy."""
        grouped: dict[int, list[tuple[int, int]]] = {}
        for node_id, slot in sorted(self._slots):
            grouped.setdefault(self._slots[(node_id, slot)], []).append((node_id, slot))
        return grouped


def identify(
    directory: SlotDirectory, node_id: int, data: object
) -> IdentityEvent | None:
    """Resolve one Matter event from the cache.

    Returns None when the event is not an unlock. Returns an event with no
    person when the lock did not send a slot, or the slot is not in the cache
    yet. This never reads the lock.
    """
    if not isinstance(data, dict):
        return None
    if _as_int(data.get("lockOperationType")) not in UNLOCK_OPERATION_TYPES:
        return None
    user_index = _as_int(data.get("userIndex"))
    credential_type, credential_index = _credential(data)
    return IdentityEvent(
        node_id=node_id,
        user_index=user_index,
        user_unique_id=directory.unique_id_for(node_id, user_index),
        method=_label(data.get("operationSource"), OPERATION_SOURCES, "source"),
        credential_type=credential_type,
        credential_index=credential_index,
        source_node=_as_int(data.get("sourceNode")),
    )


async def collect_slots(
    fetch: Callable[[int], Awaitable[object]], max_users: int
) -> dict[int, UserRecord]:
    """Walk a lock's user table.

    ``nextUserIndex`` skips empty slots, but some locks always send null.
    Null ends the walk only after the lock has already pointed forward, which
    shows that it implements the field. Otherwise every slot is visited.
    """
    if max_users < 1:
        return {}
    slots: dict[int, UserRecord] = {}
    index = 1
    reports_next = False
    while index <= max_users:
        record = await fetch(index)
        parsed = slot_from_record(record)
        if parsed is not None:
            slot, user = parsed
            slots[slot] = user
        nxt = next_user_index(record)
        if nxt is not None and nxt > index:
            reports_next = True
            index = nxt
        elif nxt is None and reports_next:
            break
        else:
            index += 1
    return slots


def slot_from_record(record: object) -> tuple[int, UserRecord] | None:
    """Return a person slot, or None for an empty or placeholder slot."""
    status = _as_int(_field(record, "userStatus"))
    # 0 is Available. Occupied slots are 1 (enabled) and 2 (disabled).
    if status is None or status == 0:
        return None
    unique_id = _as_int(_field(record, "userUniqueID"))
    slot = _as_int(_field(record, "userIndex"))
    if (
        unique_id is None
        or unique_id <= PLACEHOLDER_USER_ID
        or slot is None
        or slot <= 0
    ):
        return None
    return slot, UserRecord(unique_id, _clean_name(_field(record, "userName")))


def next_user_index(record: object) -> int | None:
    """Return the next occupied slot the lock pointed at, if any."""
    return _as_int(_field(record, "nextUserIndex"))


def default_name(user_unique_id: int, suggested_name: str | None) -> str:
    """Return the name to use until someone renames the entity."""
    cleaned = _clean_name(suggested_name)
    if cleaned:
        return cleaned
    return f"Lock user {user_unique_id}"


def display_name(
    configured: str | None, original: str | None, user_unique_id: int
) -> str:
    """Return the name currently shown for a person.

    ``configured`` is the name set in Home Assistant. ``original`` is the
    name this integration first gave the entity.
    """
    for candidate in (configured, original):
        cleaned = _clean_name(candidate, limit=None)
        if cleaned:
            return cleaned
    return f"Lock user {user_unique_id}"


def _credential(data: dict[str, object]) -> tuple[str | None, int | None]:
    """Return the first credential's type and index.

    Credential payloads can include secret material on other commands. Only
    the type and index are copied, never the credential itself.
    """
    raw = data.get("credentials")
    if isinstance(raw, list):
        raw = next((item for item in raw if isinstance(item, dict)), None)
    if not isinstance(raw, dict):
        return None, None
    number = _as_int(raw.get("credentialType"))
    index = _as_int(raw.get("credentialIndex"))
    if number is None:
        return None, index
    return _label(number, CREDENTIAL_TYPES, "credential"), index


def _label(value: object, names: dict[int, str], prefix: str) -> str:
    """Return a stable name for a Matter enum value."""
    number = _as_int(value)
    if number is None:
        return "unknown"
    return names.get(number, f"{prefix}_{number}")


def _field(record: object, name: str) -> object:
    """Read one field from a dict or a cluster object."""
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def _as_int(value: object) -> int | None:
    """Return an int, or None for bools and anything else."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    nested = getattr(value, "value", None)
    if isinstance(nested, bool) or not isinstance(nested, int):
        return None
    return nested


def _clean_name(value: object, *, limit: int | None = 64) -> str | None:
    """Return a short display name, without trailing nulls from Matter."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\x00", "").strip()
    if not cleaned:
        return None
    if limit is not None:
        return cleaned[:limit]
    return cleaned
