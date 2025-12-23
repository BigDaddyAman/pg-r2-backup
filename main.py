import os
import subprocess
import boto3
from datetime import datetime, timezone
from boto3.s3.transfer import TransferConfig
from urllib.parse import urlparse
from dotenv import load_dotenv
import time
import schedule
import py7zr
import shutil

load_dotenv()

##Env

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
MAX_BACKUPS = int(os.environ.get("MAX_BACKUPS", 7))
BACKUP_PREFIX = os.environ.get("BACKUP_PREFIX", "")
FILENAME_PREFIX = os.environ.get("FILENAME_PREFIX", "backup")
DUMP_FORMAT = os.environ.get("DUMP_FORMAT", "dump")
BACKUP_PASSWORD = os.environ.get("BACKUP_PASSWORD")
USE_PUBLIC_URL = os.environ.get("USE_PUBLIC_URL", "false").lower() == "true"
BACKUP_TIME = os.environ.get("BACKUP_TIME", "00:00")

def log(msg):
    print(msg, flush=True)

try:
    hour, minute = BACKUP_TIME.split(":")
    if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
        log("[WARNING] Invalid BACKUP_TIME format. Using default: 00:00")
        BACKUP_TIME = "00:00"
except ValueError:
    log("[WARNING] Invalid BACKUP_TIME format. Using default: 00:00")
    BACKUP_TIME = "00:00"

def get_database_url():
    """Get the appropriate database URL based on configuration"""
    if USE_PUBLIC_URL:
        if not DATABASE_PUBLIC_URL:
            raise ValueError("[ERROR] DATABASE_PUBLIC_URL not set but USE_PUBLIC_URL=true!")
        return DATABASE_PUBLIC_URL
    
    if not DATABASE_URL:
        raise ValueError("[ERROR] DATABASE_URL not set!")
    return DATABASE_URL

def run_backup():
    """Main backup function that handles the entire backup process"""
    if shutil.which("pg_dump") is None:
        log("[ERROR] pg_dump not found. Install postgresql-client.")
        return

    database_url = get_database_url()
    url = urlparse(database_url)
    db_name = url.path[1:]

    log(f"[INFO] Using {'public' if USE_PUBLIC_URL else 'private'} database URL")

    format_map = {
        "sql": ("p", "sql"),
        "plain": ("p", "sql"),
        "dump": ("c", "dump"),
        "custom": ("c", "dump"),
        "tar": ("t", "tar")
    }
    pg_format, ext = format_map.get(DUMP_FORMAT.lower(), ("c", "dump"))

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_file = f"{FILENAME_PREFIX}_{timestamp}.{ext}"

    if BACKUP_PASSWORD:
        compressed_file = f"{backup_file}.7z"
    else:
        compressed_file = f"{backup_file}.gz"

    compressed_file_r2 = f"{BACKUP_PREFIX}{compressed_file}"

    ##Create backup
    try:
        log(f"[INFO] Creating backup {backup_file}")
        subprocess.run(
            ["pg_dump", f"--dbname={database_url}", "-F", pg_format, "-f", backup_file],
            check=True
        )

        if BACKUP_PASSWORD:
            log("[INFO] Encrypting backup with 7z...")
            with py7zr.SevenZipFile(compressed_file, 'w', password=BACKUP_PASSWORD) as archive:
                archive.write(backup_file)
            log("[SUCCESS] Backup encrypted successfully")
        else:
            log("[INFO] Compressing backup with gzip...")
            subprocess.run(["gzip", "-f", backup_file], check=True)
            log("[SUCCESS] Backup compressed successfully")

    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Backup creation failed: {e}")
        return
    except Exception as e:
        log(f"[ERROR] Compression/encryption failed: {e}")
        return
    finally:
        if os.path.exists(backup_file):
            os.remove(backup_file)

    ## Upload to R2
    if os.path.exists(compressed_file):
        size = os.path.getsize(compressed_file)
        log(f"[INFO] Final backup size: {size/1024/1024:.2f} MB")
        
    try:
        client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY
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

        objects = client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=BACKUP_PREFIX)
        if 'Contents' in objects:
            backups = sorted(objects['Contents'], key=lambda x: x['LastModified'], reverse=True)
            for obj in backups[MAX_BACKUPS:]:
                client.delete_object(Bucket=R2_BUCKET_NAME, Key=obj['Key'])
                log(f"[INFO] Deleted old backup: {obj['Key']}")

    except Exception as e:
        log(f"[ERROR] R2 operation failed: {e}")
        return
    finally:
        if os.path.exists(compressed_file):
            os.remove(compressed_file)

if __name__ == "__main__":
    log("[INFO] Starting backup scheduler...")
    log(f"[INFO] Scheduled backup time: {BACKUP_TIME} UTC")
    
    schedule.every().day.at(BACKUP_TIME).do(run_backup)
    
    run_backup()
    
    while True:
        schedule.run_pending()
        time.sleep(60)