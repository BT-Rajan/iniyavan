# Zigora
Multi-user engineering study app: FastAPI + MariaDB/MySQL + React PWA. DeepSeek explains topics and writes sample answers; results are cached centrally so each topic costs tokens once.

## Production first run
1. DB: `CREATE DATABASE engtutor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL ON engtutor.* TO 'app_user'@'localhost'; FLUSH PRIVILEGES;`
3. `cp .env.example .env` and fill it in.
5. `./run.sh` (installs deps, builds the UI, starts the app under pm2; serves API and UI on HOST:PORT)
6. Sign in as the admin, add the DeepSeek key under Admin, then add students.

The PWA installs only over HTTPS (or localhost), so put the app behind a TLS reverse proxy.

## Topic content: Markdown, HTML, or HTML with JavaScript
In the topic editor, **Fill from files** takes the content as a Markdown `.md` file (a plain file is the content; one with the config sections fills the other boxes too) or an HTML file, with any images it uses. The content format has three choices:
- **Markdown** and **HTML**: HTML is cleaned when it is saved (no scripts or styles), so it takes the app's look.
- **HTML + JavaScript**: choose this before picking the file to keep the page whole, scripts and styles included. It runs only in a sandboxed frame (`GET /api/topics/{id}/frame`, served with `Content-Security-Policy: sandbox allow-scripts` and no same-origin), so its scripts work but can't read the app's sign-in, call the API as the reader or change the app's page. The frame is reached with a pass that is good for that one topic for 8 hours and is never accepted as a sign-in. A sandboxed page also can't keep data in the browser (localStorage) between visits. Search and the AI read only its words, never its scripts.

**Many topics at once:** on a unit, **Upload topic files** takes several `.html`/`.md` files, or a whole folder (its images are matched by file name), and makes one topic per file in file-name order. It shows what each file becomes first; you choose drafts or published, and whether to keep each page's JavaScript.

**Interactive pages remember.** A sandboxed page can't use the browser's storage, so the app gives it a stand-in: `localStorage` works as usual, starts with what that student saved last time, and each change is saved on the server for them (up to 100 KB per page per person; `sessionStorage` lasts while the page is open). It follows the student to other devices.

