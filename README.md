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
Structure: Program > Semester > Course > Unit > Topic. Only admins create, edit and delete; students read and learn.
Upgrades are automatic: earlier "courses" become programs, their "subjects" become courses inside a "Semester 1", and loose topics go into a "General" unit. (Table names are unchanged: `courses` = programs, `subjects` = courses.)

## Programs
Admin > Programs works like Users: a table of programs with course and student counts, search (program, semester or course name), sorting, and New program. Tap a row for the program's page: semesters, enrolled students, Rename, Delete (with a warning of what goes with it) and Add content. Program names must be unique, because the users CSV import matches programs by name. Deleting a program un-enrols its students but keeps their accounts.

## CSV import (content)
Admin > Programs > Bulk upload. Columns: `program, semester, course, unit, topic` plus optional `content, question_pattern, sample_content, guideline`. Blank hierarchy cells repeat the row above; existing names are reused and existing topics are updated. A preview shows what will change before anything is saved.

## Name and menu
The app name comes from `APP_NAME` in `.env` (login screen, top bar, drawer, installed app name). The drawer menu (top left) has Learn, and for admins Users, Programs, AI config, Reports and About.

## Bookmarks
Anyone signed in can bookmark a topic with the bookmark icon at the top of the topic page (tap again to remove it). Bookmarks are private to each user. The Bookmarks page in the drawer arranges them by semester, course and unit: pick a semester button, then a course tab to see its units, then tap a unit and every unit of that course becomes a tab, each showing its bookmarked topics. Bookmarked topics also carry a small bookmark mark in the Learn lists. The `bookmarks` table is created automatically on start.

## Users
Admin > Users is a table of name, program and semester (1 to 8). Search matches name, email, role, program or semester ("3", "sem 3"), and you can filter by program or semester and change the sort order. Tap a row to open the user's page: profile, reading activity, Edit, and Reset password (creates a new random password, shown once with a Copy button). New and edited users can be enrolled in a program and semester. You can't change your own role or status.
Bulk upload takes a CSV with `name,email,password,role,program,semester`. Blank passwords are generated and offered as a one-time download. Program must match a name on the Programs tab; semester is 1 to 8 (`3`, `S3` and `Semester 3` all work). Existing emails are updated, and blank program or semester cells leave the current value alone.
Older databases upgrade automatically: two nullable columns (`users.program_id`, `users.semester`) are added on start.

## Seed content
`content/engg_chem_unit1_water_treatment.csv`: B.E Mech > Semester 1 > Engg. Chem > Unit 1 - Water Treatment (31 topics). Load it from Admin > Programs > Bulk upload (check the preview, then confirm). Enrol students in program "B.E Mech", semester 1 to match.

## Passwords
Everyone can change their own password from the drawer (Change password). Passwords an admin sets or generates (new user, bulk upload, Reset, CLI add/passwd) are temporary: the student must choose their own on first sign-in, and the app blocks everything else until they do. Admins changing their own password are not forced. The `users.must_change` column is added automatically on start; existing users are not forced.

## Common courses
A course lives in one home semester, but can also be shown in other programs' semesters (for example first-year Engg. Chem for every branch). As admin, open a semester and tap the link icon on a course, then tick the semesters that should also show it. You edit it only at its home; the other semesters show it marked "shared from ...". Removing a shared card (trash icon) only unlinks it there. Students see a shared course like any other and are scoped by their own program and semester. Deleting the home course or a linked semester cleans up the links.

## Faculty role
Roles are student, faculty and admin. Faculty can read everything and add, edit and delete **units and topics** in the courses an admin has assigned to them (Users > open the person > Assign courses). They cannot create or delete programs, semesters or courses, share courses, manage users, upload CSVs, or change settings, and the server enforces that. Create faculty from Users (role Faculty), the bulk user CSV (`role` column) or `manage.py add --role faculty`. Like students, faculty must set their own password on first sign-in. A new `course_faculty` table is created automatically.

