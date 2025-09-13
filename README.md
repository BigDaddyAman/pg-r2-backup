# PostgreSQL Backup Bot for Railway

A lightweight automation bot that creates scheduled PostgreSQL backups and securely uploads them to **Cloudflare R2 object storage**.  
Designed for **Railway deployments**, with built-in support for Docker and cron scheduling.

---

## ✨ Features

- 📦 **Automated Backups** — scheduled daily or hourly backups of your PostgreSQL database  
- 🔐 **Optional Encryption** — compress with gzip or encrypt with 7z and password-protection  
- ☁️ **Cloudflare R2 Integration** — seamless upload to your R2 bucket  
- 🧹 **Retention Policy** — keep a fixed number of backups, auto-clean old ones  
- 🔗 **Flexible Database URL** — supports both private and public PostgreSQL URLs  
- 🐳 **Docker Ready** — lightweight container for portable deployment  

---

## 🚀 Deployment on Railway

1. **Fork this repository**  
2. **Create a new project** on [Railway](https://railway.app/)  
3. **Add environment variables** in Railway dashboard:

```env
DATABASE_URL=           # Your PostgreSQL database URL (private)
DATABASE_PUBLIC_URL=    # Public database URL (optional)
USE_PUBLIC_URL=false    # Set to true to use DATABASE_PUBLIC_URL
DUMP_FORMAT=dump        # Options: sql, plain, dump, custom, tar
FILENAME_PREFIX=backup  # Prefix for backup files
MAX_BACKUPS=7           # Number of backups to keep
R2_ACCESS_KEY=          # Cloudflare R2 access key
R2_SECRET_KEY=          # Cloudflare R2 secret key
R2_BUCKET_NAME=         # R2 bucket name
R2_ENDPOINT=            # R2 endpoint URL
BACKUP_PASSWORD=        # Optional: password for 7z encryption
BACKUP_TIME=00:00       # Daily backup time in UTC (HH:MM format)
```

---

## ⏰ Railway Cron Jobs

You can configure the backup schedule using Railway's built-in cron jobs in the dashboard:

1. Go to your project settings
2. Navigate to **Deployments** > **Cron**
3. Add a new cron job pointing to your service

Common cron expressions:

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Hourly | `0 * * * *` | Run once every hour |
| Daily (midnight) | `0 0 * * *` | Run once per day at midnight |
| Twice Daily | `0 */12 * * *` | Run every 12 hours |
| Weekly | `0 0 * * 0` | Run once per week (Sunday) |
| Monthly | `0 0 1 * *` | Run once per month |

Pro Tips:
- Use [crontab.guru](https://crontab.guru) to verify your cron expressions
- All times are in UTC
- Configure backup retention (`MAX_BACKUPS`) according to your schedule
````

📜 License

This project is open source under the MIT License.
You are free to use, modify, and distribute it with attribution.