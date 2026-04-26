# pg-s3-multi-backup

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy?template=https://github.com/midego1/pg-s3-multi-backup)

Automated PostgreSQL backup tool that creates scheduled `pg_dump` backups and
uploads them to **one or more S3-compatible destinations** — Cloudflare R2,
Railway storage buckets, Backblaze B2, AWS S3, MinIO, or any other S3-API
target. Use a single destination for simple deployments, or enable the
optional mirror to maintain a redundant copy on a second provider.

> Forked from [BigDaddyAman/pg-r2-backup](https://github.com/BigDaddyAman/pg-r2-backup), with EU-jurisdiction support, multi-destination uploads, and Railway-cron-friendly run modes.

## What's new in v2

- **Multi-destination uploads.** Optionally mirror every successful upload to
  a second S3-compatible bucket. Single dump, two destinations, independent
  retention.
- **Backwards-compatible.** With the new `MIRROR_*` env vars unset, behaviour
  is byte-identical to v1 — existing single-destination deploys keep working
  unchanged.
- **`RUN_ONCE` mode.** For Railway cron-job deploys: run a single backup,
  exit with `0` on success or `1` on failure. The non-zero exit is what
  triggers Railway's deploy-failed alerts.
- **Per-destination logging.** Lines prefixed `[dump] [r2] [mirror] [done]`
  so failed runs are instantly diagnosable.
- **Renamed.** Was `pg-r2-backup`; now `pg-s3-multi-backup` to reflect
  S3-compatible-anything support. Old GitHub URL still redirects.

## Modes of operation

This tool runs in three combinations — pick the one that fits your deploy:

| Mode | Setup | Best for |
|---|---|---|
| **Single destination, daemon** | `MIRROR_*` unset, `RUN_ONCE` unset | Always-on container with internal scheduler. Original v1 behaviour. |
| **Single destination, cron** | `MIRROR_*` unset, `RUN_ONCE=true` | Railway/Kubernetes cron job. Exit code drives alerting. |
| **Multi-destination, cron** | `MIRROR_*` set, `RUN_ONCE=true` | Production posture: redundant backup, exit-code alerting. |

## Environment variables

### Database

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (Railway provides this automatically). |
| `DATABASE_PUBLIC_URL` | No | Optional public connection string. |
| `USE_PUBLIC_URL` | No | `true`/`false` — use the public URL instead of the private one. Default `false`. |

### Primary destination (R2 or any S3-compatible)

| Variable | Required | Description |
|---|---|---|
| `R2_ENDPOINT` | Yes (R2/Railway/B2/MinIO); No (AWS-native S3) | S3 API endpoint — base URL only, no bucket path. (e.g. `https://ACCOUNT_ID.eu.r2.cloudflarestorage.com`). Optional only for AWS-native S3 with regional default. |
| `R2_BUCKET_NAME` | Yes | Bucket name. |
| `R2_ACCESS_KEY` | Yes | Access key id. |
| `R2_SECRET_KEY` | Yes | Secret access key. |
| `S3_REGION` | No | Region. Default `us-east-1`. Use `WEUR` for R2 EU jurisdiction or `auto` for default. |
| `MAX_BACKUPS` | No | Number of backups to retain on the primary destination. Default `7`. |

### Optional mirror destination (multi-destination mode)

The 3 identity fields (BUCKET_NAME + ACCESS_KEY + SECRET_KEY) must be set
together to enable the mirror. ENDPOINT is required for R2/Railway/B2/MinIO
(no regional default) and optional only for AWS-native S3. Leave all four
unset to keep single-destination mode (backwards-compatible).

| Variable | Required (if mirror enabled) | Description |
|---|---|---|
| `MIRROR_ENDPOINT` | Yes for non-AWS targets | Mirror S3 API endpoint. Empty = AWS regional default. |
| `MIRROR_BUCKET_NAME` | Yes | Mirror bucket name. |
| `MIRROR_ACCESS_KEY` | Yes | Mirror access key. |
| `MIRROR_SECRET_KEY` | Yes | Mirror secret key. |
| `MIRROR_REGION` | No | Mirror region. Defaults to `S3_REGION`. |
| `MIRROR_MAX_BACKUPS` | No | Mirror retention count. Defaults to `MAX_BACKUPS`. |

### Run mode + backup behaviour

| Variable | Required | Description |
|---|---|---|
| `RUN_ONCE` | No | `true` → run a single backup, exit with `0`/`1` (cron-style). Default `false` (daemon mode). |
| `BACKUP_TIME` | No | Daily backup time in UTC, daemon mode only. Default `00:00`. |
| `DUMP_FORMAT` | No | `custom`, `plain`, `directory`, `tar`. Default `custom`. |
| `FILENAME_PREFIX` | No | Backup filename prefix. Default `backup`. |
| `BACKUP_PREFIX` | No | Bucket key prefix (for foldering). Default empty. |
| `BACKUP_PASSWORD` | No | If set, encrypts dumps with 7z. Otherwise gzip. |
| `KEEP_LOCAL_BACKUP` | No | Keep local backup file after upload. Default `false`. |

## Cloudflare R2 EU jurisdiction

If your R2 bucket uses EU jurisdiction, set:

```
R2_ENDPOINT=https://YOUR_ACCOUNT_ID.eu.r2.cloudflarestorage.com
S3_REGION=WEUR
```

The `.eu.` subdomain is required for EU buckets and this fork patches
botocore to handle it correctly.

## Deploy on Railway (recommended setup: cron + mirror)

1. Click the Deploy button at the top, OR use the [Railway template](https://railway.com/deploy?template=https://github.com/midego1/pg-s3-multi-backup).
2. Set required env vars: `DATABASE_URL` (from Railway Postgres reference), `R2_*`, `S3_REGION`.
3. **Optional but recommended for production**: enable the mirror by adding
   `MIRROR_*` env vars pointing to a Railway storage bucket (or any second
   S3-compatible destination). Use Railway reference variables to wire the
   bucket's `BUCKET_S3_*` env vars into `MIRROR_*`.
4. Set `RUN_ONCE=true`.
5. In Railway service settings, configure a **cron schedule** (e.g.
   `30 3 * * *` for 03:30 UTC daily). Railway will spin up the container at
   schedule, the script runs once, exits, container shuts down.
6. **Configure failure alerts**: Service settings → Notifications → enable
   email/webhook on "deploy failed". Because `RUN_ONCE=true` exits non-zero
   on any backup failure, this triggers an alert whenever a backup run fails.

## Deploy on Railway (legacy setup: daemon + single destination)

If you want the original v1 behaviour (always-on container, internal
scheduler, single destination):

1. Deploy from template, set `R2_*` env vars.
2. Leave `MIRROR_*` and `RUN_ONCE` unset.
3. Set `BACKUP_TIME` to whatever daily UTC time you want.

The container stays up, runs once on startup, then runs daily at
`BACKUP_TIME`.

## Failure semantics

- **Exit code** (cron mode only): `0` only if dump AND all configured
  destinations succeeded. Non-zero otherwise.
- **Failure isolation**: a primary upload failure does NOT skip mirror
  upload. Independent insurance.
- **Per-destination logging**: every line prefixed with the destination so
  partial failures are obvious.
- **Retention prune failures**: logged but non-fatal — retention is
  best-effort cleanup, not the primary purpose.

## License

See [MIT License](MIT%20License.md).
