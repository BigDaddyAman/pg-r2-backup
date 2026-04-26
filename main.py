import os
import subprocess
import boto3
from botocore.config import Config
from datetime import datetime, timezone
from boto3.s3.transfer import TransferConfig
from dotenv import load_dotenv, find_dotenv
import time
import schedule
import botocore.utils

# Monkey-patch: bypass endpoint URL validation for Cloudflare R2 EU jurisdiction endpoints
botocore.utils.is_valid_endpoint_url = lambda endpoint_url: True
import py7zr
import shutil
import gzip

load_dotenv(find_dotenv(usecwd=True), override=True)

## ENV

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
MAX_BACKUPS = int(os.environ.get("MAX_BACKUPS", 7))
KEEP_LOCAL_BACKUP = os.environ.get("KEEP_LOCAL_BACKUP", "false").lower() == "true"
BACKUP_PREFIX = os.environ.get("BACKUP_PREFIX", "")
FILENAME_PREFIX = os.environ.get("FILENAME_PREFIX", "backup")
DUMP_FORMAT = os.environ.get("DUMP_FORMAT", "dump")
BACKUP_PASSWORD = os.environ.get("BACKUP_PASSWORD")
USE_PUBLIC_URL = os.environ.get("USE_PUBLIC_URL", "false").lower() == "true"
BACKUP_TIME = os.environ.get("BACKUP_TIME", "00:00")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

def log(msg):
    print(msg, flush=True)

## Validate BACKUP_TIME
try:
    hour, minute = BACKUP_TIME.split(":")
    if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
        raise ValueError
except ValueError:
    log("[WARNING] Invalid BACKUP_TIME format. Using default: 00:00")
    BACKUP_TIME = "00:00"

## Mirror destination (optional, opt-in — secondary S3-compatible backup target)

MIRROR_ENDPOINT = os.environ.get("MIRROR_ENDPOINT")
MIRROR_BUCKET_NAME = os.environ.get("MIRROR_BUCKET_NAME")
MIRROR_ACCESS_KEY = os.environ.get("MIRROR_ACCESS_KEY")
MIRROR_SECRET_KEY = os.environ.get("MIRROR_SECRET_KEY")
MIRROR_REGION = os.environ.get("MIRROR_REGION")
MIRROR_MAX_BACKUPS = os.environ.get("MIRROR_MAX_BACKUPS")


def mirror_config():
    """
    Return a dict describing the mirror destination, or None if mirror is disabled.

    All four core fields (ENDPOINT, BUCKET_NAME, ACCESS_KEY, SECRET_KEY) must be
    set together. Partial config raises ValueError so misconfiguration is loud.
    """
    fields = {
        "MIRROR_ENDPOINT": MIRROR_ENDPOINT,
        "MIRROR_BUCKET_NAME": MIRROR_BUCKET_NAME,
        "MIRROR_ACCESS_KEY": MIRROR_ACCESS_KEY,
        "MIRROR_SECRET_KEY": MIRROR_SECRET_KEY,
    }
    set_fields = {k: v for k, v in fields.items() if v}
    if not set_fields:
        return None  # mirror disabled
    if len(set_fields) < len(fields):
        missing = [k for k, v in fields.items() if not v]
        raise ValueError(
            f"Mirror destination misconfigured: {', '.join(missing)} not set. "
            f"Set all four MIRROR_* fields together, or unset all four to disable the mirror."
        )
    return {
        "endpoint": MIRROR_ENDPOINT,
        "bucket_name": MIRROR_BUCKET_NAME,
        "access_key": MIRROR_ACCESS_KEY,
        "secret_key": MIRROR_SECRET_KEY,
        "region": MIRROR_REGION or S3_REGION,
        "max_backups": int(MIRROR_MAX_BACKUPS) if MIRROR_MAX_BACKUPS else MAX_BACKUPS,
    }


def upload_to_destination(dest, local_file, remote_key):
    """
    Upload a single file to one S3-compatible destination, then prune old backups
    beyond dest['max_backups']. Logs are prefixed with dest['label'] so multi-destination
    runs are easy to diagnose.

    Returns True if upload succeeded, False if it failed. Retention failures are
    logged but don't flip the return value — retention is best-effort cleanup.
    """
    label = dest["label"]
    try:
        client = boto3.client(
            "s3",
            endpoint_url=dest["endpoint"],
            aws_access_key_id=dest["access_key"],
            aws_secret_access_key=dest["secret_key"],
            region_name=dest["region"],
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

        config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True,
        )

        log(f"[{label}] uploading {remote_key}")
        client.upload_file(local_file, dest["bucket_name"], remote_key, Config=config)
        size_mb = os.path.getsize(local_file) / 1024 / 1024
        log(f"[{label}] uploaded ({size_mb:.2f} MB)")
    except Exception as e:
        log(f"[{label}] FAILED: {e}")
        return False

    # Best-effort retention (don't fail the run on retention errors)
    try:
        objects = client.list_objects_v2(Bucket=dest["bucket_name"], Prefix=BACKUP_PREFIX)
        contents = objects.get("Contents", [])
        if contents:
            backups = sorted(contents, key=lambda x: x["LastModified"], reverse=True)
            pruned = 0
            for obj in backups[dest["max_backups"]:]:
                client.delete_object(Bucket=dest["bucket_name"], Key=obj["Key"])
                pruned += 1
            if pruned:
                log(f"[{label}] retention: pruned {pruned} backup(s) beyond {dest['max_backups']}")
    except Exception as e:
        log(f"[{label}] retention WARNING (non-fatal): {e}")

    return True


