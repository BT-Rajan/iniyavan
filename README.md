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
Structure: Program > Semester > Course > Unit > Topic. Admins build and change programs, semesters and courses; each course's faculty owner looks after its units and topics; students read and learn.
Upgrades are automatic: earlier "courses" become programs, their "subjects" become courses inside a "Semester 1", and loose topics go into a "General" unit. (Table names are unchanged: `courses` = programs, `subjects` = courses.)

## Programs
Admin > Programs works like Users: a table of programs with course and student counts, search (program, semester or course name), sorting, and New program. Tap a row for the program's page: its semesters in order, Add semester, enrolled students, Rename, Delete (with a warning of what goes with it) and Open semesters and courses. Program names must be unique, because the users CSV import matches programs by name. Deleting a program un-enrols its students but keeps their accounts.

## Building the structure (admins)
Everything is made from where it belongs. In Learn (or from a program's page): the programs list has **New program**; inside a program, **Add semester** asks for its number (1 to 8) and a name; inside a semester, **Add course** asks for a name and the faculty owner. A course page shows its program, semester and owner, with **Edit course** (rename, move to another semester, change owner) and **Change owner**. The pencil on a program, semester or course edits it in place; the trash icon deletes it after saying exactly what goes with it.

A semester's **number** is stored data, not read from its name: it decides the order semesters are listed in and which students see them (a student in semester 3 sees semesters 1 to 3). Each number is used once per program. On upgrade, migration 0010 fills the number from each existing semester's name when that is unambiguous; any it can't fill show "No semester number set" and are listed by `./manage.sh integrity`. Until numbered, such a semester is visible to every student of the program, as before.

Moving a course to another semester also moves it to that semester's program, with its units, topics, quizzes and owner.

## CSV import (content)
Admin > Programs > Bulk upload. Columns: `program, semester, course, unit, topic` plus optional `semester_no, content, question_pattern, sample_content, guideline`. A new semester takes `semester_no`, or else the number in its name if that number is free in the program; otherwise it is created without a number and the preview says so. Imported courses have no owner until an admin assigns one. Blank hierarchy cells repeat the row above; existing names are reused and existing topics are updated. A preview shows what will change before anything is saved.

## Name and menu
The app name comes from `APP_NAME` in `.env` (login screen, top bar, drawer, installed app name). The drawer menu (top left) has Learn, and for admins Users, Programs, AI config, Reports and About.

## Bookmarks
Anyone signed in can bookmark a topic with the bookmark icon at the top of the topic page (tap again to remove it). Bookmarks are private to each user. The Bookmarks page in the drawer arranges them by semester, course and unit: pick a semester button, then a course tab to see its units, then tap a unit and every unit of that course becomes a tab, each showing its bookmarked topics. Bookmarked topics also carry a small bookmark mark in the Learn lists. The `bookmarks` table is created automatically on start.

## Users
Admin > Users is a table of name, program and semester (1 to 8). Search matches name, email, role, program or semester ("3", "sem 3"), and you can filter by program or semester and change the sort order. Tap a row to open the user's page: profile, reading activity, Edit, and Reset password (creates a new random password, shown once with a Copy button). New and edited users can be enrolled in a program and semester. Students see their own program, up to and including their current semester; a student with no program sees no programs, courses or topics until you enrol them. You can't change your own role or status.
Bulk upload takes a CSV with `name,email,password,role,program,semester`. Blank passwords are generated and offered as a one-time download. Program must match a name on the Programs tab; semester is 1 to 8 (`3`, `S3` and `Semester 3` all work). Existing emails are updated, and blank program or semester cells leave the current value alone.
Older databases upgrade automatically: two nullable columns (`users.program_id`, `users.semester`) are added on start.

## Seed content
`content/engg_chem_unit1_water_treatment.csv`: B.E Mech > Semester 1 > Engg. Chem > Unit 1 - Water Treatment (31 topics). Load it from Admin > Programs > Bulk upload (check the preview, then confirm). Enrol students in program "B.E Mech", semester 1 to match.

## Passwords
Everyone can change their own password from the drawer (Change password). Passwords an admin sets or generates (new user, bulk upload, Reset, CLI add/passwd) are temporary: the student must choose their own on first sign-in, and the app blocks everything else until they do. Admins changing their own password are not forced. The `users.must_change` column is added automatically on start; existing users are not forced.

## Common courses
A course lives in one home semester, but can also be shown in other programs' semesters (for example first-year Engg. Chem for every branch). As admin, open a semester and tap the link icon on a course, then tick the semesters that should also show it. You edit it only at its home; the other semesters show it marked "shared from ...". Removing a shared card (trash icon) only unlinks it there. Students see a shared course like any other and are scoped by their own program and semester. Deleting the home course or a linked semester cleans up the links.

## Faculty role
Roles are student, faculty and admin. Faculty can read all published content and see drafts only in the courses they own. They cannot create, edit, move or delete programs, semesters or courses, share courses, manage users, upload CSVs, or change settings, and the server enforces that. Create faculty from Users (role Faculty), the bulk user CSV (`role` column) or `manage.py add --role faculty`. Like students, faculty must set their own password on first sign-in. On sign-in faculty see **My courses** first, above the full program list.

## Course workspace (faculty)
Faculty open **My courses** and then a course. The course page shows its program, semester and owner, and **Add unit**; inside a unit, **Add topic** opens the topic editor (Markdown, equations, images, Preview) already placed in that unit. Units and topics have up/down arrows; the order is saved and is the order students see. A topic page has **Edit topic** and **Publish/Unpublish** for its owner. Faculty can rename and delete their own units and topics and move a topic between units of the same course; moving a unit to another course, or a topic out of its course, is left to admins. Deleting a topic or unit also deletes its students' reading progress, bookmarks and saved AI answers (and a unit's quizzes and attempts); the confirmation says so. Migration 0011 adds `units.position` and `topics.position`, filled in the existing order.

