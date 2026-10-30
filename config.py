
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

def get_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in ("true", "1", "yes", "on")


def get_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a valid integer")

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL")
USE_PUBLIC_URL = get_bool("USE_PUBLIC_URL", False)

R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

MAX_BACKUPS = get_int("MAX_BACKUPS", 7)
KEEP_LOCAL_BACKUP = get_bool("KEEP_LOCAL_BACKUP", False)

BACKUP_PREFIX = os.getenv(
    "BACKUP_PREFIX",
    "postgres-backups/"
)

FILENAME_PREFIX = os.getenv(
    "FILENAME_PREFIX",
    "backup"
)

DUMP_FORMAT = os.getenv(
    "DUMP_FORMAT",
    "dump"
).strip().lower()

BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

BACKUP_TIME = os.getenv("BACKUP_TIME", "00:00").strip()

RUN_MODE = os.getenv(
    "RUN_MODE",
    "daemon"
).strip().lower()

VALID_RUN_MODES = {"railway", "daemon", "cli"}

if RUN_MODE not in VALID_RUN_MODES:
    raise ValueError(
        f"Invalid RUN_MODE: {RUN_MODE}. "
        f"Choose from: {', '.join(sorted(VALID_RUN_MODES))}"
    )

if MAX_BACKUPS < 1:
    raise ValueError("MAX_BACKUPS must be at least 1")

if not BACKUP_PREFIX or not BACKUP_PREFIX.endswith("/"):
    raise ValueError(
        "BACKUP_PREFIX must be a non-empty prefix ending with '/'. "
        "Example: postgres-backups/"
    )

if (
    not FILENAME_PREFIX
    or "/" in FILENAME_PREFIX
    or "\\" in FILENAME_PREFIX
):
    raise ValueError("FILENAME_PREFIX must be a simple filename prefix")

if DUMP_FORMAT not in ("sql", "plain", "dump", "custom", "tar"):
    raise ValueError(
        "DUMP_FORMAT must be sql, plain, dump, custom, or tar"
    )

if RUN_MODE == "daemon":
    try:
        hour, minute = map(int, BACKUP_TIME.split(":"))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError

    except ValueError:
        raise ValueError(
            "BACKUP_TIME must use valid HH:MM format, e.g. 00:00"
        )

if USE_PUBLIC_URL:
    if not DATABASE_PUBLIC_URL:
        raise ValueError(
            "DATABASE_PUBLIC_URL is required when USE_PUBLIC_URL=true"
        )
else:
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is required")

if not R2_ACCESS_KEY:
    raise ValueError("R2_ACCESS_KEY is required")

if not R2_SECRET_KEY:
    raise ValueError("R2_SECRET_KEY is required")

if not R2_BUCKET_NAME:
    raise ValueError("R2_BUCKET_NAME is required")

if not R2_ENDPOINT:
    raise ValueError("R2_ENDPOINT is required")