## Equations and images in content
Topic content is Markdown with math: `$x^2$` inline, or a block with `$$` on its own line above and below. Chemistry uses mhchem, for example `$\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$` (`v` is a precipitate arrow, `^` a gas arrow). In the editor, **Add image** uploads a PNG, JPG, GIF or WebP (max 3 MB) and inserts it at the cursor; **Preview** shows the result. Admins and faculty can upload. Files are saved in `backend/uploads` (set `UPLOAD_DIR` to move it) and must be backed up with the database. Images are served without sign-in (random names) because `<img>` tags can't send a login token. If a reverse proxy sits in front, allow request bodies of at least 3 MB (nginx `client_max_body_size 4m`). A literal dollar sign in content may need escaping as `\$` when a second one follows in the same paragraph.

## Draft and publish
Topics have a Published flag. Drafts are visible to admins and faculty only: students don't see them in the course list, and opening, reading, bookmarking or asking the AI about a draft returns "not found". In the editor, tick "Published" (it starts unticked for faculty and ticked for admins). In a unit, the eye icon on a topic publishes or unpublishes it, and "Publish all N drafts" publishes the whole unit. Faculty can publish topics in their own courses. Topics created by CSV import are published. Existing topics stay published when the `topics.published` column is added on start.

## Security settings
- **JWT_SECRET** is required (32+ random characters). The app refuses to start without it, and `run.sh` generates one if it is missing or still the placeholder.
- **Sign-in lockout:** 5 wrong passwords per account from one address, 20 per account, or 200 per address inside 15 minutes returns "try again in 15 minutes". The same limit guards the current-password check when changing a password.
- **Sessions** last `TOKEN_DAYS` (default 7) and end whenever the password changes, is reset by an admin, or the account is disabled. Changing your own password keeps you signed in on that device.
- **Password hashing** is PBKDF2 with 600,000 rounds (`PBKDF2_ITER`). Old hashes upgrade automatically at the next sign-in. One-time passwords made by bulk upload use fewer rounds and are replaced by the full-strength hash when the user sets their own.
- **CORS** is off (same-origin). Set `ALLOWED_ORIGINS` only if the front-end is served from another site. Responses carry CSP, nosniff, frame-deny and referrer headers, and HSTS over HTTPS.
- **GET /api/health** returns 200 when the database answers, 503 otherwise, for uptime monitors.

## Operations
- **Tests:** `cd backend && pip install -r requirements-dev.txt && python -m pytest`. They run on a throwaway SQLite database and cover scoping, faculty permissions, drafts, common courses, passwords, lockout, uploads, import, migrations, the audit log and backups. GitHub Actions runs them and builds the front-end on every push (`.github/workflows/ci.yml`).
- **Migrations:** schema changes are numbered entries in `MIGRATIONS` in `backend/main.py`. Each runs once, is recorded in the `schema_migrations` table, and is safe on a database that already has the change. Add new ones at the end. They apply on start; `./manage.sh migrate` applies them and lists what is applied.
- **Backups:** `./backup.sh` writes a compressed database dump (`mysqldump` for MariaDB/MySQL, the SQLite backup API for SQLite) and a tarball of `uploads/` into `./backups` (or `BACKUP_DIR` / `--dir`), and deletes copies older than `--keep-days` (default 14). Schedule it, for example `30 2 * * * /path/to/iniyavan/backup.sh >> /var/log/engtutor-backup.log 2>&1`, and copy the folder off the server. The MariaDB client tools (`mysqldump`) must be installed.
  Restore: `gunzip < engtutor-DATE-db.sql.gz | mysql -u USER -p DBNAME`, then `tar -xzf engtutor-DATE-uploads.tar.gz -C backend/` to bring the images back.
- **Activity log:** every create, edit, delete, publish, share, import, upload, password reset and password change by a signed-in user is recorded with who, when, what and whether it was allowed (blocked attempts show as "Not allowed"). Admins read it under Activity log, with search. Request contents and passwords are never stored, and entries older than 400 days are removed. Students opening or bookmarking topics are not logged here (that is the reading progress).
