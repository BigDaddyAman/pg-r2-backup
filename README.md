![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Storage](https://img.shields.io/badge/storage-S3--compatible-orange)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)
![Deploy](https://img.shields.io/badge/deploy-Railway-purple)
![Docker](https://img.shields.io/badge/docker-supported-blue)

# Postgres-to-R2 Backup (S3-Compatible)

A lightweight automation service that creates scheduled PostgreSQL backups and securely uploads them to **S3-compatible object storage**
such as **Cloudflare R2, AWS S3, Wasabi, Backblaze B2, or MinIO**.  
Designed specifically as a **Railway deployment template**, with built-in support for Docker and cron scheduling.

---

## ✨ Features

- 📦 **Automated Backups** — scheduled daily or hourly PostgreSQL backups  
- 🔐 **Optional Encryption** — gzip compression or 7z encryption with password  
- ☁️ **Cloudflare R2 Integration** — seamless S3-compatible storage support
- 🧹 **Retention Policy** — automatically delete old backups  
- 🔗 **Flexible Database URLs** — supports private and public PostgreSQL URLs  
- ⚡ **Optimized Performance** — parallel pg_dump and multipart S3 uploads
- 🐳 **Docker Ready** — portable, lightweight container  
- 🚀 **Railway Template First** — no fork required for normal usage  
<<<<<<< HEAD
=======
- 🪣 **S3-Compatible Storage** — works with R2, AWS S3, Wasabi, B2, MinIO
>>>>>>> 20e6dd1 (Update Docker, dependencies, S3 compatibility, and documentation)

---

## 🚀 Deployment on Railway 

1. Click the **Deploy on Railway** button below  
2. Railway will create a new project using the latest version of this repository  
3. Add the required environment variables in the Railway dashboard  
4. (Optional) Configure a cron job for your desired backup schedule  

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/postgres-to-r2-backup?referralCode=nIQTyp&utm_medium=integration&utm_source=template&utm_campaign=generic)

---

## 🔧 Environment Variables (S3-Compatible)

```env
DATABASE_URL=           # PostgreSQL database URL (private)
DATABASE_PUBLIC_URL=    # Public PostgreSQL URL (optional)
USE_PUBLIC_URL=false    # Set true to use DATABASE_PUBLIC_URL

DUMP_FORMAT=dump        # sql | plain | dump | custom | tar
FILENAME_PREFIX=backup  # Backup filename prefix
MAX_BACKUPS=7           # Number of backups to retain

R2_ENDPOINT=            # S3 endpoint URL
R2_BUCKET_NAME=         # Bucket name
R2_ACCESS_KEY=          # Access key
R2_SECRET_KEY=          # Secret key
S3_REGION=us-east-1     # Required for AWS S3 (ignored by R2/MinIO)

BACKUP_PASSWORD=        # Optional: enables 7z encryption
BACKUP_TIME=00:00       # Daily backup time (UTC, HH:MM)
```

> Variable names use `R2_*` for historical reasons, but **any S3-compatible provider** can be used by changing the endpoint and credentials.
> For AWS S3 users: ensure `S3_REGION` matches your bucket’s region.

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

---

## 🖥️ Running Locally or on Other Platforms

It can run on **any platform** that supports:
- Python 3.9+
- `pg_dump` (PostgreSQL client tools)
- Environment variables
- Long-running background processes or cron

<<<<<<< HEAD
=======
> Docker images use **Python 3.12** by default.  
> Local execution supports **Python 3.9+**.

>>>>>>> 20e6dd1 (Update Docker, dependencies, S3 compatibility, and documentation)
### Supported Environments

- Local machine (Linux / macOS / Windows*)
- VPS (Netcup, Hetzner, DigitalOcean, etc.)
- Docker containers
- Other PaaS providers (Heroku, Fly.io, Render, etc.)

> *Windows is supported when `pg_dump` is installed and available in PATH.*

### Local Requirements

- Python 3.9+
- PostgreSQL client tools (`pg_dump`)
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

### Run from Prebuilt Docker Image

If you downloaded a prebuilt Docker image archive (`.tar` or `.tar.gz`), you can run it without building locally:

```bash
# Extract the archive (if compressed)
tar -xzf postgres-to-r2-backup_v1.0.0.tar.gz

# Load the image into Docker
docker load -i postgres-to-r2-backup_v1.0.0.tar

# Run the container
docker run --env-file .env postgres-to-r2-backup:v1.0.0
```

> Prebuilt images are architecture-specific (amd64 / arm64).

---

## 🔐 Security

- **Do not expose PostgreSQL directly to the public internet.**  
  If your database is not on a private network, use a secure tunnel instead.

- **Recommended: Cloudflare Tunnel**  
  When using a public database URL, it is strongly recommended to connect via a secure tunnel such as **Cloudflare Tunnel** rather than opening database ports.

- **Protect credentials**  
  Store all secrets (database URLs, R2 keys, encryption passwords) using environment variables.  
  Never commit `.env` files to version control.

- **Encrypted backups (optional)**  
  Set `BACKUP_PASSWORD` to enable encrypted backups using 7z before uploading to S3-compatible storage.

- **Least privilege access**  
  Use a PostgreSQL user with read-only access where possible, and restrict R2 credentials to the required bucket only.

---

## 🛠 Development & Contributions

Fork this repository **only if you plan to**:

- Modify the backup logic
- Add features or integrations
- Submit pull requests
- Run locally for development

---

## 📜 License

This project is open source under the **MIT License**.

You are free to use, modify, and distribute it with attribution.
