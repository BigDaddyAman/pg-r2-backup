import argparse
import shutil
import os
import sys
import textwrap
import importlib.metadata

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

def get_version():
    try:
        return importlib.metadata.version("pg-r2-backup")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


def mask(value, show=4):
    if not value:
        return ""
    if len(value) <= show:
        return "*" * len(value)
    return value[:show] + "*" * (len(value) - show)

def doctor():
    print("pg-r2-backup doctor\n")

    failed = False

    for tool in ("pg_dump", "pg_restore"):
        if shutil.which(tool):
            print(f"[OK] {tool} found")
        else:
            print(f"[FAIL] {tool} not found in PATH")
            failed = True

    use_public = os.environ.get("USE_PUBLIC_URL", "false").lower() == "true"
    database_var = "DATABASE_PUBLIC_URL" if use_public else "DATABASE_URL"

    required_envs = [
        database_var,
        "R2_ACCESS_KEY",
        "R2_SECRET_KEY",
        "R2_BUCKET_NAME",
        "R2_ENDPOINT",
    ]

    missing = [name for name in required_envs if not os.environ.get(name)]

    if missing:
        print("\n[FAIL] Missing environment variables:")
        for name in missing:
            print(f"  - {name}")
        failed = True
    else:
        print("\n[OK] Required environment variables set")

    print(f"\nDatabase URL mode : {'public' if use_public else 'private'}")
    print(f"Database variable : {database_var}")

    if os.environ.get("BACKUP_PASSWORD"):
        if shutil.which("7z"):
            print("Compression       : 7z (encrypted)")
            print("[OK] 7z found")
        else:
            print("Compression       : 7z (encrypted)")
            print("[FAIL] 7z not found in PATH")
            failed = True
    else:
        print("Compression       : gzip")

    if os.environ.get("KEEP_LOCAL_BACKUP", "false").lower() == "true":
        print("Local backups     : kept after upload")
    else:
        print("Local backups     : deleted after upload")

    print("\n" + ("Doctor check failed." if failed else "Doctor check complete."))
    return 1 if failed else 0


def config_show():
    print("pg-r2-backup config\n")

    config = {
        "RUN_MODE": os.environ.get("RUN_MODE", "railway"),
        "USE_PUBLIC_URL": os.environ.get("USE_PUBLIC_URL", "false"),
        "DUMP_FORMAT": os.environ.get("DUMP_FORMAT", "dump"),
        "FILENAME_PREFIX": os.environ.get("FILENAME_PREFIX", "backup"),
        "BACKUP_PREFIX": os.environ.get("BACKUP_PREFIX", "postgres-backups/"),
        "MAX_BACKUPS": os.environ.get("MAX_BACKUPS", "7"),
        "KEEP_LOCAL_BACKUP": os.environ.get("KEEP_LOCAL_BACKUP", "false"),
        "BACKUP_TIME": os.environ.get("BACKUP_TIME", "00:00"),
        "R2_BUCKET_NAME": os.environ.get("R2_BUCKET_NAME", ""),
        "R2_ENDPOINT": os.environ.get("R2_ENDPOINT", ""),
        "R2_ACCESS_KEY": "********" if os.environ.get("R2_ACCESS_KEY") else "",
        "R2_SECRET_KEY": "********" if os.environ.get("R2_SECRET_KEY") else "",
        "BACKUP_PASSWORD": "********" if os.environ.get("BACKUP_PASSWORD") else "",
    }

    for key, value in config.items():
        print(f"{key:<18} : {value}")

def init_env():
    if os.path.exists(".env"):
        print("[ERROR] .env already exists")
        return

    example = ".env.example"
    if not os.path.exists(example):
        print("[ERROR] .env.example not found")
        return

    shutil.copy(example, ".env")
    print("[SUCCESS] .env created from .env.example")
    print("Edit the file before running backups.")


def schedule_info():
    print(textwrap.dedent("""
    pg-r2-backup scheduling

    Linux / macOS (cron):
      0 0 * * * pg-r2-backup run

    Windows (Task Scheduler):
      Program : pg-r2-backup
      Args    : run
      Start in: folder containing .env (working directory)

    Railway / Docker:
      Use the platform scheduler
    """).strip())

def main():
    parser = argparse.ArgumentParser(
        prog="pg-r2-backup",
        description="PostgreSQL backup tool for S3-compatible storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              pg-r2-backup doctor
              pg-r2-backup run
              pg-r2-backup config show
              pg-r2-backup init
              pg-r2-backup schedule
        """)
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}"
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run backup immediately")
    subparsers.add_parser("doctor", help="Check environment & dependencies")
    subparsers.add_parser("schedule", help="Show scheduling examples")

    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_sub = config_parser.add_subparsers(dest="subcommand")
    config_sub.add_parser("show", help="Show current configuration")

    subparsers.add_parser("init", help="Create .env from .env.example")

    args = parser.parse_args()

    if args.command == "run":
        from main import run_backup
        run_backup()

    elif args.command == "doctor":
        sys.exit(doctor())

    elif args.command == "config" and args.subcommand == "show":
        config_show()

    elif args.command == "init":
        init_env()

    elif args.command == "schedule":
        schedule_info()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
