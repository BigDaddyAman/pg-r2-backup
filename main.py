
import os
import re
import subprocess
import boto3
from boto3.session import Config
from datetime import datetime, timezone
from boto3.s3.transfer import TransferConfig
import time
import schedule
import py7zr
import shutil
import gzip
import sys
import hashlib

from filelock import FileLock, Timeout

from config import (
    DATABASE_URL,
    DATABASE_PUBLIC_URL,
    R2_ACCESS_KEY,
    R2_SECRET_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT,
    MAX_BACKUPS,
    KEEP_LOCAL_BACKUP,
    BACKUP_PREFIX,
    FILENAME_PREFIX,
    DUMP_FORMAT,
    BACKUP_PASSWORD,
    USE_PUBLIC_URL,
    BACKUP_TIME,
    S3_REGION,
    RUN_MODE,
)

def log(msg):
    print(msg, flush=True)

def get_database_url():
    database_url = (
        DATABASE_PUBLIC_URL
        if USE_PUBLIC_URL
        else DATABASE_URL
    )

    if not database_url:
        raise ValueError(
            f"[ERROR] {'DATABASE_PUBLIC_URL' if USE_PUBLIC_URL else 'DATABASE_URL'} is not configured."
        )

    if not database_url.startswith(("postgres://", "postgresql://")):
        raise ValueError("[ERROR] Invalid PostgreSQL connection URL.")

    return database_url

def gzip_compress(src):
    dst = src + ".gz"
    with open(src, "rb") as f_in:
        with gzip.open(dst, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return dst

def sha256_of(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)

    return digest.hexdigest()

def acquire_backup_lock():
    lock = FileLock(".backup.lock", timeout=0)

    try:
        lock.acquire()
        log("[INFO] Backup lock acquired.")
        return lock

    except Timeout:
        log("[WARNING] Another backup is already running.")
        return None

def run_backup():
    lock_file = acquire_backup_lock()

    if lock_file is None:
        return False

    compressed_file = None
    upload_success = False

    try:
        if MAX_BACKUPS < 1:
            raise ValueError("MAX_BACKUPS must be at least 1")

        if shutil.which("pg_dump") is None:
            raise RuntimeError("pg_dump not found. Install postgresql-client.")

        database_url = get_database_url()
        log(f"[INFO] Using {'public' if USE_PUBLIC_URL else 'private'} database URL")

        format_map = {
            "sql": ("p", "sql"),
            "plain": ("p", "sql"),
            "dump": ("c", "dump"),
            "custom": ("c", "dump"),
            "tar": ("t", "tar")
        }

        pg_format, ext = format_map[DUMP_FORMAT]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_file = f"{FILENAME_PREFIX}_{timestamp}.{ext}"
        compressed_file = f"{backup_file}.7z" if BACKUP_PASSWORD else f"{backup_file}.gz"
        compressed_file_r2 = f"{BACKUP_PREFIX}{compressed_file}"

        try:
            log(f"[INFO] Creating backup {backup_file}")

            subprocess.run([
                "pg_dump",
                "--dbname", database_url,
                "-F", pg_format,
                "--no-owner",
                "--no-acl",
                "-f", backup_file
            ], check=True)

            if BACKUP_PASSWORD:
                log("[INFO] Encrypting backup with 7z...")
                with py7zr.SevenZipFile(compressed_file, "w", password=BACKUP_PASSWORD) as archive:
                    archive.write(backup_file)
                log("[SUCCESS] Backup encrypted successfully")
            else:
                log("[INFO] Compressing backup with gzip...")
                gzip_compress(backup_file)
                log("[SUCCESS] Backup compressed successfully")

        finally:
            if os.path.exists(backup_file):
                os.remove(backup_file)

        if not os.path.isfile(compressed_file) or os.path.getsize(compressed_file) == 0:
            raise ValueError("Compressed backup file is missing or empty.")

        size = os.path.getsize(compressed_file)
        log(f"[INFO] Final backup size: {size / 1024 / 1024:.2f} MB")

        local_sha256 = sha256_of(compressed_file)
        log(f"[INFO] SHA-256: {local_sha256}")

        client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(
                s3={"addressing_style": "path"},
                retries={"max_attempts": 5, "mode": "standard"},
                connect_timeout=30,
                read_timeout=300
            )
        )

        transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True
        )

        log("[INFO] Uploading backup to R2...")

        client.upload_file(
            compressed_file,
            R2_BUCKET_NAME,
            compressed_file_r2,
            ExtraArgs={"Metadata": {
                "managed-by": "postgres-backup-app",
                "sha256": local_sha256
            }},
            Config=transfer_config
        )

        remote = client.head_object(Bucket=R2_BUCKET_NAME, Key=compressed_file_r2)

        if remote["ContentLength"] != size:
            raise ValueError("Uploaded file size mismatch.")

        if remote.get("Metadata", {}).get("managed-by") != "postgres-backup-app":
            raise ValueError("Backup ownership metadata verification failed.")

        remote_sha256 = remote.get("Metadata", {}).get("sha256")

        if remote_sha256 != local_sha256:
            raise ValueError("Uploaded checksum metadata mismatch.")

        upload_success = True
        log(
            f"[SUCCESS] Backup uploaded: {compressed_file_r2} "
            f"| size={size} bytes | sha256={local_sha256}"
        )

        log("[INFO] Starting safe backup retention...")

        paginator = client.get_paginator("list_objects_v2")
        backups = []

        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=BACKUP_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]

                if not is_valid_backup(key):
                    continue

                try:
                    head = client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
                except Exception as e:
                    log(f"[WARNING] Cannot verify {key}: {e}. Skipping.")
                    continue

                if head.get("Metadata", {}).get("managed-by") != "postgres-backup-app":
                    log(f"[INFO] Skipping unmanaged object: {key}")
                    continue

                backups.append(obj)

        backups.sort(
            key=lambda x: (x["LastModified"], x["Key"]),
            reverse=True
        )
        log(f"[INFO] Found {len(backups)} verified backups.")

        verified_keys = {obj["Key"] for obj in backups}

        if compressed_file_r2 not in verified_keys:
            raise RuntimeError("New backup missing from verified retention list. Aborting cleanup.")

        retention_errors = 0
        deleted_count = 0

        for obj in backups[MAX_BACKUPS:]:
            key = obj["Key"]

            try:
                if not is_valid_backup(key):
                    raise ValueError("Invalid backup filename.")

                head = client.head_object(Bucket=R2_BUCKET_NAME, Key=key)

                if head.get("Metadata", {}).get("managed-by") != "postgres-backup-app":
                    raise ValueError("Unmanaged object; refusing deletion.")

                client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
                deleted_count += 1
                log(f"[INFO] Deleted old backup: {key}")

            except Exception as e:
                retention_errors += 1
                log(f"[ERROR] Could not delete {key}: {e}")

        if retention_errors:
            log(f"[WARNING] Retention completed with {retention_errors} error(s).")
        else:
            log(f"[SUCCESS] Retention completed. Deleted {deleted_count} old backup(s).")

        return True

    except Exception as e:
        log(f"[ERROR] Backup process failed: {e}")
        return False

    finally:
        if compressed_file and os.path.exists(compressed_file):
            if KEEP_LOCAL_BACKUP or not upload_success:
                log("[INFO] Keeping local backup (KEEP_LOCAL_BACKUP=true or upload failed)")
            else:
                try:
                    os.remove(compressed_file)
                    log("[INFO] Local backup deleted")
                except OSError as e:
                    log(f"[WARNING] Local cleanup failed: {e}")

        if lock_file:
            lock_file.release()
            log("[INFO] Backup lock released.")