Students open a topic straight into a **full-screen reader** (with a button for the browser's own full screen). Anyone can select text and press **Highlight** to save it; tapping a highlight offers **Remove highlight**. Highlights come in four colours (coral, yellow, green, blue) and can carry a note. **My highlights** in the menu lists all of them across topics, with search and a colour filter. Highlights are saved per person (`/api/topics/{id}/highlights`, `DELETE /api/me/highlights/{id}`), listed in the reader's side panel and under the topic's notes, and come back each time the topic is opened. A highlight is stored as its text plus the words just before it, so it is found again even if the topic is edited elsewhere.

## Notifications
The bell shows what needs doing: for staff, the Home page's "Needs attention" items; for students, overdue and due-soon topics and tests not tried or not passed. The badge counts only new ones; opening the list marks them seen, and an item comes back as new when it changes (for example, more drafts). When email is set up (SMTP in `.env`), anyone can tick **Email me a daily summary** in the bell: once a day, after `DIGEST_HOUR` (default 7, local time per `DAY_OFFSET_MINUTES`), they get an email listing their new notifications, and nothing when there are none.

## Languages: English, Arabic and Tamil
Everyone picks their language with the switch in the header (and on the sign-in page): English, العربية or தமிழ். The choice is saved to their account (`PUT /api/me/lang`) and on the device; a first visit follows the browser's language. Arabic turns the whole app right to left (the side menu moves to the right, arrows for back and next turn round). Arabic and Tamil text use Noto Sans, downloaded only when needed.

- **How text is translated:** the screens are written in English and every piece of text goes through `t()` (`frontend/src/i18n.js`), which looks it up by its English wording in `frontend/src/locales/ar.json` and `ta.json`. Anything not in the dictionary shows in English. `{name}`-style placeholders are filled in at run time and may sit anywhere in a translation. Messages from the server are looked up the same way, so the common ones are translated; rare ones and emails stay English.
- **Fixing or adding a translation:** edit the JSON file (the key is the exact English text). The translations were made with AI help; have a native Arabic and a native Tamil speaker review them before students use them.
- **AI answers** (Explain, Sample answer, AI search, explanations and practice questions in student-built courses) come in the person's language. Saved answers are kept per language, so each language costs AI tokens once per topic.
- What people type (topic content, course and program names, highlights) is never translated.

## Name, logo and colours
The app is called Zigora (formerly Eng Tutor). The name comes from `APP_NAME` in `.env`; an older `.env` may still say `APP_NAME="Eng Tutor"`, so change it there and run `./run.sh`. An admin can also set another name and logo under Settings, which wins over `.env`. Without a custom logo the app shows the Zigora mark (`frontend/public/favicon.svg`; the PNG icons beside it are drawn from the same shape). The colours are plum `#722f99`, stone `#c5c1c1`, cream `#fee7c8` and coral `#ff9292`, set as variables at the top of `frontend/src/styles.css`. The pm2 process and the database keep the name `engtutor`, so existing servers carry on unchanged.

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
Students and faculty can bookmark a topic with the bookmark icon at the top of the topic page (tap again to remove it). Admins manage content and have no bookmarks. Each bookmark is one topic, never its unit or course. Bookmarks are private to each user. The Bookmarks page in the drawer lists only the topics you saved: pick a semester or year, then a course tab, and its saved topics appear under their unit headings (units with nothing saved are left out). Bookmarked topics also carry a small bookmark mark in the Learn lists. The `bookmarks` table is created automatically on start.
- **Archive and restore**: programs, semesters or years, courses, units and topics can be archived instead of deleted. Archiving hides an item and everything under it; nothing is removed, and reading progress, bookmarks and quiz results are kept. Students see an archived course as a locked name with "Unavailable right now" and cannot open anything in it. Archived topics and units simply disappear for students. Admins can archive and restore at every level; the faculty owner of a course can archive and restore that course and its units and topics, but not programs or semesters. An item archived because its parent is archived can only be restored by restoring the parent first. Restoring a parent brings back everything that was archived with it, while items archived on their own stay archived. Archived courses and topics are left out of the dashboard numbers, reports and attention lists. Staff see archived items hidden by default with a "Show archived" tick, and the Programs page has an Active, Archived and All filter. API: `PUT /api/{programs|semesters|courses|units|topics}/{id}/archive` with `{"archived": true|false}`; the `archived_at` columns are added by migration 0017.

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
Admins and faculty (for their own courses) add multiple-choice quizzes to a unit: open the unit, tap **Add quiz**, set a title and pass mark, write questions with 2 to 6 answers, tick the correct one and add an optional explanation (Markdown and `$math$` work). A quiz stays a draft until **Published** is ticked. Students open it from the unit, answer, and are graded on the server, so the correct answers are never sent to the browser before they submit. They then see their score, pass or fail and which of their answers were right; the correct answers and explanations are sent to students only when the quiz is set to show them (admins and the course's faculty always see them). Students can try again as often as they like; the best score shows on the unit. Quizzes follow the same program and semester rules as topics and disappear with their unit or course.

## Students bring their own notes to a course
The college sets the framework: program, semester, course, units and topics. A course can be just that framework (topic titles and order, no content), so staff don't have to write or format every topic. Each student brings their own material for it.

On a course page a student taps **Bring your own notes** (later **Your notes in X of Y topics**):
1. **Your files:** add PDFs (with selectable text), Word (.docx) or text files, or paste text. Several files are joined in order.
2. **File it under the syllabus:** **Match with AI** cuts the material into parts and puts each under the course topic it is about, judging by meaning (headings may be worded differently from the syllabus). It never rewrites the text. **Match by headings** (no AI) uses headings that match topic titles; sub-headings stay with their topic, and a paragraph that starts with a topic's title counts as its heading (PDFs often lose heading styles). Parts about nothing in the syllabus (a preface, an index) are left out.
3. **Check where each part goes:** each part shows its heading or first words, its size, **Read it**, and the topic it is filed under, which the student can change. The screen says how many topics are covered and which are not yet.
4. **Save to my topics:** each topic gets the student's notes, shown on the topic page under **Your notes** (alone when the topic has no staff content, otherwise below it). Quick checks and quizzes on the topic also ask about them.

**Scanned PDFs** (pages that are only pictures) are read with text recognition (Tesseract) on the server, in both this screen and Build a course. The file appears at once with "Reading scanned pages… 3 of 40" and the screen updates by itself; matching or slicing waits until it is done, and the student can leave and come back. Pages that already have text keep it; only picture pages are recognised. Printed pages read well; handwriting does not. A blank PDF (no text and no pictures) is refused. If the server restarts while a file is being read, it shows "Reading stopped…" and the student adds it again. Setup: `sudo apt install tesseract-ocr` (and `tesseract-ocr-tam`, `-hin`… for other languages, with `OCR_LANGS=eng+tam` in `.env`); `OCR_WORKERS` (default 1) files are read at a time, `OCR_MAX_PAGES` (default 300) pages per file, a few seconds a page. Without Tesseract, scanned PDFs are refused with a clear message and everything else works.

The notes are private: classmates, faculty and admins don't see them. Saving again rebuilds the notes from the material; **Remove my material** deletes the material and its notes. Reading, completion and quiz results are never touched. Only published, non-archived topics are offered, and only students who can open the course can add material. Matching with AI counts as one request toward the daily AI limit. Tables `course_materials` and `topic_notes` are created on first start. API under `/api/courses/{id}/my-material`.

## Students build their own courses
Students have **Build a course** in the menu. It turns their own notes, textbook chapters or handouts into a course they study in the app, next to the courses staff set up.

1. **Name** the course.
2. **Material:** upload PDFs (with selectable text; scanned pages can't be read), Word (.docx) files, or .txt/.md files, and/or paste text. Several files are joined in the order they are added. Word headings, lists and tables are kept.
3. **Slice:** the AI groups the material into units and the smallest topics that make sense on their own. The student can write notes for it ("one topic per verse", "keep the vocabulary table together"). The AI only decides where each topic starts and ends and what to call it: topics keep the student's own words, nothing is rewritten or invented. Without AI, **Slice by headings** uses the document's headings.
4. **Preview:** every unit and topic with its size and the start of its text, **Read it all**, rename, **Merge with next** and **Remove**. Change the notes and slice again as often as needed; **Save outline and finish later** keeps the work.
5. **Finish** builds the course. **Change the setup** goes back to the outline later; finishing again replaces the topics (after asking), with their progress and quiz results.

Studying a course: topics in order with **Mark as completed**, previous/next, and an AI **Explain** (saved, so it is asked once per topic). On any topic, **Quick check** gives 5 AI-written questions with the answer and explanation right after each one; **Full quiz** gives 10 questions scored at the end (pass mark 60%), with what the student knows well and what to revisit. Every request writes new questions, asked to differ from the last ones, and the AI is told to use only facts in the material. The course page shows topics completed, the quiz average and each topic's best quiz score sorted into strong, getting there and revisit.

**Keeping a self-learner going** (simple, measurable, fun):
- **One next step.** Home and Build a course show a card with the day streak, level and points, this week's study days, **Review N topics due** and **Continue: <next topic>**. Students who have not built a course yet get a "Build a course from your own notes" shortcut on Home.
- **Stars and mastery.** Every topic has up to three stars: ★ completed, ★★ passed a full quiz (60%+), ★★★ mastered (90%+ in a full quiz). The course shows its mastery % (stars earned out of all possible).
- **No bookkeeping.** A quick check with 4 of 5 right, or a passed quiz, marks the topic completed.
- **Spaced review.** After every check a topic is scheduled to come back: 1, 3, 7, 14 then 30 days as results stay good (80%+), tomorrow again when they are poor (under 60%). **Review** mixes the student's own earlier questions on the due topics (two per topic, up to ten), with the answer after each one, and moves each topic on its own schedule. Reviews use no AI requests.
- **Points and levels.** 10 per topic completed, 1 per right answer, 20 per topic with a passed quiz, 30 more per mastered topic, 5 per review. Level 2 starts at 100 points, level 3 at 300, then 600, 1000 and so on. Points are worked out from what the student did, so they can't drift. After a check the student sees the points gained, new stars, "Topic completed", "Mastered!" or a new level, and when the topic comes back for review.
- **Streak.** Opening topics and taking checks in these courses count toward the day streak on Home, like the staff-made courses.

**Smaller things that keep a student unstuck:**
- **Checks on every topic.** Topics in staff-made courses also have **Quick check · 5** and **Full quiz · 10**, written by the AI from the topic's notes on demand.
- **Fix a topic later.** The owner of a course can edit a topic's title and text, or delete it, from the topic page without redoing the setup. Progress and stars stay.
- **Explanations fit the material.** Explain in student-built courses uses its own tutor prompt for any subject, written in the material's language.
- **Knowing what AI is left.** When 10 or fewer of the day's AI requests are left, topic pages say how many. Without an AI key, the AI buttons are off with the reason, and the wizard suggests slicing by headings.
- **Flow.** After a check, **Next topic** goes straight on. Courses with more than 12 topics have a **Find a topic** box. **This question is wrong** on any answered question keeps it out of future reviews.

Sharing: a course is private. Its owner can share it with **My classmates** (students in the same program); they can study it and take their own quizzes, but only the owner can change it. Admins can open and delete any of them through the API.

AI use follows the usual rules: self-registered students use their own DeepSeek key; others use the admin's key and are limited to `STUDY_AI_DAILY` (default 40) AI requests a day for their own courses. Limits: 50 courses per student, 20 MB per file, 1.5 million characters of material per course. API under `/api/study/...`; the tables are created on first start.

## Topics from an HTML file and a config file
In the topic editor (Add topic, or Edit topic), **Fill from files** takes an HTML file for the content and a config `.md` file for everything else. Choose them together, with any images the HTML uses, and the form fills in. Check it, then save. Nothing is saved until you do.

The config file (**Config template** downloads an example):

```
---
title: 1. Introduction and learning objectives
published: no
deadline: 2026-10-20 17:00
---

## Question pattern
...

## Sample content
...

## How an answer should be
...
```

- Everything is optional. The front matter sets the title, published (yes/no) and the learning deadline (`2026-10-20` or `2026-10-20 17:00`). The `##` sections fill the boxes of the same name; `Answer guideline` and `Sample answer` work too. Other headings stay inside the section they are in, so a sample answer can have its own headings. A `## Topic content` section is used as Markdown content when there is no HTML file.
- Without a title in the config, the HTML file's `<title>` or first heading is used.
- The HTML keeps its structure (headings, lists, tables, links, images, right-to-left text) and takes the app's look in light and dark mode. Scripts, styles, forms, frames and event handlers are removed on the server when it is saved and again whenever it is shown, so an uploaded file can't run code. The editor's preview is cleaned the same way.
- Images embedded in the HTML (`data:` images) are saved as uploads. Images referenced by file name (`<img src="figs/chart.png">`) use the image file of that name chosen with the HTML; any others are left out and named.
- The content box has a **Markdown / HTML** switch, so an HTML topic can still be edited by hand; **Add image** inserts an `<img>` in HTML mode. Version history, restore and copying keep the format. A CSV import always writes Markdown content. Search and the AI read the text of an HTML topic, not its tags.
- API: `POST /api/topics/from-files` (`unit_id`, `html`, `config`, `images` as file name → upload url) returns the filled fields; topics take `content_format` (`markdown` or `html`). Migration 0019 adds `content_format` and, on MariaDB/MySQL, makes topic content MEDIUMTEXT.

## MCQ tests (whole course, from a CSV)
A course test is a multiple-choice test for a whole course rather than one unit. The course owner or an admin opens the course and taps **New MCQ test from a CSV**.

1. **Attach the CSV.** One question per row. Columns: `question`, `a` to `f` (the answer choices; leave the later ones blank if there are fewer), `correct` (the letter, the number or the exact answer text), and optionally `explanation`, `topic` (a topic title from the course), `area` (a skill name for questions not tied to a topic), `question_image` and `a_image` to `f_image` (image file names). **Download the template** shows the format. Comma, semicolon and tab files all work, up to 200 questions. Rows that can't be read are listed with the reason and left out; a topic name that isn't in the course becomes an area.
2. **Preview, add images, save.** Every question can be checked and edited. Questions and answer choices named in the image columns show "Needs boiler.png": **Upload images** takes all the files at once and matches them by file name, or upload each one in place (Skip drops it). Any question or answer can get an image here even if the CSV didn't name one, and an answer can be just an image. **Create test** stays disabled until every named image is uploaded or skipped. Tick **Published** when students may take it, and **Show students the correct answers and explanations after they submit** if they should see the key.

Students find the test on the course page under **MCQ tests**, and on Today when they haven't taken it or haven't passed yet. After submitting they see the score, a sentence on what they are good at and what to revisit, the areas grouped as Needs another round / Getting there / Strong (by topic, else by area), and **Review answers**, a question-by-question view of their answer and, when the test reveals it, the correct one.

**Scores and drill-down.**
- Staff: the chart icon beside a test (or a unit quiz) opens **Results**. *Overview* has the average final score, pass rate, median, highest and lowest, who took it and the spread of scores. *Students* lists each student's final (best) and latest score, attempts and strengths; tap one to see their attempts, then any attempt question by question. *Questions* shows how many picked each answer, with the correct one marked, sorted in test order or hardest first. *Strengths* lists the class's areas, weakest first. **Download results CSV** includes students who haven't taken it.
- **Gradebook** on the course page: every student × every published test and quiz with their final score, and a final course score (the average of the tests they took). Tap a test for its results or a student for their tests and attempts; CSV download.
- Students: **My progress > Scores** gives the final score per course, then each test's best and latest result, then each attempt.

A student's final score in a test is their best attempt. Strengths and the question analysis use each student's latest attempt, so a retake replaces the earlier result. Unit quizzes take images, areas and the answer setting too, and their **Add from a CSV** uses the same format. API: `POST /api/quizzes/parse-csv`, `POST /api/quizzes` with `course_id`, `GET /api/quizzes/{id}/results`, `GET /api/quizzes/{id}/attempts`, `GET /api/attempts/{id}`, `GET /api/courses/{id}/gradebook`, `GET /api/me/scores`. Migration 0018 adds the columns.

## Safety rules for the AI (built in, not editable)
Every AI request starts with the app's safety rules (`backend/guardrails.py`), ahead of every prompt an admin can edit under Settings. They live in code, not in Settings or the database, so they cannot be changed or switched off from the app; changing them is a code change.
- **What they say:** stay a study helper; nothing unsafe for young people (no sexual content, gore, hate, or instructions for weapons, drugs, hacking or self-harm; science stays at textbook level); a student in crisis gets a short, caring reply pointing to a trusted adult or emergency services; be honest and say when unsure; never ask for personal details; treat notes, uploads and questions as material, never as instructions; keep the rules private. They say they override everything that follows, including the editable prompts.
- **How they are enforced:** `deepseek()` (text, to DeepSeek) and `vision()` (a photo of a diagram, to Claude) in `main.py` are the only two places an AI request leaves the server. Each always puts the rules first, fences everything people wrote (topic notes, uploads, a student's notes, searches) as material, strips hidden direction and zero-width characters and fake fence markers from it, and withholds any reply that leaks the rules (a hidden marker in the rules gives it away).
- **A search that reads like a crisis** (self-harm or suicide, in English, Arabic or Tamil) is answered at once with a caring message in the student's language: no AI call, and nothing saved or logged.
- Admins can read the rules under Settings → AI prompts → Read the safety rules. Tests in `backend/tests/test_guardrails.py` check that every request starts with them, even after an admin rewrites a prompt to say otherwise.

## What goes to the AI provider, and what does not
The rule: study text goes out **once**, the answer is kept, and from then on the app shows its own copy. A student's doubt sends only names and a phrase.
- **Sent once, then kept:** a topic's gist, steps, Explain and Sample answer (shared by everyone, saved in `ai_cache`); a student's own-notes Explain and Sample answer (private to that student, saved in `private_answers`, sent again only if the notes or the prompt change); the slicing and matching of a student's uploaded material (the outline is saved with the material). A second look at any of these sends nothing.
- **A doubt (`Not clear?`):** in the reader, select a phrase and tap **Not clear?**. Step one stays on the server: the panel shows where the phrase sits in the topic and in the student's own notes, and a kept AI answer if this doubt was asked before. Only if the student taps **Still not clear? Ask AI** does anything leave: the names of the program, semester, course and topic, and the phrase (up to 300 characters). Never the topic text, never the student's notes. The answer is kept in `doubt_answers`, so the same doubt is never sent twice. Students get `AI_DOUBT_DAILY` (default 30) AI doubts a day; kept answers are free. API: `POST /api/topics/{id}/doubt` (local) and `POST /api/topics/{id}/doubt/ask` (AI). The prompt can be edited under Settings > AI prompts like the others.
- **A highlight's explanation** (written when a student highlights a passage) sends, like a doubt, only the program, semester, course and topic names and the highlighted passage (up to 600 characters), never the notes. It is kept per passage and language and shared, so the same words are never sent twice.
- **Search** sends the typed search and the student's program and semester only; answers are kept and shared.
- **Ask from a photo** reads the photo's text on this server; only that text (checked by the student), their question and their program and semester go to DeepSeek. The photo itself leaves only when the student says the question is about a diagram, and then only to Claude. Photos are shrunk in the phone, re-encoded on the server (no location or camera details) and never stored; answers are not kept.
- **Still sent each time:** a new Quick check or Full quiz in a student-built course sends that topic's text again, because every request is meant to write different questions. Reducing that means generating a question bank once and drawing from it, which is not built yet.
- **The outbound log:** every request that leaves is recorded in `ai_egress`: who, which kind, which topic, how many characters, and whether it was answered. Never the text. Admins read the totals at `GET /api/admin/egress?days=30`.

## Ask from a photo
The camera beside the search box opens **Ask from a photo**: a student photographs a question, a paragraph or a diagram in their book (or picks a photo), checks the text the server read from it, and asks (quick choices: Explain this simply, Solve it step by step, What will the exam ask about this?; with a diagram: What does the diagram show?). Answers come back short, with "This looks wrong?" under each.
- **Text:** read on this server with Tesseract, in the languages in `OCR_LANGS` (for English, Tamil and Arabic: `OCR_LANGS=eng+tam+ara`, with the `tesseract-ocr-tam` and `tesseract-ocr-ara` packs installed). Only the text goes to DeepSeek.
- **Diagrams (optional):** DeepSeek cannot see images. Add a Claude API key under **Settings → AI → Photos of diagrams (Claude)** (or `ANTHROPIC_API_KEY` in `.env`), and use **Test the key**. Then a student can tick "My question is about a diagram" and the photo goes to Claude (default model `claude-opus-5-5`, changeable there; refused requests are retried on a fallback model by the API). A photo question to Claude costs roughly 1 to 2 US cents. Without a key, diagrams are read for their labels only. People who registered themselves never use the college's Claude key.
- Students get `AI_PHOTO_DAILY` (default 20) photo questions a day. The editable prompt is "Ask from a photo" under Settings → AI prompts; the safety rules come first as everywhere.
- After updating, run `pip install -r backend/requirements.txt` once (it adds the `anthropic` package).

## How students learn a topic: short, curious, their choice
The notes are the reference; the learning happens in small steps the student picks, and the app never assigns work.
- **The gist** heads every topic page: three short points and one curious question (the answer is one tap away). Then four steps, each a few lines that end in a question worth wondering about: **Why?**, **Example**, **Exam angle** (an exam-style question with a short model answer and what examiners look for) and **Quick check** (one question, answer on tap, nothing scored or reported). The full notes, Explain and the sample answer stay below.
- **Short by design:** the gist is about 50 words and each step at most about 80, with token limits on every reply. Explain is now at most 150 words. The Sample answer tab opens with the outline of a full-marks answer; the full answer is one tap away.
- **Remember this?** On Home, one question from a topic the student opened 2 to 60 days ago, taken from that topic's saved gist (no AI call). It changes daily and can be dismissed for the day.
- **No pressure:** Home shows where the student left off, Remember this? and their courses. There are no streaks, stat tiles, "today's focus" or late labels. A study routine appears only if the student sets one under My routine. A teacher's date shows as a plain date, and "I've learned this" is the student's own mark. Students are notified only of a teacher's date coming up and of new tests.
- **It adapts to each student, privately.** The steps a student opens most move to the front (after 3 taps). After a quick check's answer they can say "I had it" or "Not quite": mostly "Not quite" makes the next quick checks plainer, with a hint; mostly "I had it" makes them ask to apply the idea. "Not quite" also offers the idea again, more simply. After 3 topics opened in a unit, its other topics start with the question and keep the gist one tap away. Remember this? brings back topics whose last quick check was "Not quite". My progress shows the student what the app has picked up, with **Start fresh** to clear it. Teachers never see any of it, and staff are not profiled.
- **Quiet everywhere a student looks.** The student menu has four places: My courses, Saved (bookmarks and highlights), My progress and Build a course; About is in the footer. My progress shows "What clicked" and "Worth another look" without percentages, the optional study routine, test results folded away, and how the app adapts. Test results state the score and the pass mark without verdicts. Course and unit lists show how many topics there are and a tick on the ones the student marked as learned, with no completion bars. Courses students build have no streaks, points, levels or stars. Teachers' screens (gradebooks, pass marks, reports) are unchanged.
- **Highlight, then understand it.** When a student highlights a passage in the reader, a short card ("What this means", at most 60 words) explains it in plain words (the AI gets only the names and the passage). The explanation stays with the highlight (in the reader's list and in Saved), and tapping a highlight offers **Explain** too. It is saved per passage and language, so the same words cost tokens once; each student can ask for up to 40 new ones a day (`AI_LINE_DAILY`).
- **Revision sheet.** On a unit, **Revision sheet** puts every topic's gist, its question ("Ask yourself") and the student's own highlights on one page, with **Print or save as PDF** (two columns on paper). Missing gists are written as the sheet opens.
- **"This looks wrong?"** under every AI reply (gist, steps, Explain, sample answer and outline, highlight explanations, AI search). A student can add what looks wrong. The topic's teacher (admins for searches and everything) sees **Flagged AI answers** on their Home, never with the student's name, and chooses **Write it again** (the saved reply is dropped and the next request writes a new one) or **It's fine**.
- Every reply is saved per topic and language, so each costs AI tokens once. Admins can change any of these prompts under Settings → AI prompts.

## Lists: ten rows a page
Every list in the app shows at most ten rows; a longer one gets numbered pages under it (Previous, page numbers, Next, and "1–10 of 41"). Long lists from the server (users, courses, programs, the activity log, the Reports lists, the question bank) are fetched a page at a time; shorter ones the screen already holds use the `Paged` component in `frontend/src/App.jsx`. New screens follow the same rule: wrap a list in `<Paged rows={…} render={…}/>`, or use `usePaged` with `<Pager>` when the server pages it.

The **Activity log** can be searched by person or action and filtered by action (created, changed, deleted), result and time (last 24 hours, 7 or 30 days), newest or oldest first, and downloaded as CSV. On **Reports**, the most read topics, students and saved AI answers each have their own search, filter and sort; a course's student report can be searched and filtered (never opened a topic, under 50% completed, needs another round of study) and sorted by completion or last activity.

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

## Semester, year or grade programs

Each program is a **semester** program (B.E., B.Tech, M.E.), an **annual** program (M.B.B.S, B.Sc, law) or a **school** program (Grade 1 to 12). Choose it when you create the program under Programs > New program.

- The terms are created for you: Semester 1 to 8 (default for semester programs), Year 1 to 4 (default for annual programs) or Grade 1 to 12 (default for school programs). Semester and annual programs take 0 to 8, so M.B.B.S can start with 5 years; school programs take 0 to 12. You can go straight to adding courses.
- Everything then speaks the program's own word: the program page, adding a term, Users (placing a student, bulk Move, a student's "Year 2" or "Grade 7"), and starting a new term ("moves up one year"). The number dropdowns go up to 12 for school programs.
- Edit a program to change its pattern. Terms still named "Semester n", "Year n" or "Grade n" are renamed to match; terms you named yourself keep their names. A school program with grades above 8 cannot become a semester or annual program until those grades are deleted or renumbered.
- Existing programs stay semester programs. The CSV import creates an annual program when its terms are called "Year 1", "Year 2" and so on, and a school program when they are called "Grade 1" (or "Std 1", "Class 1"; Roman numerals such as "Grade XII" work too). Students' semester, year or grade is a number from 1 to 12, and a student sees every term up to their current one.

## Search (local first, then AI)

Students find topics from **Search** in the menu, or the search bar on Home.

- As they type, topics in their own program (up to their current semester or year, published only) are listed. Press Enter to search properly.
- If the app has a good match (the words appear in a topic title, unit or course name) it shows those topics. If there is no match, or only a weak one (a word buried in some notes), the **AI answers automatically** and any weak matches stay listed above it.
- **Recheck with AI** is on every result: after local results it asks the AI; after an AI answer it asks again from a different angle (a recheck is not saved for others).
- AI answers to a search are saved and shared, so the same question costs tokens once. Each student gets 30 AI searches a day (`AI_SEARCH_DAILY` in `.env`); saved answers don't count. Self-registered users use their own key, as everywhere.

## Editing the AI prompts

Settings > AI prompts lets an admin rewrite the instructions the AI gets for **Explain**, **Sample answer** and **Student search**: tone, language, depth, format. Saving discards the saved answers that the old wording produced, so the new prompt applies from the next question (that spends tokens again). "Reset to built-in" restores the original. Prompts are 20 to 4000 characters.

## Own-pace routine
Students pick **My routine** in the menu: their study days (Mon to Sun), minutes a session (15, 30, 45 or 60) and, optionally, their usual time. Home then shows **Today's session**:

- **One small session a study day:** 1 new topic (15 or 30 minutes), 2 (45) or 3 (60), plus one review set when reviews are due. The topic they already started comes first, then topics with deadlines (nearest first), then each course's next topic in turn, so no course is left behind. Staff courses and their own courses are both included.
- **Fixed for the day:** finishing a topic ticks it off; it doesn't add another. When every item is done the card says **Done for today** and when the next session is. Changing the routine redoes today's session only if nothing in it was done yet.
- **No pile-up:** after missed days, today is still one session, with "Welcome back… no catching up needed". The plan is worked out again each day from what is left: how many topics remain, when they'd be finished at this pace, how many would miss their deadline, and one suggestion (add a study day, or study longer) when that helps.
- **Rest days:** no session is made; **Study anyway** makes one. With a routine, the streak counts only the chosen days: a rest day doesn't break it, studying on one still counts. Without a routine nothing changes.
- **In the app only:** no messages are sent.

**Stop the routine** removes it and its daily sessions; progress is untouched. Tables `routines` and `day_sessions` are created on first start. API: `GET`/`POST /api/me/session`, `PUT /api/me/routine`, `POST /api/me/routine/stop`.

## Student dashboard

Home for a student is a plan for the day, not a list of everything.

- **Today's focus:** up to four next steps, most urgent first: overdue topics, topics due within three days, topics tied to weak quiz results, the topic they started, quizzes to retake (below the pass mark) or try, and the next topic in each course. A topic appears once, with the reason in plain words ("Overdue by 2 days", "You scored 40% on questions about this").
- **Study streak and week:** consecutive days with any study (opening a topic, completing one or taking a quiz), and a 7-day strip. A day not yet studied does not break a live streak. Days follow the college's time zone: set `DAY_OFFSET_MINUTES` in `.env` (default 330 for India; 0 for UTC).
- **Tiles:** streak, topics completed this week, overall completion, quiz average (best score per quiz).
- **Courses:** progress, overdue count and the next topic to open.

## After an update: rebuild the screens

The built screens (`frontend/dist`) are not stored in git. After `git pull`, run `./run.sh` (it rebuilds and restarts). If you only restart the backend, the app serves the old screens and new features seem to be missing (for example the new student dashboard, or a program getting 8 semesters instead of the years you chose). To check, open `/api/version` on your server: `"match": true` means the screens are up to date; `false` shows what to run.

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

## Front-end conventions
The UI is one React file (`frontend/src/App.jsx`) and one stylesheet. So that every screen behaves the same, reuse these pieces instead of writing a new variant:
- **Confirmations:** `const confirm=useConfirm()`, then `if(!await confirm({title,body,ok,danger}))return`. Don't use the browser's `confirm()`.
- **Sheets:** `<Sheet close={...}>` for every bottom sheet (Escape closes the top one; focus moves in and back out). Back out with **Cancel**; use **Close** or **Done** only on sheets that just show something.
- **Shared parts:** `<Skeleton/>` for loading (not "Loading…" text), `<Toast/>` via `toast(msg)`, `<ShowMore left={n} onClick={...}/>` for long lists, `<Tabs/>` for tab bars.
- **Spacing and badges:** section headings are `<h3 className="sec">` (`sec first` at the top of a page); status badges are `pill sm`; the button that opens a list is `btn ghost lead`; a row's action buttons go in `<div className="acts">` so they wrap under the title on a phone.
- **Tappable rows** are buttons (`row rowbtn`) with a chevron, never a clickable `div`. Colours come from the theme variables (`--ok`, `--warn`, `--bad`, `--info`, `--acc`) and corner radii from `--r-ctl`, `--r-box` and `--r-sheet`.
