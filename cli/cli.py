import argparse
import shutil
import os
import sys
import textwrap
import importlib.metadata

from main import run_backup

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
    
    if shutil.which("pg_dump") is None:
        print("[FAIL] pg_dump not found in PATH")
    else:
        print("[OK] pg_dump found")

    required_envs = [
        "DATABASE_URL",
        "R2_ACCESS_KEY",
        "R2_SECRET_KEY",
        "R2_BUCKET_NAME",
        "R2_ENDPOINT",
    ]

    missing = [e for e in required_envs if not os.environ.get(e)]

    if missing:
        print("\n[FAIL] Missing environment variables:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("\n[OK] Required environment variables set")

    use_public = os.environ.get("USE_PUBLIC_URL", "false").lower() == "true"
    print(f"\nDatabase URL mode : {'public' if use_public else 'private'}")

    if os.environ.get("BACKUP_PASSWORD"):
        print("Compression      : 7z (encrypted)")
    else:
        print("Compression      : gzip")

    if os.environ.get("KEEP_LOCAL_BACKUP", "false").lower() == "true":
        print("Local backups    : kept after upload")
    else:
        print("Local backups    : deleted after upload")

    print("\nDoctor check complete.")


def config_show():
    print("pg-r2-backup config\n")

    config = {
        "USE_PUBLIC_URL": os.environ.get("USE_PUBLIC_URL", "false"),
        "DUMP_FORMAT": os.environ.get("DUMP_FORMAT", "dump"),
        "FILENAME_PREFIX": os.environ.get("FILENAME_PREFIX", "backup"),
        "MAX_BACKUPS": os.environ.get("MAX_BACKUPS", "7"),
        "KEEP_LOCAL_BACKUP": os.environ.get("KEEP_LOCAL_BACKUP", "false"),
        "BACKUP_TIME": os.environ.get("BACKUP_TIME", "00:00"),
        "R2_BUCKET_NAME": os.environ.get("R2_BUCKET_NAME", ""),
        "R2_ENDPOINT": os.environ.get("R2_ENDPOINT", ""),
        "R2_ACCESS_KEY": mask(os.environ.get("R2_ACCESS_KEY")),
        "R2_SECRET_KEY": mask(os.environ.get("R2_SECRET_KEY")),
    }

    for k, v in config.items():
        print(f"{k:<16} : {v}")


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
        description="PostgreSQL backup tool for Cloudflare R2",
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
        run_backup()

    elif args.command == "doctor":
        doctor()

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
