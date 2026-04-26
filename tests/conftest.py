"""Shared pytest fixtures."""
import sys

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def reset_env(monkeypatch, tmp_path):
    """
    Clear all backup-related env vars between tests so each test starts clean.

    Also chdir to an empty tmp dir to neutralize main.py's `load_dotenv(find_dotenv(usecwd=True))`,
    and evict main from sys.modules so each test re-imports it fresh (its module-level
    constants like MIRROR_ENDPOINT are captured at import time, so without re-import a
    second test would see the first test's env values).
    """
    for key in (
        "DATABASE_URL", "DATABASE_PUBLIC_URL", "USE_PUBLIC_URL",
        "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET_NAME",
        "R2_ENDPOINT", "S3_REGION", "MAX_BACKUPS",
        "MIRROR_ENDPOINT", "MIRROR_BUCKET_NAME", "MIRROR_ACCESS_KEY",
        "MIRROR_SECRET_KEY", "MIRROR_REGION", "MIRROR_MAX_BACKUPS",
        "RUN_ONCE", "BACKUP_TIME", "FILENAME_PREFIX", "BACKUP_PREFIX",
        "DUMP_FORMAT", "BACKUP_PASSWORD", "KEEP_LOCAL_BACKUP",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    sys.modules.pop("main", None)


@pytest.fixture
def mock_s3(monkeypatch):
    """Mock S3 endpoint with two pre-created buckets — primary + mirror."""
    # Use monkeypatch so AWS_* don't leak into subsequent tests; otherwise
    # boto3's credential resolution can shadow values that later tests pass explicitly.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="primary-bucket")
        client.create_bucket(Bucket="mirror-bucket")
        yield client
