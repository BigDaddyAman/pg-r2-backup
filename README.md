# PostgreSQL Backup to Cloudflare R2 (with EU Jurisdiction Support)

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy?template=https://github.com/midego1/pg-r2-backup)

Automated PostgreSQL backup service that creates scheduled database dumps and uploads them to Cloudflare R2 (S3-compatible storage). Supports **all R2 jurisdictions** including EU (`*.eu.r2.cloudflarestorage.com`).

Forked from [BigDaddyAman/pg-r2-backup](https://github.com/BigDaddyAman/pg-r2-backup) with a fix for Cloudflare R2 EU jurisdiction endpoint compatibility.

## What's Different from the Original?

- **EU jurisdiction support** — Bypasses botocore's endpoint URL validation that rejects `.eu.` subdomains in Cloudflare R2 EU jurisdiction endpoints
- **PostgreSQL 18 client** — Supports the latest PostgreSQL version
- **Works with all R2 jurisdictions** — EU, FedRAMP, or default

## Features

- Automated daily PostgreSQL backups via `pg_dump`
- Upload to Cloudflare R2 (or any S3-compatible storage)
- Optional gzip compression or 7z encryption
- Configurable retention policies (auto-delete old backups)
- Runs on Railway, Docker, or standalone

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (Railway provides this automatically) |
| `R2_ACCESS_KEY` | Yes | Cloudflare R2 API access key |
| `R2_SECRET_KEY` | Yes | Cloudflare R2 API secret key |
| `R2_BUCKET_NAME` | Yes | R2 bucket name (e.g., `my-db-backups`) |
| `R2_ENDPOINT` | Yes | R2 S3 API endpoint — **base URL only, no bucket path** (e.g., `https://ACCOUNT_ID.eu.r2.cloudflarestorage.com`) |
| `S3_REGION` | No | Region for R2 (default: `us-east-1`, use `WEUR` for EU buckets or `auto`) |
| `BACKUP_TIME` | No | Daily backup time in UTC (default: `00:00`, e.g., `03:30`) |
| `MAX_BACKUPS` | No | Number of backups to retain (default: `7`) |
| `DUMP_FORMAT` | No | pg_dump format: `custom`, `plain`, `directory`, `tar` (default: auto) |
| `KEEP_LOCAL_BACKUP` | No | Keep local backup file after upload: `true`/`false` (default: `false`) |

## Cloudflare R2 EU Jurisdiction

If your R2 bucket uses EU jurisdiction, set:

```
R2_ENDPOINT=https://YOUR_ACCOUNT_ID.eu.r2.cloudflarestorage.com
S3_REGION=WEUR
```

The `.eu.` subdomain is required for EU jurisdiction buckets and this fork handles it correctly.

## Deploy on Railway

Click the button above or use the [Railway template](https://railway.com/deploy?template=https://github.com/midego1/pg-r2-backup).

## License

See [MIT License](MIT%20License.md).
