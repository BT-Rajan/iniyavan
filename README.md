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
