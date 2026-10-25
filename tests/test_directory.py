"""Tests for the slot table and unlock identification."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.matter_lock_identity.directory import (
    SlotDirectory,
    UserRecord,
    collect_slots,
    default_name,
    display_name,
    identify,
    slot_from_record,
)


class _Value:
    def __init__(self, value: int) -> None:
        self.value = value


def test_same_person_on_two_locks_is_one_id() -> None:
    """Slot 1 on one lock is not slot 1 on the next."""
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None)})
    directory.replace_node(2, {4: UserRecord(1001, None)})

    assert directory.unique_id_for(1, 1) == 1001
    assert directory.unique_id_for(2, 4) == 1001
    assert directory.unique_id_for(2, 1) is None
    assert directory.membership() == {1001: [(1, 1), (2, 4)]}


def test_same_slot_can_be_different_people() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None)})
    directory.replace_node(2, {1: UserRecord(2002, None)})

    assert directory.unique_id_for(1, 1) == 1001
    assert directory.unique_id_for(2, 1) == 2002


def test_placeholder_unique_id_is_not_a_person() -> None:
    directory = SlotDirectory()
    directory.replace_node(2, {1: UserRecord(0, "Card")})

    assert directory.membership() == {}
    assert directory.suggested_name(0) is None


def test_replacing_a_lock_drops_removed_people_only_on_that_lock() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None), 2: UserRecord(2002, None)})
    directory.replace_node(2, {2: UserRecord(1001, None)})

    directory.replace_node(1, {2: UserRecord(2002, None)})

    assert directory.unique_id_for(1, 1) is None
    assert directory.unique_id_for(1, 2) == 2002
    assert directory.membership()[1001] == [(2, 2)]


def test_first_real_lock_name_is_kept() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None)})
    directory.replace_node(2, {2: UserRecord(1001, "Ada")})
    directory.replace_node(1, {1: UserRecord(1001, "Someone else")})

    assert directory.suggested_name(1001) == "Ada"


def test_unlock_uses_the_cached_person() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {3: UserRecord(1001, None)})

    event = identify(
        directory,
        1,
        {"lockOperationType": 1, "operationSource": 10, "userIndex": 3},
    )

    assert event is not None
    assert event.user_unique_id == 1001
    assert event.user_index == 3
    assert event.method == "aliro"
    assert event.identified is True


def test_unknown_slot_does_not_invent_a_person() -> None:
    event = identify(
        SlotDirectory(),
        1,
        {"lockOperationType": 1, "operationSource": _Value(3), "userIndex": 9},
    )

    assert event is not None
    assert event.user_unique_id is None
    assert event.method == "keypad"
    assert event.identified is False


def test_remote_and_unspecified_unlocks_stay_anonymous() -> None:
    remote = identify(
        SlotDirectory(),
        1,
        {"lockOperationType": 1, "operationSource": 7, "sourceNode": 50},
    )
    unspecified = identify(
        SlotDirectory(),
        1,
        {"lockOperationType": 1, "operationSource": 0},
    )

    assert remote is not None
    assert remote.user_index is None
    assert remote.method == "remote"
    assert remote.source_node == 50
    assert unspecified is not None
    assert unspecified.method == "unspecified"
    assert unspecified.user_unique_id is None


def test_locking_is_ignored_and_unlatch_counts() -> None:
    directory = SlotDirectory()

    assert identify(directory, 1, {"lockOperationType": 0, "userIndex": 1}) is None
    assert identify(directory, 1, None) is None
    assert identify(directory, 1, {"lockOperationType": 4, "userIndex": 1}) is not None


def test_bool_is_not_a_slot_number() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None)})

    event = identify(directory, 1, {"lockOperationType": 1, "userIndex": True})

    assert event is not None
    assert event.user_index is None
    assert event.user_unique_id is None


def test_credential_type_and_index_are_kept_but_not_the_secret() -> None:
    directory = SlotDirectory()
    directory.replace_node(1, {1: UserRecord(1001, None)})
    event = identify(
        directory,
        1,
        {
            "lockOperationType": 1,
            "operationSource": 3,
            "userIndex": 1,
            "credentials": [
                {
                    "credentialType": 1,
                    "credentialIndex": 0,
                    "credentialData": "9999",
                }
            ],
        },
    )

    assert event is not None
    assert event.credential_type == "pin"
    assert event.credential_index == 0
    assert "9999" not in repr(event)


def test_single_credential_object_and_unknown_type() -> None:
    event = identify(
        SlotDirectory(),
        1,
        {
            "lockOperationType": 1,
            "credentials": {"credentialType": 3, "credentialIndex": 1},
        },
    )

    assert event is not None
    assert event.credential_type == "fingerprint"
    assert event.credential_index == 1

    unknown = identify(
        SlotDirectory(),
        1,
        {
            "lockOperationType": 1,
            "credentials": {"credentialType": 10, "credentialIndex": 0},
        },
    )
    assert unknown is not None
    assert unknown.credential_type == "credential_10"
    assert unknown.credential_index == 0


def test_empty_slot_and_placeholder_record_are_skipped() -> None:
    empty = {"userIndex": 1, "userStatus": None, "userUniqueID": 1001}
    available = {"userIndex": 1, "userStatus": 0, "userUniqueID": 1001}
    assert slot_from_record(empty) is None
    assert slot_from_record(available) is None
    assert (
        slot_from_record(
            {"userIndex": 1, "userStatus": 1, "userUniqueID": 0, "userName": "Card"}
        )
        is None
    )


def test_record_object_supplies_a_cleaned_name() -> None:
    parsed = slot_from_record(
        SimpleNamespace(
            userIndex=2,
            userStatus=_Value(1),
            userUniqueID=1001,
            userName=b"Ada\x00",
            nextUserIndex=None,
        )
    )

    assert parsed is not None
    slot, user = parsed
    assert slot == 2
    assert user.unique_id == 1001
    assert user.suggested_name == "Ada"


def test_names_prefer_the_rename_and_fall_back() -> None:
    assert display_name("Ada", "Lock user 1001", 1001) == "Ada"
    assert display_name(None, "Lock user 1001", 1001) == "Lock user 1001"
    assert display_name("  ", None, 1001) == "Lock user 1001"
    assert default_name(1001, None) == "Lock user 1001"
    assert default_name(1001, "Ada") == "Ada"


async def test_next_index_skips_empty_slots() -> None:
    records = {
        1: {
            "userIndex": 1,
            "userStatus": 1,
            "userUniqueID": 1001,
            "nextUserIndex": 4,
        },
        4: {
            "userIndex": 4,
            "userStatus": 1,
            "userUniqueID": 2002,
            "userName": "Ada",
            "nextUserIndex": None,
        },
    }

    async def fetch(index: int) -> dict[str, object]:
        assert index in records
        return records[index]

    slots = await collect_slots(fetch, 10)

    assert set(slots) == {1, 4}
    assert slots[4].suggested_name == "Ada"


async def test_missing_next_index_walks_the_table() -> None:
    seen: list[int] = []

    async def fetch(index: int) -> dict[str, object]:
        seen.append(index)
        if index == 2:
            return {
                "userIndex": 2,
                "userStatus": 1,
                "userUniqueID": 1001,
                "nextUserIndex": None,
            }
        return {"userIndex": index, "userStatus": None, "nextUserIndex": None}

    slots = await collect_slots(fetch, 3)

    assert seen == [1, 2, 3]
    assert slots[2].unique_id == 1001


async def test_null_next_index_ends_the_walk_after_a_skip() -> None:
    seen: list[int] = []

    async def fetch(index: int) -> dict[str, object]:
        seen.append(index)
        if index == 1:
            return {
                "userIndex": 1,
                "userStatus": 1,
                "userUniqueID": 1001,
                "nextUserIndex": 3,
            }
        return {
            "userIndex": 3,
            "userStatus": 1,
            "userUniqueID": 2002,
            "nextUserIndex": None,
        }

    slots = await collect_slots(fetch, 10)

    assert seen == [1, 3]
    assert set(slots) == {1, 3}


async def test_unique_id_zero_is_dropped_while_walking() -> None:
    async def fetch(index: int) -> dict[str, object]:
        return {
            "userIndex": index,
            "userStatus": 1,
            "userUniqueID": 0,
            "userName": "Card",
            "nextUserIndex": None,
        }

    assert await collect_slots(fetch, 1) == {}