## Learning deadlines and progress
A topic can have a **learning deadline**, set or removed by its course's owner or an admin in the topic editor ("Learning deadline", or "No deadline"). It is stored as one instant (UTC, like every time in the app) and shown in each reader's own time zone; the API takes ISO 8601 with a time zone (`2026-10-05T17:00:00+05:30` or `...Z`). Past deadlines are allowed and never moved. A deadline does not lock anything: after it passes, a student who hasn't completed the topic sees **Overdue** and can still read and complete it.

Each student's state per topic is **Not started** (never opened), **In progress** (opened) or **Completed** (they tapped **Mark as completed**; the time is kept, and "after the deadline" is shown when it was late). Opening a topic never completes it and never undoes a completion; only **Mark as not completed** does. Overdue and late are worked out from the deadline and the completion time, not stored. Unit and course counts ("3 / 5 topics completed") are counted from these states. In a unit, a course's owner sees per topic how many of the course's students completed it and how many are overdue. There is one progress row per student and topic (a unique key), so repeated or simultaneous clicks can't duplicate it. Migration 0012 adds `topics.learning_due_at` and `progress.completed_at`; existing topics get no deadline, and students who had opened a topic are In progress, not Completed.

## Course owners
Admins create courses; each course has **one owner**, an active faculty member, who adds, edits, deletes and publishes its units, topics and quizzes. No other faculty member can edit it (admins always can). A course may be left with "Owner not assigned" until an admin picks one; until then only admins edit it.

Set the owner in any of three places. They all change the same field (`subjects.faculty_owner_id`): the Owner box when adding or editing a course; Programs > open a program > pencil beside a course; or Users > open a faculty member > Assign courses (ticking a course someone else owns moves it to this person). Changing or removing an owner never touches units, topics, quizzes or student progress.

Owners are never replaced automatically. If an owner is disabled or stops being faculty, they stay on record but can't edit; the course shows "Owner ... is disabled" or "... is no longer faculty", and saving that change on their page says how many courses need a new owner.

Upgrading: migration 0009 makes the single assigned faculty member of each course its owner. It does not choose when a course had several assigned faculty, none, or one who is no longer active faculty. `./manage.sh owners` lists those courses with the people who used to be assigned. The old `course_faculty` rows are kept but no longer give anyone edit rights. The `owner_id` columns on programs, semesters, courses, units and topics record who created the row (`created_by` in the code); they are not owners.

## Equations and images in content
Topic content is Markdown with math: `$x^2$` inline, or a block with `$$` on its own line above and below. Chemistry uses mhchem, for example `$\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$` (`v` is a precipitate arrow, `^` a gas arrow). In the editor, **Add image** uploads a PNG, JPG, GIF or WebP (max 3 MB) and inserts it at the cursor; **Preview** shows the result. Admins and faculty can upload. Files are saved in `backend/uploads` (set `UPLOAD_DIR` to move it) and must be backed up with the database. Images are served without sign-in (random names) because `<img>` tags can't send a login token. If a reverse proxy sits in front, allow request bodies of at least 3 MB (nginx `client_max_body_size 4m`). A literal dollar sign in content may need escaping as `\$` when a second one follows in the same paragraph.

## Draft and publish
Topics have a Published flag. Drafts are visible to admins and the course's owner only: students don't see them in the course list, and opening, reading, bookmarking or asking the AI about a draft returns "not found". In the editor, tick "Published" (it starts unticked for faculty and ticked for admins). In a unit, the eye icon on a topic publishes or unpublishes it, and "Publish all N drafts" publishes the whole unit. Faculty can publish topics in their own courses, and the topic page has Publish/Unpublish buttons. Saving a topic's content never changes whether it is published. Topics created by CSV import are published. Existing topics stay published when the `topics.published` column is added on start.

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

