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


def test_upload_to_destination_uploads_file_and_logs(monkeypatch, mock_s3, tmp_path, capsys):
    """upload_to_destination() puts the file in the named bucket and emits prefixed logs."""
    backup_file = tmp_path / "backup_test.dump.gz"
    backup_file.write_bytes(b"fake backup data")

    from main import upload_to_destination

    dest = {
        "label": "r2",
        "endpoint": None,  # moto handles regional default
        "bucket_name": "primary-bucket",
        "access_key": "test",
        "secret_key": "test",
        "region": "us-east-1",
        "max_backups": 7,
    }

    success = upload_to_destination(dest, str(backup_file), "backup_test.dump.gz")

    assert success is True
    objects = mock_s3.list_objects_v2(Bucket="primary-bucket")
    assert objects["KeyCount"] == 1
    assert objects["Contents"][0]["Key"] == "backup_test.dump.gz"

    captured = capsys.readouterr()
    assert "[r2]" in captured.out
    assert "uploaded" in captured.out


def test_upload_to_destination_returns_false_on_failure(monkeypatch, tmp_path, capsys):
    """upload_to_destination() returns False (and logs ERROR) when the upload fails."""
    backup_file = tmp_path / "backup_test.dump.gz"
    backup_file.write_bytes(b"fake backup data")

    from main import upload_to_destination

    # Point at a nonexistent endpoint so boto3 fails
    dest = {
        "label": "mirror",
        "endpoint": "http://localhost:1",  # no server here
        "bucket_name": "mirror-bucket",
        "access_key": "test",
        "secret_key": "test",
        "region": "us-east-1",
        "max_backups": 7,
    }

    success = upload_to_destination(dest, str(backup_file), "backup_test.dump.gz")

    assert success is False
    captured = capsys.readouterr()
    assert "[mirror]" in captured.out
    assert "FAILED" in captured.out or "ERROR" in captured.out


def test_upload_to_destination_prunes_old_backups(monkeypatch, mock_s3, tmp_path, capsys):
    """After uploading, old backups beyond max_backups are deleted."""
    # Pre-populate the bucket with 5 fake old backups
    for i in range(5):
        mock_s3.put_object(Bucket="primary-bucket", Key=f"backup_old_{i}.dump.gz", Body=b"old")

    backup_file = tmp_path / "backup_new.dump.gz"
    backup_file.write_bytes(b"fake")

    from main import upload_to_destination

    dest = {
        "label": "r2",
        "endpoint": None,
        "bucket_name": "primary-bucket",
        "access_key": "test",
        "secret_key": "test",
        "region": "us-east-1",
        "max_backups": 3,  # keep only 3 newest
    }

    success = upload_to_destination(dest, str(backup_file), "backup_new.dump.gz")

    assert success is True
    objects = mock_s3.list_objects_v2(Bucket="primary-bucket")
    # We had 5 old + 1 new = 6 total, pruned to 3 = 3 deleted
    assert objects["KeyCount"] == 3