def is_valid_backup(key):
    if not key.startswith(BACKUP_PREFIX):
        return False

    filename = key[len(BACKUP_PREFIX):]

    if not filename or "/" in filename:
        return False

    pattern = (
        rf"{re.escape(FILENAME_PREFIX)}_"
        r"(\d{8})_(\d{6})_(\d{6})"
        r"\.(?:dump|sql|tar)"
        r"(?:\.gz|\.7z)"
    )

    match = re.fullmatch(pattern, filename)

    if not match:
        return False

    try:
        datetime.strptime(
            f"{match.group(1)}_{match.group(2)}_{match.group(3)}",
            "%Y%m%d_%H%M%S_%f"
        )
        return True

    except ValueError:
        return False


def scheduled_backup():
    try:
        success = run_backup()

        if not success:
            log("[ERROR] Scheduled backup failed.")

    except Exception as e:
        log(f"[ERROR] Scheduled backup exception: {e}")


def run_daemon():
    log(f"[INFO] Daemon mode: scheduled daily at {BACKUP_TIME} UTC")

    schedule.every().day.at(BACKUP_TIME, "UTC").do(scheduled_backup)

    while True:
        try:
            schedule.run_pending()
            time.sleep(30)

        except KeyboardInterrupt:
            log("[INFO] Backup service stopped by user")
            break

        except Exception as e:
            log(f"[ERROR] Scheduler error: {e}")
            time.sleep(30)


def main():
    log(f"[INFO] Starting backup service in '{RUN_MODE}' mode")

    if RUN_MODE in ("railway", "cli"):
        success = run_backup()
        sys.exit(0 if success else 1)

    elif RUN_MODE == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()

