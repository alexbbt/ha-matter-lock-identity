"""Constants for Matter Lock Identity."""

from __future__ import annotations

import logging
from datetime import timedelta

__version__ = "0.2.2"

DOMAIN = "matter_lock_identity"
HUB_ID = "hub"
HUB_NAME = "Matter Lock Identity"
LOGGER = logging.getLogger(__package__)

EVENT_UNLOCKED = "matter_lock_identity_unlocked"
UNKNOWN_OPERATOR = "Unknown"

# Matter Door Lock cluster, LockOperation event, NumberOfTotalUsersSupported.
DOOR_LOCK_CLUSTER_ID = 257
LOCK_OPERATION_EVENT_ID = 2
TOTAL_USERS_ATTRIBUTE_ID = 17

# Unlock and unlatch both mean the door was opened by someone.
UNLOCK_OPERATION_TYPES = frozenset({1, 4})

REFRESH_INTERVAL = timedelta(hours=6)
UNKNOWN_SLOT_RETRY = timedelta(minutes=5)
DEFAULT_MAX_USERS = 32
GET_USER_TIMEOUT_MS = 25000
GET_USER_TIMED_MS = 10000

# A Matter user unique id of 0 is not a person. Some locks use it for a
# placeholder slot that has no stable id.
PLACEHOLDER_USER_ID = 0


def user_entity_key(user_unique_id: int) -> str:
    """Return the stable entity unique id for one person."""
    return f"user-{user_unique_id}"


def lock_entity_key(node_id: int) -> str:
    """Return the stable entity unique id for one lock's unlock event."""
    return f"unlock-{node_id}"


def operator_entity_key(node_id: int) -> str:
    """Return the stable entity unique id for one lock's operator sensor."""
    return f"operator-{node_id}"


def default_lock_name(node_id: int) -> str:
    """Return the name used until the lock reports one."""
    return f"Matter lock {node_id}"


def is_legacy_lock_device(identifiers: set[tuple[str, ...]]) -> bool:
    """Return True when this device is an old per-lock identity device."""
    for identifier in identifiers:
        if len(identifier) < 2:
            continue
        domain, value = identifier[0], identifier[1]
        if domain == DOMAIN and str(value).startswith("node-"):
            return True
    return False


def is_forked_matter_lock_device(identifiers: set[tuple[str, ...]]) -> bool:
    """Return True when this device reused Matter identifiers under our entry.

    Home Assistant 2026.8+ no longer merges devices across integrations, so
    DeviceInfo with Matter identifiers creates an empty fork to remove.
    """
    for identifier in identifiers:
        if len(identifier) >= 2 and identifier[0] == "matter":
            return True
    return False
