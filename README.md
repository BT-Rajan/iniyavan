# Eng Tutor
Multi-user engineering study app. FastAPI + MySQL + React (mobile-first, dark). DeepSeek explains topics and writes sample answers; results are cached centrally so each topic costs tokens once.

## Run
1. `CREATE DATABASE engtutor CHARACTER SET utf8mb4;`
2. `cp .env.example .env` and edit it (the first admin is created from it).
3. Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`
4. Frontend: `cd frontend && npm install && npm run build` (the backend then serves it at :8000). For dev use `npm run dev`.
5. Sign in as admin, add the DeepSeek key under Admin, then add students.
