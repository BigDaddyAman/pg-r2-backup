# 🔐 Security Policy

## Database Exposure

This project does **not** require PostgreSQL to be exposed to the public internet.

- Never open PostgreSQL port `5432` directly without strict firewall rules.
- Prefer private networking whenever possible.

## Managed Databases

Managed PostgreSQL providers (e.g. Supabase, Neon, AWS RDS, Google Cloud SQL) use public hostnames but secure connections via TLS, authentication, and network controls.

These can be used without a tunnel when TLS, authentication, and appropriate network controls are properly configured.

## Self-hosted Databases

If you run PostgreSQL on your own server, avoid exposing its database port directly to the public internet.

For remote backup connections, use a secure connection method such as:

- **VPN:** WireGuard, Tailscale, or another private networking solution.
- **SSH tunneling:** Forward PostgreSQL connections through an authenticated SSH connection.
- **Cloudflare Tunnel:** Use Cloudflare Tunnel with Cloudflare Access for securely connecting to PostgreSQL over TCP.

If a public PostgreSQL endpoint is necessary, apply appropriate security controls:

- Enable TLS/SSL.
- Use strong database credentials.
- Restrict access using firewall rules or IP allowlisting.
- Keep PostgreSQL updated.

**Recommendation:** Prefer private networking or secure tunnelling over unrestricted public database access.

## Credentials & Secrets

- Store all secrets (database URLs, R2 access keys, encryption passwords) in environment variables.
- Never commit `.env` files or credentials to version control.

## Encrypted Backups (Optional)

Set `BACKUP_PASSWORD` to enable encrypted backups before uploading to S3-compatible storage.

Keep your `BACKUP_PASSWORD` safe and separate from your backup files. Losing the password may make encrypted backups impossible to recover.

## Least Privilege

- Use a dedicated PostgreSQL user with only the permissions required to perform backups.
- Restrict Cloudflare R2 credentials to the required bucket only.

## Backup Data Protection

Database backups may contain sensitive or confidential information.

- Keep backup buckets private.
- Avoid sharing backup download links publicly.
- Use encryption when backups contain sensitive data.
- Restrict access to backup storage.
- Regularly review backup retention and access permissions.

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly.

- Do **not** open a public GitHub issue with sensitive details.
- Use GitHub's **Security Advisories** feature to submit a private report.

Security reports will be reviewed and addressed as soon as possible.

> This document describes recommended security practices; exact requirements depend on your deployment environment.