# Postgres-to-R2 Backup

A lightweight automation service that creates scheduled PostgreSQL backups and securely uploads them to **Cloudflare R2 object storage**.  
Designed specifically as a **Railway deployment template**, with built-in support for Docker and cron scheduling.

---

## ✨ Features

- 📦 **Automated Backups** — scheduled daily or hourly PostgreSQL backups  
- 🔐 **Optional Encryption** — gzip compression or 7z encryption with password  
- ☁️ **Cloudflare R2 Integration** — seamless S3-compatible uploads  
- 🧹 **Retention Policy** — automatically delete old backups  
- 🔗 **Flexible Database URLs** — supports private and public PostgreSQL URLs  
- ⚡ **Optimized Performance** — parallel pg_dump and multipart R2 uploads  
- 🐳 **Docker Ready** — portable, lightweight container  
- 🚀 **Railway Template First** — no fork required for normal usage  

---

## 🚀 Deployment on Railway (Recommended)

1. Click the **Deploy on Railway** button below  
2. Railway will create a new project using the latest version of this repository  
3. Add the required environment variables in the Railway dashboard  
4. (Optional) Configure a cron job for your desired backup schedule  

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/e-ywUS?referralCode=nIQTyp&utm_medium=integration&utm_source=template&utm_campaign=generic)

---

## 🔧 Environment Variables

```env
DATABASE_URL=           # PostgreSQL database URL (private)
DATABASE_PUBLIC_URL=    # Public PostgreSQL URL (optional)
USE_PUBLIC_URL=false    # Set true to use DATABASE_PUBLIC_URL

DUMP_FORMAT=dump        # sql | plain | dump | custom | tar
FILENAME_PREFIX=backup  # Backup filename prefix
MAX_BACKUPS=7           # Number of backups to retain

R2_ACCESS_KEY=          # Cloudflare R2 access key
R2_SECRET_KEY=          # Cloudflare R2 secret key
R2_BUCKET_NAME=         # R2 bucket name
R2_ENDPOINT=            # R2 endpoint URL

BACKUP_PASSWORD=        # Optional: enables 7z encryption
BACKUP_TIME=00:00       # Daily backup time (UTC, HH:MM)
```

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

```bash
docker build -t postgres-to-r2-backup .
docker run --env-file .env postgres-to-r2-backup
```

All scheduling uses **UTC by default** to ensure consistent behavior across platforms.

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
