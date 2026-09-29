# Eng Tutor
Multi-user engineering study app: FastAPI + MariaDB/MySQL + React PWA. DeepSeek explains topics and writes sample answers; results are cached centrally so each topic costs tokens once.

## Production first run
1. DB: `CREATE DATABASE engtutor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL ON engtutor.* TO 'app_user'@'localhost'; FLUSH PRIVILEGES;`
2. `python3 -m venv venv && . venv/bin/activate && pip install -r backend/requirements.txt` (Python 3.10+)
3. `cp .env.example .env` and fill it in.
4. `cd frontend && npm ci && npm run build && cd ..`
5. `python backend/run.py` (serves API and UI on HOST:PORT)
6. Sign in as the admin, add the DeepSeek key under Admin, then add students.

The PWA installs only over HTTPS (or localhost), so put the app behind a TLS reverse proxy.