def get_database_url():
    if USE_PUBLIC_URL:
        if not DATABASE_PUBLIC_URL:
            raise ValueError("[ERROR] DATABASE_PUBLIC_URL not set but USE_PUBLIC_URL=true!")
        return DATABASE_PUBLIC_URL

    if not DATABASE_URL:
        raise ValueError("[ERROR] DATABASE_URL not set!")
    return DATABASE_URL

def gzip_compress(src):
    dst = src + ".gz"
    with open(src, "rb") as f_in:
        with gzip.open(dst, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return dst

def run_backup():
    if shutil.which("pg_dump") is None:
        log("[ERROR] pg_dump not found. Install postgresql-client.")
        return

    database_url = get_database_url()
    log(f"[INFO] Using {'public' if USE_PUBLIC_URL else 'private'} database URL")

    format_map = {
        "sql": ("p", "sql"),
        "plain": ("p", "sql"),
        "dump": ("c", "dump"),
        "custom": ("c", "dump"),
        "tar": ("t", "tar")
    }
    pg_format, ext = format_map.get(DUMP_FORMAT.lower(), ("c", "dump"))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = f"{FILENAME_PREFIX}_{timestamp}.{ext}"

    compressed_file = (
        f"{backup_file}.7z" if BACKUP_PASSWORD else f"{backup_file}.gz"
    )

    compressed_file_r2 = f"{BACKUP_PREFIX}{compressed_file}"

    ## Create backup
    try:
        log(f"[INFO] Creating backup {backup_file}")

        dump_cmd = [
            "pg_dump",
            f"--dbname={database_url}",
            "-F", pg_format,
            "--no-owner",
            "--no-acl",
            "-f", backup_file
        ]

        subprocess.run(dump_cmd, check=True)

        if BACKUP_PASSWORD:
            log("[INFO] Encrypting backup with 7z...")
            with py7zr.SevenZipFile(compressed_file, "w", password=BACKUP_PASSWORD) as archive:
                archive.write(backup_file)
            log("[SUCCESS] Backup encrypted successfully")
        else:
            log("[INFO] Compressing backup with gzip...")
            gzip_compress(backup_file)
            log("[SUCCESS] Backup compressed successfully")

    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Backup creation failed: {e}")
        return
    finally:
        if os.path.exists(backup_file):
            os.remove(backup_file)

    ## Upload to R2
    if os.path.exists(compressed_file):
        size = os.path.getsize(compressed_file)
        log(f"[INFO] Final backup size: {size / 1024 / 1024:.2f} MB")

    try:
        client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(signature_version="s3v4", 
                s3={"addressing_style": "path"}
            )
        )

        config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True
        )

        client.upload_file(
            compressed_file,
            R2_BUCKET_NAME,
            compressed_file_r2,
            Config=config
        )

        log(f"[SUCCESS] Backup uploaded: {compressed_file_r2}")

        objects = client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=BACKUP_PREFIX
        )

        if "Contents" in objects:
            backups = sorted(
                objects["Contents"],
                key=lambda x: x["LastModified"],
                reverse=True
            )

            for obj in backups[MAX_BACKUPS:]:
                client.delete_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=obj["Key"]
                )
                log(f"[INFO] Deleted old backup: {obj['Key']}")

    except Exception as e:
        log(f"[ERROR] R2 operation failed: {e}")
    finally:
        if os.path.exists(compressed_file):
                if KEEP_LOCAL_BACKUP:
                    log("[INFO] Keeping local backup (KEEP_LOCAL_BACKUP=true)")
                else:
                    os.remove(compressed_file)
                    log("[INFO] Local backup deleted")

if __name__ == "__main__":
    log("[INFO] Starting backup scheduler...")
    log(f"[INFO] Scheduled backup time: {BACKUP_TIME} UTC")

    schedule.every().day.at(BACKUP_TIME).do(run_backup)

    run_backup()

    while True:
        schedule.run_pending()
        time.sleep(60)
