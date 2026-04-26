"""Shared pytest fixtures."""
import os
import pytest
from moto import mock_aws
import boto3


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Clear all backup-related env vars between tests so each test starts clean."""
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


@pytest.fixture
def mock_s3():
    """Mock S3 endpoint with two pre-created buckets — primary + mirror."""
    with mock_aws():
        # Set fake credentials so boto3 doesn't error trying to find real ones
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="primary-bucket")
        client.create_bucket(Bucket="mirror-bucket")
        yield client
