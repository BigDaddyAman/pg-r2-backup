"""Tests for the multi-destination backup logic."""
import pytest


def test_mirror_disabled_when_all_env_unset(monkeypatch):
    """With no MIRROR_* env vars set, mirror_config() returns None (mirror disabled)."""
    # All MIRROR_* unset by the autouse reset_env fixture.
    from main import mirror_config

    assert mirror_config() is None


def test_mirror_enabled_when_all_four_required_set(monkeypatch):
    """With all 4 required MIRROR_* set, mirror_config() returns a populated dict."""
    monkeypatch.setenv("MIRROR_ENDPOINT", "https://mirror.example.com")
    monkeypatch.setenv("MIRROR_BUCKET_NAME", "mirror-bucket")
    monkeypatch.setenv("MIRROR_ACCESS_KEY", "mirror-key")
    monkeypatch.setenv("MIRROR_SECRET_KEY", "mirror-secret")

    from main import mirror_config

    cfg = mirror_config()
    assert cfg is not None
    assert cfg["endpoint"] == "https://mirror.example.com"
    assert cfg["bucket_name"] == "mirror-bucket"
    assert cfg["access_key"] == "mirror-key"
    assert cfg["secret_key"] == "mirror-secret"


def test_mirror_partial_config_raises(monkeypatch):
    """Setting some but not all required MIRROR_* fields fails fast with a clear error."""
    monkeypatch.setenv("MIRROR_ENDPOINT", "https://mirror.example.com")
    monkeypatch.setenv("MIRROR_BUCKET_NAME", "mirror-bucket")
    # MIRROR_ACCESS_KEY + MIRROR_SECRET_KEY deliberately unset

    from main import mirror_config

    with pytest.raises(ValueError, match="MIRROR_ACCESS_KEY"):
        mirror_config()


def test_mirror_region_falls_back_to_s3_region(monkeypatch):
    """MIRROR_REGION defaults to S3_REGION if unset."""
    monkeypatch.setenv("S3_REGION", "eu-west-1")
    monkeypatch.setenv("MIRROR_ENDPOINT", "https://mirror.example.com")
    monkeypatch.setenv("MIRROR_BUCKET_NAME", "mirror-bucket")
    monkeypatch.setenv("MIRROR_ACCESS_KEY", "mirror-key")
    monkeypatch.setenv("MIRROR_SECRET_KEY", "mirror-secret")

    from main import mirror_config

    cfg = mirror_config()
    assert cfg["region"] == "eu-west-1"


def test_mirror_max_backups_falls_back_to_max_backups(monkeypatch):
    """MIRROR_MAX_BACKUPS defaults to MAX_BACKUPS if unset."""
    monkeypatch.setenv("MAX_BACKUPS", "30")
    monkeypatch.setenv("MIRROR_ENDPOINT", "https://mirror.example.com")
    monkeypatch.setenv("MIRROR_BUCKET_NAME", "mirror-bucket")
    monkeypatch.setenv("MIRROR_ACCESS_KEY", "mirror-key")
    monkeypatch.setenv("MIRROR_SECRET_KEY", "mirror-secret")

    from main import mirror_config

    cfg = mirror_config()
    assert cfg["max_backups"] == 30
