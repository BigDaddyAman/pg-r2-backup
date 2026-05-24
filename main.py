import os
import subprocess
import boto3
from boto3.session import Config
from datetime import datetime, timezone
from boto3.s3.transfer import TransferConfig
from dotenv import load_dotenv, find_dotenv
import time
import schedule
import py7zr
import shutil
import sys 

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

def get_database_url():
    if USE_PUBLIC_URL:
        if not DATABASE_PUBLIC_URL:
            raise ValueError("[ERROR] DATABASE_PUBLIC_URL not set but USE_PUBLIC_URL=true!")
        return DATABASE_PUBLIC_URL

    if not DATABASE_URL:
        raise ValueError("[ERROR] DATABASE_URL not set!")
    return DATABASE_URL

def run_backup():
    success = True
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

    pg_format, ext = format_map.get(
        DUMP_FORMAT.lower(),
        ("c", "dump")
    )

    is_custom_format = pg_format == "c"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    backup_file = f"{FILENAME_PREFIX}_{timestamp}.{ext}"

    compressed_file = (
        f"{backup_file}.7z"
        if BACKUP_PASSWORD
        else (
            backup_file
            if is_custom_format
            else f"{backup_file}.gz"
        )
    )

    compressed_file_r2 = f"{BACKUP_PREFIX}{compressed_file}"

    try:
        log(f"[INFO] Creating backup {compressed_file}")

        dump_cmd = [
            "pg_dump",
            f"--dbname={database_url}",
            "-F", pg_format,
            "--no-owner",
            "--no-acl"
        ]

        #
        # ENCRYPTED BACKUP
        #
        if BACKUP_PASSWORD:

            dump_cmd.extend(["-f", backup_file])

            subprocess.run(dump_cmd, check=True)

            log("[INFO] Encrypting backup with 7z...")

            with py7zr.SevenZipFile(
                compressed_file,
                "w",
                password=BACKUP_PASSWORD
            ) as archive:
                archive.write(backup_file)

            log("[SUCCESS] Backup encrypted successfully")

        #
        # CUSTOM FORMAT (pg_dump internal compression)
        #
        elif is_custom_format:

            dump_cmd.extend([
                "-Z", "6",
                "-f", compressed_file
            ])

            subprocess.run(dump_cmd, check=True)

            log("[SUCCESS] PostgreSQL compressed backup created")

        #
        # SQL/TAR STREAMING GZIP
        #
        else:

            log("[INFO] Streaming pg_dump to gzip...")

            with open(compressed_file, "wb") as f_out:

                dump_proc = subprocess.Popen(
                    dump_cmd,
                    stdout=subprocess.PIPE
                )

                gzip_proc = subprocess.Popen(
                    ["gzip"],
                    stdin=dump_proc.stdout,
                    stdout=f_out
                )

                dump_proc.stdout.close()

                gzip_proc.communicate()
                dump_return = dump_proc.wait()
                gzip_return = gzip_proc.wait()

                if dump_return != 0:
                    raise subprocess.CalledProcessError(
                        dump_proc.returncode,
                        dump_cmd
                    )

                if gzip_proc.returncode != 0:
                    raise subprocess.CalledProcessError(
                        gzip_proc.returncode,
                        "gzip"
                    )

            log("[SUCCESS] Backup streamed and compressed")

    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Backup creation failed: {e}")
        return False
    finally:

        if (
            BACKUP_PASSWORD
            and os.path.exists(backup_file)
        ):
            os.remove(backup_file)
            

    #
    # FILE SIZE
    #
    if compressed_file and os.path.exists(compressed_file):

        size = os.path.getsize(compressed_file)

        log(
            f"[INFO] Final backup size: "
            f"{size / 1024 / 1024:.2f} MB"
        )

    #
    # UPLOAD TO R2
    #
    try:

        client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(
                s3={"addressing_style": "path"},
                retries={
                    "max_attempts": 5,
                    "mode": "standard"
                },
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
            Config=transfer_config
        )

        #
        # VERIFY UPLOAD
        #
        remote = client.head_object(
            Bucket=R2_BUCKET_NAME,
            Key=compressed_file_r2
        )

        remote_size = remote["ContentLength"]
        local_size = os.path.getsize(compressed_file)

        if remote_size != local_size:
            raise Exception(
                "Uploaded file size mismatch!"
            )

        log(
            f"[SUCCESS] Backup uploaded: "
            f"{compressed_file_r2}"
        )

        #
        # CLEAN OLD BACKUPS
        #
        paginator = client.get_paginator(
            "list_objects_v2"
        )

        backups = []

        for page in paginator.paginate(
            Bucket=R2_BUCKET_NAME,
            Prefix=BACKUP_PREFIX
        ):

            if "Contents" in page:
                backups.extend(page["Contents"])

        backups = sorted(
            backups,
            key=lambda x: x["LastModified"],
            reverse=True
        )

        for obj in backups[MAX_BACKUPS:]:

            client.delete_object(
                Bucket=R2_BUCKET_NAME,
                Key=obj["Key"]
            )

            log(
                f"[INFO] Deleted old backup: "
                f"{obj['Key']}"
            )

    except Exception as e:

        log(f"[ERROR] R2 operation failed: {e}")
        return False
    finally:
        if (compressed_file and os.path.exists(compressed_file)
        ):
            if KEEP_LOCAL_BACKUP:
                log("[INFO] Keeping local backup "
                    "(KEEP_LOCAL_BACKUP=true)"
                )
            else:
                os.remove(compressed_file)
                log("[INFO] Local backup deleted")
                              
    return success

if __name__ == "__main__":
    log("[INFO] Starting backup process...")

    success = run_backup()

    if RUN_ONCE:
        sys.exit(0 if success else 1)

    log(f"[INFO] Scheduled backup time: {BACKUP_TIME} UTC")

    schedule.every().day.at(BACKUP_TIME).do(run_backup)

    while True:
        schedule.run_pending()
        time.sleep(60)
