import os
import subprocess
import sys
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
RUN_ONCE = os.environ.get("RUN_ONCE", "false").lower() == "true"

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

    Note: ENDPOINT may be empty (e.g. when targeting AWS-native S3 with regional
    defaults); we treat empty ENDPOINT as a deliberate None.
    """
    fields = {
        "MIRROR_ENDPOINT": MIRROR_ENDPOINT,
        "MIRROR_BUCKET_NAME": MIRROR_BUCKET_NAME,
        "MIRROR_ACCESS_KEY": MIRROR_ACCESS_KEY,
        "MIRROR_SECRET_KEY": MIRROR_SECRET_KEY,
    }
    # Endpoint is connection-level config (like region) — optional, since AWS-native
    # S3 works with regional defaults. The other three are identity and must coexist.
    identity_fields = {k: v for k, v in fields.items() if k != "MIRROR_ENDPOINT"}
    set_identity = {k: v for k, v in identity_fields.items() if v}
    set_fields = {k: v for k, v in fields.items() if v}

    if not set_fields:
        return None  # mirror disabled
    if len(set_identity) < len(identity_fields):
        missing = [k for k, v in fields.items() if not v]
        raise ValueError(
            f"Mirror destination misconfigured: {', '.join(missing)} not set. "
            f"Set all four MIRROR_* fields together, or unset all four to disable the mirror."
        )
    return {
        "endpoint": MIRROR_ENDPOINT or None,
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
        return False

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
        return False
    finally:
        if os.path.exists(backup_file):
            os.remove(backup_file)

    ## Upload to all configured destinations

    if os.path.exists(compressed_file):
        size = os.path.getsize(compressed_file)
        log(f"[dump] final backup size: {size / 1024 / 1024:.2f} MB")

    destinations = [
        {
            "label": "r2",
            "endpoint": R2_ENDPOINT or None,
            "bucket_name": R2_BUCKET_NAME,
            "access_key": R2_ACCESS_KEY,
            "secret_key": R2_SECRET_KEY,
            "region": S3_REGION,
            "max_backups": MAX_BACKUPS,
        }
    ]

    mirror = mirror_config()
    if mirror:
        destinations.append({"label": "mirror", **mirror})

    results = []
    for dest in destinations:
        ok = upload_to_destination(dest, compressed_file, compressed_file_r2)
        results.append((dest["label"], ok))

    if os.path.exists(compressed_file):
        if KEEP_LOCAL_BACKUP:
            log("[done] keeping local backup (KEEP_LOCAL_BACKUP=true)")
        else:
            os.remove(compressed_file)
            log("[done] local backup deleted")

    failed = [label for label, ok in results if not ok]
    if failed:
        log(f"[done] {len(failed)} of {len(results)} destination(s) failed: {', '.join(failed)} — overall FAIL")
        return False
    log(f"[done] all {len(results)} destination(s) OK")
    return True

def main_entrypoint():
    """
    Entry point. Two modes:

    - RUN_ONCE=true: run a single backup, exit 0 on success, 1 on failure.
      Use this when deployed as a Railway cron job (exit code triggers
      Railway's deploy-failed alerts).

    - RUN_ONCE unset/false (default): daemon mode. Run once on startup, then
      schedule daily runs at BACKUP_TIME. Original pg-r2-backup behaviour —
      preserved for backwards compatibility with existing always-on deploys.
    """
    if RUN_ONCE:
        log("[INFO] RUN_ONCE=true — single-shot mode")
        success = run_backup()
        sys.exit(0 if success else 1)

    log("[INFO] starting backup scheduler (daemon mode)")
    log(f"[INFO] scheduled backup time: {BACKUP_TIME} UTC")

    schedule.every().day.at(BACKUP_TIME).do(run_backup)

    run_backup()  # run immediately on startup (preserves existing behaviour)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main_entrypoint()