## Quizzes
Admins and faculty (for their own courses) add multiple-choice quizzes to a unit: open the unit, tap **Add quiz**, set a title and pass mark, write questions with 2 to 6 answers, tick the correct one and add an optional explanation (Markdown and `$math$` work). A quiz stays a draft until **Published** is ticked. Students open it from the unit, answer, and are graded on the server, so the correct answers are never sent to the browser before they submit. They then see their score, pass or fail and which of their answers were right; the correct answers and explanations are never sent to students (admins and the course's faculty see them). Students can try again as often as they like; the best score shows on the unit. Quizzes follow the same program and semester rules as topics and disappear with their unit or course.

## Reports
**Reports** now shows, per course, how many students can see it, how many topics it has, the average share of topics read, and quiz averages (each student's best score per quiz). Filter by program and semester, tap a course to see every student's completion, topics read, quiz results and last activity, and download either list as CSV (names starting with `=`, `+`, `-` or `@` are escaped so spreadsheets can't run them). Admins see all courses; faculty get a Reports page limited to their assigned courses. "Read" means the student opened the topic (completion in Reports is still based on opening, not on "Mark as completed"); only published topics count.

## AI (one key for everyone)
An admin saves a DeepSeek key under **AI config** (or sets `DEEPSEEK_API_KEY` in `.env` as a fallback). That single key serves every student. With a key, the Explain and Sample answer buttons work, and each answer is saved and reused for all students. Without a key, or if the key is removed, students see "AI unavailable. Try again later." and the buttons are hidden, saved answers included, until a key is added again. If DeepSeek errors, times out or rejects the key, students see the same message and can try again, while admins also get the likely cause. **Test the key** checks it with a tiny request, and **Remove the key** turns AI off for everyone. `GET /api/ai/status` tells the app whether AI is on.

## Forgot password (email)
Set `SMTP_HOST`, `SMTP_FROM` and `APP_URL` in `.env` (plus `SMTP_PORT`, `SMTP_TLS`, `SMTP_USER`, `SMTP_PASSWORD` as your mail server needs; see `.env.example`) and restart. The sign-in page then shows **Forgot password?**: the person enters their email and gets a link that works once, for 30 minutes (`RESET_MINUTES`). Choosing a new password signs them in, ends every older session and link, and lifts any sign-in lockout. Details that matter:
- The answer is the same whether or not the email has an account, so the form can't be used to find out who is registered, and disabled accounts get no mail.
- Links always point at `APP_URL`, never at the request's Host header, so a forged header can't redirect a reset link. The token sits after `#` so it never reaches server logs, and only a hash of it is stored.
- Limits: 3 emails an hour per account and 20 requests an hour per address.
- Without SMTP settings the sign-in page says "Ask your admin to reset it", and the admin Reset button still works. **AI & email** (admin) shows whether email is on and can send a test email to you.

## Self-registration

Off by default. Turn it on under Settings > Self-registration. It also needs email set up (`SMTP_HOST`, `SMTP_FROM`, `APP_URL`, see the forgot-password section); without that it stays closed.

- The sign-in page shows "Create an account". People give full name, institution, ID number, email, phone and a password.
- A 6-digit code is emailed (valid 10 minutes, 5 tries, resend after 30 seconds, at most 8 codes per email). **No account exists until the code is verified.** Then they are signed in as students.
- The sign-up form gives the same answer whether or not an email already has an account (an existing address gets a notice by email), and an institution + ID number can only be used once.
- Optional "only these email domains" (for example `college.edu`) limits who can register.
- They arrive with no program or semester. Find them in Users (marked "Self-registered"; search by name, email, ID or phone), then use Select several > Move.
- **AI uses their own key.** Self-registered people never use the shared admin key. They add a DeepSeek key under "My AI key"; it is checked with DeepSeek, then stored encrypted (derived from `JWT_SECRET`, so changing that secret means they add their key again). Until they do, AI shows as off for them.

## Shared question bank

A pool of questions every faculty member and admin can browse, so a good question is written once and reused across courses.

- In a quiz, **Save to bank** shares its questions (optionally with tags such as `water, hardness`; the quiz and course name are kept as the source). Exact duplicates are skipped.
- **Add from the question bank** searches by words, tag or source ("Only mine" narrows it), then adds the ticked questions to the quiz you are editing. Review them, tie them to topics, then save.
- Adding **copies** the question, so editing or deleting it in the bank never changes a quiz students are already taking.
- Everyone on staff sees every bank question. Only the person who added a question, or an admin, can edit or delete it. Students never see the bank.
- API: `GET/POST /api/bank`, `PUT/DELETE /api/bank/{id}`, `POST /api/bank/from-quiz/{quiz_id}`, `POST /api/quizzes/{quiz_id}/questions/from-bank`.

## Semester or year programs

Each program is either a **semester** program (B.E., B.Tech, M.E.) or an **annual** program (M.B.B.S, B.Sc, law). Choose it when you create the program under Programs > New program.

- The terms are created for you: Semester 1 to 8 (default for semester programs) or Year 1 to 4 (default for annual programs). Pick 0 to 8, so M.B.B.S can start with 5 years. You can go straight to adding courses.
- Everything then speaks the program's own word: the program page, adding a term, Users (placing a student, bulk Move, a student's "Year 2"), and starting a new term ("moves up one year").
- Edit a program to change its pattern. Terms still named "Semester n" or "Year n" are renamed to match; terms you named yourself keep their names.
- Existing programs stay semester programs. The CSV import creates an annual program when its terms are called "Year 1", "Year 2" and so on. Students' year or semester is a number from 1 to 8 either way, and a student sees every term up to their current one.

## Strengths and weak areas
Authors tie each quiz question to the topic it tests (the "Topic this tests" menu in the quiz editor; untied questions count under their unit). From each student's **latest** result in each published quiz the app works out, per topic, what share they got right: **80% or more is a strength**, **below 60% needs another round of study**, and in between is "getting there" (`STRONG` and `WEAK` in `backend/main.py`). A retake replaces the earlier result, so improving moves a topic up.
- **After a quiz** the student sees "How you did by topic" with the weakest first and a **Study again** button that opens the topic. They still don't get the answer key.
- **My progress** (students' drawer) lists strengths and the topics that need another round of study across all their courses, with whether they have opened or completed each topic.
- **Staff** see, in Reports > a course, the topics the class finds hardest (with how many students need another round) and, under each student, their strong and weak topics; the students CSV gains "Strong areas" and "Needs another round of study" columns. Faculty see only their own courses.
- A draft topic is never named to students (its questions count under the unit), and attempts made before this feature have no per-question detail, so they are ignored until the student retakes the quiz.

## Look and branding
- The app follows the device's light or dark setting. Each person can force Light or Dark (or go back to Auto) with the switch at the bottom of the menu; the choice is remembered in that browser.
- Admins set the institution's name and logo under Settings. The logo is a PNG, JPG or WebP uploaded there (under 3 MB, square works best). It appears on the sign-in page and in the menu; without one, a neutral mark is shown. Clearing the name goes back to `APP_NAME` in `.env`.
- Fonts are bundled with the app, so nothing is loaded from the internet.

## Staff workflow
- **Home** for admins and faculty lists what needs attention (courses with no owner, students not placed in a program and semester, draft topics, semesters without a number, students who have never opened a topic) and the course table with completion. Faculty see only their own courses.
- **Dashboard cards open their list**: tap any number (Active students, Studied this week, Faculty, Courses, Topics, Drafts) or any "Needs attention" item to see the rows behind it. The list has search, sorting and 5 rows per page; tap a row to open that user, course, topic or program.
- **Start a new term**: Programs > a program > "Start a new term". It previews, then moves every active student up one semester. Students already in the program's last semester are left alone or have their accounts switched off, as you choose. Run it once per term.
- **Quizzes from a CSV**: in the quiz editor, "Import from CSV" adds questions from a file with the columns `question, a, b, c, d, correct, explanation, topic` (`correct` is a letter or number; `topic` is matched to a topic title in the unit). Problem rows are listed and skipped; nothing is saved until you press Save quiz. "CSV template" downloads an example.
- **Preview as student**: on a topic page, staff can hide the editing buttons to see what students see.
- **Bulk actions in Users**: "Select several users", tick people (or "Select all shown"), then Move (program and semester), Disable, Enable or Reset passwords. Your own account and anyone an action can't apply to are skipped and listed. Reset passwords gives a one-time download of the new passwords; each person must choose their own at next sign-in.
- **Topic version history**: every save of a topic's text (editor, CSV re-import, restore) is kept, up to the latest 100 per topic. On a topic page, staff who can edit the course open "Version history", compare any version with the current text (red = only in the old version, green = in the current text) and restore it. Restoring adds a new version, so nothing is lost. A topic that predates this feature keeps its old text as a baseline the first time it is edited. Students never see history.
- **Copy topics and units between courses**: on a topic page, "Copy to another course" copies that topic into a unit you choose; inside a unit, "Copy this unit to another course" copies the unit with all its topics and, if you may edit the original, its quizzes (with each question still tied to the right copied topic). You can copy into any course you can edit; admins can copy anywhere. Copies are always drafts, names stay unique ("Water (copy)"), the original is untouched, and reading progress, bookmarks, deadlines and saved AI answers are not copied. Someone else's draft topics are never copied.
