![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Storage](https://img.shields.io/badge/storage-S3--compatible-orange)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)
![Deploy](https://img.shields.io/badge/deploy-Railway-purple)
![Docker](https://img.shields.io/badge/docker-supported-blue)

# Postgres-to-R2 Backup (S3-Compatible)

A lightweight PostgreSQL backup automation tool that creates scheduled backups and securely uploads them to **S3-compatible object storage**
such as **Cloudflare R2, AWS S3, Wasabi, Backblaze B2, or MinIO**.

It is designed to run reliably on **PaaS platforms**, with first-class support for Docker and cron scheduling, while remaining fully portable via a CLI or container.

---

## ✨ Features

- 📦 **Automated Backups** — scheduled daily or hourly PostgreSQL backups  
- 🔐 **Optional Encryption** — gzip compression or 7z encryption with password  
- ☁️ **Cloudflare R2 Integration** — seamless S3-compatible storage support
- 🧹 **Retention Policy** — automatically delete old backups  
- 🔗 **Flexible Database URLs** — supports private and public PostgreSQL connection URLs
- ⚡ **Optimized Performance** — parallel pg_dump and multipart S3 uploads
- 🐳 **Docker Ready** — portable, lightweight container  
- 🚀 **Deployment Templates** — no fork required for normal usage
- 🪣 **S3-Compatible Storage** — works with R2, AWS S3, Wasabi, B2, MinIO
- 💾 **Optional Local Retention** — keep backups locally for CLI, VPS, or NAS usage

---

## 🚀 Deployment on Railway 

1. Click the **Deploy on Railway** button below  
2. Railway will create a new project using the latest version of this repository  
3. Add the required environment variables in the Railway dashboard  
4. (Optional) Configure a cron job for your desired backup schedule

> Railway uses ephemeral storage. Local backup files are deleted by default after upload.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/postgres-to-r2-backup?referralCode=nIQTyp&utm_medium=integration&utm_source=template&utm_campaign=generic)

---

## 🔧 Environment Variables (S3-Compatible)

```env
# Database
DATABASE_URL=           # Private PostgreSQL URL
DATABASE_PUBLIC_URL=    # Public PostgreSQL URL (optional)
USE_PUBLIC_URL=false    # true = public, false = private

# Backup
RUN_MODE=railway        # railway | cli | daemon
DUMP_FORMAT=dump        # sql | plain | dump | custom | tar
FILENAME_PREFIX=backup
BACKUP_PREFIX=postgres-backups/
MAX_BACKUPS=7
KEEP_LOCAL_BACKUP=false

# S3-compatible storage
R2_ENDPOINT=
R2_BUCKET_NAME=
R2_ACCESS_KEY=
R2_SECRET_KEY=
S3_REGION=us-east-1

# Compression
BACKUP_PASSWORD=        # Optional: enables encrypted 7z

# Daemon scheduling (UTC)
BACKUP_TIME=00:00
```
`BACKUP_PREFIX` isolates backups in a folder within your bucket. `FILENAME_PREFIX` controls the generated backup filename.

Variable names use `R2_*` for historical reasons, but any S3-compatible provider can be used by changing the endpoint and credentials.

For AWS S3 users, ensure `S3_REGION` matches your bucket's region.

---

## ☁️ Supported S3-Compatible Providers

This project uses the **standard AWS S3 API via boto3**, and works with:

- Cloudflare R2 (recommended)
- AWS S3
- Wasabi
- Backblaze B2 (S3 API)
- MinIO (self-hosted)

### Example Endpoints

| Provider | Endpoint Example |
|--------|------------------|
| Cloudflare R2 | `https://<accountid>.r2.cloudflarestorage.com` |
| AWS S3 | `https://s3.amazonaws.com` |
| Wasabi | `https://s3.wasabisys.com` |
| Backblaze B2 | `https://s3.us-west-004.backblazeb2.com` |
| MinIO | `http://localhost:9000` |

---

## ⏰ Railway Cron Jobs

You can configure the backup schedule using **Railway Cron Jobs**:

1. Open your Railway project  
2. Go to **Deployments → Cron**  
3. Add a cron job targeting this service  

### Common Cron Expressions

| Schedule | Cron Expression | Description |
|--------|----------------|------------|
| Hourly | `0 * * * *` | Every hour |
| Daily | `0 0 * * *` | Once per day (UTC midnight) |
| Twice Daily | `0 */12 * * *` | Every 12 hours |
| Weekly | `0 0 * * 0` | Every Sunday |
| Monthly | `0 0 1 * *` | First day of the month |

**Tips**
- All cron times are **UTC**
- Use https://crontab.guru to validate expressions
- Adjust `MAX_BACKUPS` to match your schedule

> If you use Railway Cron Jobs, the service will start once per execution.
> In this setup, the service is expected to run a single backup and exit. Any internal scheduler should not be relied on.
> Ensure the backup process exits cleanly after completion; otherwise, Railway will skip subsequent cron executions.

---

### Railway Cron Mode
For Railway Cron Jobs, configure:

```
RUN_MODE=railway
```
Railway controls when the service starts.

Each execution:

- Runs one backup.
- Uploads the backup to S3-compatible storage.
- Applies the retention policy.
- Exits after completion.
Do not use `RUN_MODE=daemon` with Railway Cron. Daemon mode is intended for a continuously running service.

---

## 🖥️ Running Locally or on Other Platforms

It can run on **any platform** that supports:
- Python 3.9+
- `pg_dump` (PostgreSQL client tools)
- Environment variables
- Long-running background processes or cron

> Docker images use **Python 3.12** by default.  
> Local execution supports **Python 3.9+**.

### Supported Environments

- Local machine (Linux / macOS / Windows*)
- VPS (Netcup, Hetzner, DigitalOcean, etc.)
- Docker containers
- Other PaaS providers (Heroku, Fly.io, Render, etc.)

> *Windows is supported when `pg_dump` is installed and available in PATH.*

### Supported Run Modes
pg-r2-backup supports three operating modes:

| Mode | Description |
|------|-------------|
| `railway` | Runs one backup and exits. Designed for Railway Cron. |
| `cli` | Runs one backup and exits. Designed for manual execution. |
| `daemon` | Runs daily according to `BACKUP_TIME` (UTC). |

#### Railway Mode

```
RUN_MODE=railway
```
Use Railway Cron to trigger backups.

#### CLI Mode

```
RUN_MODE=cli
```
Run one backup manually:

```
python main.py
```

#### Daemon Mode

```
RUN_MODE=daemon
BACKUP_TIME=16:00
```
The application stays running and performs backups daily at the configured UTC time.

Example: `BACKUP_TIME=16:00` means midnight in Malaysia (UTC+8).

### Local Requirements

- Python 3.9+
- PostgreSQL client tools (`pg_dump` and `pg_restore`)
- pip

### Run Manually (Local)

```bash
pip install -r requirements.txt
python main.py
```

### Run with Docker (Optional)

Build and run the image locally:

```bash
docker build -t postgres-to-r2-backup .
docker run --env-file .env postgres-to-r2-backup
```

> Ensure the container is allowed to run continuously when not using an external cron scheduler.

> All scheduling uses **UTC** by default (e.g. Malaysia UTC+8 → set `BACKUP_TIME=16:00` for midnight).

## 🧰 Using the CLI (Global Installation)

This project can also be used as a standalone CLI tool, installable via pip, in addition to running as a Railway or Docker service.

### Install via pip

```bash
pip install pg-r2-backup
```

### Requirements

- Python 3.9+
- PostgreSQL client tools (`pg_dump` and `pg_restore`) installed and available in PATH

### Quick Start (CLI)

```bash
mkdir backups
cd backups

pg-r2-backup init      # creates .env from .env.example
pg-r2-backup doctor    # checks environment and dependencies
pg-r2-backup run       # runs a backup immediately
```

### CLI Commands

```bash
pg-r2-backup run            # Run backup immediately
pg-r2-backup doctor         # Check environment & dependencies
pg-r2-backup config show    # Show current configuration
pg-r2-backup init           # Create .env from .env.example
pg-r2-backup schedule       # Show scheduling examples
pg-r2-backup --version
```

### Environment Variable Resolution (CLI)
The application loads environment variables from `.env`.

When `override=true` is enabled, `.env` values take precedence over existing system environment variables.

The `.env` file is discovered from the current working directory or its parent directories.

This allows different folders to maintain separate backup configurations.

### Local Backup Behavior (CLI)

By default, pg-r2-backup deletes the local backup file after a successful upload.

To keep a local copy (recommended for local machines, VPS, or NAS):

    KEEP_LOCAL_BACKUP=true

> Not recommended on PaaS platforms (Railway, Fly.io, Render, Heroku, etc.)
> due to ephemeral filesystems.

### Scheduling Backups (CLI)

The CLI does not run a background scheduler. Use your operating system or platform scheduler instead.

**Linux / macOS (cron)**

```bash
0 0 * * * pg-r2-backup run
```

**Windows (Task Scheduler)**

- Program: `pg-r2-backup`
- Arguments: `run`
- Start in: folder containing `.env` (working directory)

**Railway / Docker**

Use the platform's built-in scheduler (recommended).

💡 **Tip**  
Run `pg-r2-backup schedule` at any time to see scheduling examples.

---

## 🛠 Development & Contributions

Fork this repository **only if you plan to**:

- Modify the backup logic
- Add features or integrations
- Submit pull requests
- Run locally for development

---

## For security best practices and deployment recommendations, see [SECURITY.md](SECURITY.md).

## ❓ FAQ

**Why only DATABASE_URL?**  
This matches how most modern platforms expose PostgreSQL credentials.  
Support for separate DB variables may be added if there is demand.

## 📜 License

This project is open source under the **MIT License**.

You are free to use, modify, and distribute it with attribution.
