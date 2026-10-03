import gzip, os, sqlite3, tarfile, time
from sqlalchemy import create_engine, text
import main
from main import Session_, AuditLog, User
from backup import run_backup

def test_migrations_upgrade_an_old_database_and_are_recorded(tmp_path):
    url = f"sqlite:///{tmp_path}/old.db"; e = create_engine(url)
    with e.begin() as c:  # a database from before units, enrolment, forced password change and drafts existed
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, pw TEXT, role TEXT, active BOOLEAN)"))
        c.execute(text("CREATE TABLE topics (id INTEGER PRIMARY KEY, title TEXT, subject_id INTEGER)"))
        c.execute(text("CREATE TABLE subjects (id INTEGER PRIMARY KEY, name TEXT)"))
    old = main.engine; main.engine = e
    try:
        main.upgrade_schema(); main.upgrade_schema()  # the second run must change nothing
        cols = lambda t: {x["name"] for x in __import__("sqlalchemy").inspect(e).get_columns(t)}
        assert {"program_id", "semester", "must_change"} <= cols("users") and {"unit_id", "published"} <= cols("topics") and "semester_id" in cols("subjects")
        assert main.applied_migrations() == [m for m, _ in main.MIGRATIONS]
    finally: main.engine = old

def test_staff_actions_are_audited_and_student_reading_is_not(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n")
    tid = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["topics"][0]["id"]
    env.c.put(f"/api/topics/{tid}/publish", headers=env.admin, json={"published": False})
    env.c.post(f"/api/topics/{tid}/read", headers=env.stu); env.c.post("/api/login", json={"email": "admin@x.com", "password": "pw"})
    env.c.get("/api/tree", headers=env.admin)
    with Session_() as s: rows = [(a.method, a.path, a.status) for a in s.query(AuditLog)]
    assert ("PUT", f"/api/topics/{tid}/publish", 200) in rows and ("POST", "/api/admin/import", 200) in rows
    assert not any(p.endswith("/read") or p == "/api/login" or m == "GET" for m, p, _ in rows)
    r = env.c.get("/api/admin/audit", headers=env.admin).json(); assert r["total"] >= 2 and r["items"][0]["email"] == "admin@x.com"
    assert env.c.get("/api/admin/audit?q=publish", headers=env.admin).json()["total"] == 1
    assert env.c.get("/api/admin/audit", headers=env.fac).status_code == 403
    env.c.post("/api/topics", headers=env.stu, json={"title": "x", "unit_id": 1})  # a blocked attempt is recorded as such
    with Session_() as s: assert s.query(AuditLog).filter(AuditLog.status == 403).count() >= 1

def test_backup_makes_restorable_copies_and_prunes_old_ones(env, tmp_path):
    os.makedirs(main.UPLOADS, exist_ok=True); open(os.path.join(main.UPLOADS, "a.png"), "wb").write(b"img")
    out = tmp_path / "bk"; os.makedirs(out); old = out / "engtutor-19990101-000000-db.sqlite.gz"; old.write_bytes(b"x"); os.utime(old, (1, 1))
    files = run_backup(main.DB, main.UPLOADS, str(out), keep_days=14)
    assert not old.exists() and len(files) == 2
    db = next(f for f in files if "-db." in f); restored = tmp_path / "r.db"; restored.write_bytes(gzip.open(db).read())
    assert sqlite3.connect(restored).execute("SELECT count(*) FROM users").fetchone()[0] == 3
    with tarfile.open(next(f for f in files if "uploads" in f)) as t: assert "uploads/a.png" in t.getnames()

def test_upgrade_survives_an_old_semesters_table_without_semester_no(tmp_path):
    url = f"sqlite:///{tmp_path}/old2.db"; e = create_engine(url)
    with e.begin() as c:  # semesters exists but predates semester_no; migration 0007 reports orphans before 0010 adds the column
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, pw TEXT, role TEXT, active BOOLEAN)"))
        c.execute(text("CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT)"))
        c.execute(text("CREATE TABLE semesters (id INTEGER PRIMARY KEY, name TEXT, program_id INTEGER)"))
        c.execute(text("INSERT INTO courses (id, name) VALUES (1, 'Mech')"))
        c.execute(text("INSERT INTO semesters (id, name, program_id) VALUES (1, 'Semester 1', 1)"))
    old = main.engine; main.engine = e
    try:
        main.upgrade_schema()
        assert main.applied_migrations() == sorted(m for m, _ in main.MIGRATIONS)
        with e.connect() as c: assert c.execute(text("SELECT semester_no FROM semesters WHERE id = 1")).scalar() == 1
    finally: main.engine = old

def test_admin_sets_the_institution_name_and_logo_and_only_an_uploaded_image_is_accepted(env):
    assert env.c.get("/api/config").json()["logo"] is None
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    url = env.c.post("/api/uploads", headers={**env.admin, "Content-Type": "image/png"}, content=png).json()["url"]
    put = lambda hd, **b: env.c.put("/api/admin/branding", headers=hd, json=b)
    assert put(env.stu, name="X").status_code == 403 and put(env.fac, name="X").status_code == 403
    assert put(env.admin, logo_url="https://evil.example/x.png").status_code == 400  # outside addresses are refused
    assert put(env.admin, logo_url="/api/uploads/../../etc/passwd").status_code == 400
    assert put(env.admin, name="x" * 61).status_code == 400
    assert put(env.admin, name="  Karkathar College ", logo_url=url).status_code == 200
    cfg = env.c.get("/api/config").json(); assert cfg["name"] == "Karkathar College" and cfg["logo"] == url  # public: the sign-in page needs it
    assert put(env.admin, remove_logo=True, name="").status_code == 200
    cfg = env.c.get("/api/config").json(); assert cfg["logo"] is None and cfg["name"] == main.APP_NAME
