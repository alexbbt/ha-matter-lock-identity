"""Tests for small helpers that do not need Home Assistant."""

from __future__ import annotations

from custom_components.matter_lock_identity.const import is_legacy_lock_device


def test_legacy_lock_device_matches_node_identifier() -> None:
    assert is_legacy_lock_device({("matter_lock_identity", "node-39")})


def test_legacy_lock_device_ignores_hub_and_other_domains() -> None:
    assert not is_legacy_lock_device({("matter_lock_identity", "hub")})
    assert not is_legacy_lock_device({("matter", "deviceid_abc")})


def test_legacy_lock_device_accepts_longer_identifier_tuples() -> None:
    assert is_legacy_lock_device({("matter_lock_identity", "node-40", "extra")})
