"""Tests for the integration manifest and HACS metadata."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.matter_lock_identity import __version__

ROOT = Path(__file__).parent.parent
MANIFEST = ROOT / "custom_components" / "matter_lock_identity" / "manifest.json"
HACS = ROOT / "hacs.json"


def _load(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert isinstance(loaded, dict)
    return loaded


class TestManifest:
    """Test cases for the integration manifest."""

    def test_manifest_exists(self) -> None:
        """Test that manifest.json exists."""
        assert MANIFEST.exists()

    def test_manifest_valid_json(self) -> None:
        """Test that manifest.json is valid JSON."""
        assert isinstance(_load(MANIFEST), dict)

    def test_manifest_required_keys(self) -> None:
        """Test that manifest.json contains required keys."""
        manifest = _load(MANIFEST)
        required_keys = [
            "domain",
            "name",
            "version",
            "codeowners",
            "config_flow",
            "dependencies",
            "documentation",
            "iot_class",
            "issue_tracker",
            "requirements",
        ]
        for key in required_keys:
            assert key in manifest, f"Missing required key: {key}"

    def test_manifest_domain(self) -> None:
        """Test that manifest domain is correct."""
        assert _load(MANIFEST)["domain"] == "matter_lock_identity"

    def test_manifest_version_matches_init(self) -> None:
        """Test that manifest version matches the package version."""
        assert _load(MANIFEST)["version"] == __version__

    def test_manifest_requirements(self) -> None:
        """Test that manifest has no extra Python requirements."""
        manifest = _load(MANIFEST)
        assert manifest["requirements"] == []

    def test_manifest_depends_on_matter(self) -> None:
        """Test that the integration uses the Matter integration."""
        assert _load(MANIFEST)["dependencies"] == ["matter"]


class TestHACSManifest:
    """Test cases for the HACS manifest."""

    def test_hacs_json_exists(self) -> None:
        """Test that hacs.json exists."""
        assert HACS.exists()

    def test_hacs_json_valid(self) -> None:
        """Test that hacs.json is valid JSON."""
        assert isinstance(_load(HACS), dict)

    def test_hacs_json_required_keys(self) -> None:
        """Test that hacs.json contains required keys."""
        hacs_config = _load(HACS)
        required_keys = [
            "name",
            "content_in_root",
            "homeassistant",
            "render_readme",
        ]
        for key in required_keys:
            assert key in hacs_config, f"Missing required key: {key}"

    def test_hacs_json_no_invalid_keys(self) -> None:
        """Test that hacs.json doesn't contain invalid keys."""
        assert "iot_class" not in _load(HACS)
