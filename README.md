# Eng Tutor
Multi-user engineering study app: FastAPI + MariaDB/MySQL + React PWA. DeepSeek explains topics and writes sample answers; results are cached centrally so each topic costs tokens once.

## Production first run
1. DB: `CREATE DATABASE engtutor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL ON engtutor.* TO 'app_user'@'localhost'; FLUSH PRIVILEGES;`
3. `cp .env.example .env` and fill it in.
5. `./run.sh` (installs deps, builds the UI, starts the app under pm2; serves API and UI on HOST:PORT)
6. Sign in as the admin, add the DeepSeek key under Admin, then add students.

The PWA installs only over HTTPS (or localhost), so put the app behind a TLS reverse proxy.

## Managing users from the terminal
`./manage.sh add --name "Name" --email a@b.com [--role admin]` (prompts for the password), `passwd`, `enable`, `disable`, `role`, `list`. Use `VENV=/path/to/venv` if your venv is not `./venv`.

## Admins and passwords
No account is created automatically. Create or reset the admin (creates it if missing, otherwise resets the password and makes sure it is an active admin):
`./manage.sh admin --email you@example.com`. Reset any user with `./manage.sh passwd --email x@y.com`, or from the Admin tab in the app (Reset).

## Content
Only admins can create, edit and delete courses, subjects, units and topics (Course › Subject › Unit › Topic). Students read and learn. Upgrading an older database is automatic: existing topics move into a "General" unit per subject.
