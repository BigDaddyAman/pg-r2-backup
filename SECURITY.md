# 🔐 Security Policy

## Database Exposure

This project does **not** require PostgreSQL to be exposed to the public internet.

- Never open PostgreSQL port `5432` directly without strict firewall rules.
- Prefer private networking whenever possible.

## Managed Databases

Managed PostgreSQL providers (e.g. Supabase, Neon, AWS RDS, Google Cloud SQL)
use public hostnames but secure connections via TLS, authentication, and network controls.
These are safe to use without any tunnel.

## Self-hosted Databases

If you run PostgreSQL on your own server and cannot place it on a private network,
use a secure tunnel such as:
- Cloudflare Tunnel
- SSH tunneling
- VPN (WireGuard, Tailscale, etc.)

Do **not** expose database ports directly to the internet.

## Credentials & Secrets

- Store all secrets (database URLs, R2 access keys, encryption passwords)
  in environment variables.
- Never commit `.env` files or credentials to version control.

## Encrypted Backups (Optional)

Set `BACKUP_PASSWORD` to enable encrypted backups before uploading
to S3-compatible storage.

## Least Privilege

- Use a PostgreSQL user with read-only permissions where possible.
- Restrict Cloudflare R2 credentials to the required bucket only.

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly.
Do **not** open a public issue with sensitive details.

> This document describes recommended security practices; exact requirements depend on your deployment environment.

