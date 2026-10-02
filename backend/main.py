from collections import defaultdict
import csv, io, json, os, re, hashlib, hmac, secrets, datetime as dt, httpx, jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, func, or_, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
APP_NAME = (os.getenv("APP_NAME") or "Eng Tutor").strip()
VERSION = "1.1.0"
DB = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/engtutor")
SECRET = (os.getenv("JWT_SECRET") or "").strip()
TOKEN_DAYS = int(os.getenv("TOKEN_DAYS") or 7)
ITER = int(os.getenv("PBKDF2_ITER") or 600000)  # password hashing cost; old 100000-round hashes are upgraded at next sign-in
TEMP_ITER = 100000  # one-time passwords made in bulk are hashed cheaply; the user's own password (set on first sign-in) gets the full cost
def require_secret():
    if len(SECRET) < 32 or SECRET in ("change-me",) or "generate-with" in SECRET:
        raise RuntimeError("JWT_SECRET is missing or too weak. Put a random value of 32+ characters in .env, for example: openssl rand -hex 32")
engine = create_engine(DB, pool_pre_ping=True)
Session_ = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100)); email = Column(String(190), unique=True)
    pw = Column(String(200)); role = Column(String(10), default="student"); active = Column(Boolean, default=True)
    must_change = Column(Boolean, default=False)  # set when an admin chose the password; cleared once the user picks their own
    program_id = Column(Integer, nullable=True, index=True)  # which program the student is enrolled in (no FK: users and programs reference each other)
    semester = Column(Integer, nullable=True)  # current semester, 1 to 8
class CourseFaculty(Base):  # which courses a faculty member may edit (units and topics only)
    __tablename__ = "course_faculty"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)
class Setting(Base):
    __tablename__ = "settings"
    k = Column(String(50), primary_key=True); v = Column(Text)
# Hierarchy: Program > Semester > Course > Unit > Topic.
# Program and Course keep their original table names ("courses", "subjects") so existing databases upgrade in place.
class Program(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
class Semester(Base):
    __tablename__ = "semesters"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
    program_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
class Course(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
    program_id = Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=True)
class CourseLink(Base):  # a common course shown in other programs' semesters as well; it is edited only at its home
    __tablename__ = "course_links"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("course_id", "semester_id"),)
class LoginFail(Base):  # failed sign-in attempts, used for lockout
    __tablename__ = "login_fails"
    id = Column(Integer, primary_key=True); email = Column(String(190), index=True); ip = Column(String(64), index=True)
    at = Column(DateTime, default=dt.datetime.utcnow, index=True)
class SchemaMigration(Base):  # which numbered migrations this database has already had
    __tablename__ = "schema_migrations"
    id = Column(String(80), primary_key=True); applied_at = Column(DateTime, default=dt.datetime.utcnow)
class AuditLog(Base):  # who changed what (staff actions and password changes; never request bodies or secrets)
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True); at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    user_id = Column(Integer, index=True); method = Column(String(8)); path = Column(String(200)); status = Column(Integer)
class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True); title = Column(String(200)); owner_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text); sample_content = Column(Text); question_pattern = Column(Text); guideline = Column(Text)
    published = Column(Boolean, default=True)  # drafts are visible to admins and faculty only
class Quiz(Base):  # a multiple-choice quiz attached to a unit
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True); unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), index=True); course_id = Column(Integer, index=True)
    title = Column(String(200)); pass_percent = Column(Integer, default=50); published = Column(Boolean, default=False)
class Question(Base):
    __tablename__ = "quiz_questions"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); pos = Column(Integer, default=0)
    text = Column(Text); options = Column(Text); correct = Column(Integer); explanation = Column(Text)  # options is a JSON list
class Attempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); user_id = Column(Integer, ForeignKey("users.id"), index=True)
    score = Column(Integer); total = Column(Integer); percent = Column(Integer); at = Column(DateTime, default=dt.datetime.utcnow)
class Progress(Base):  # what each student has read
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id")); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    reads = Column(Integer, default=1); last_read = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
class Bookmark(Base):  # topics a user has saved to their own list
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE")); created = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
class AICache(Base):  # shared by all students; key changes when the topic is edited
    __tablename__ = "ai_cache"
    id = Column(Integer, primary_key=True); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    kind = Column(String(10)); chash = Column(String(64)); text = Column(Text)
    tokens = Column(Integer, default=0); hits = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint("topic_id", "kind", "chash"),)

def _dk(p, salt, it): return hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), it).hex()
def hp(p, iters=None):
    it = iters or ITER; salt = secrets.token_hex(8)
    return f"pbkdf2_sha256${it}${salt}${_dk(p, salt, it)}"
def _parts(h):  # new format pbkdf2_sha256$rounds$salt$hash; legacy format salt$hash (100000 rounds)
    a = h.split("$")
    return (int(a[1]), a[2], a[3]) if a[0] == "pbkdf2_sha256" and len(a) == 4 else (100000, a[0], a[-1])
def vp(p, h):
    try: it, salt, dig = _parts(h)
    except Exception: return False
    return hmac.compare_digest(_dk(p, salt, it), dig)
def stale(h): return _parts(h)[0] < ITER
def fp(u): return hashlib.sha256(u.pw.encode()).hexdigest()[:16]  # changes whenever the password does, which signs out every old token
def make_token(u): return jwt.encode({"uid": u.id, "k": fp(u), "exp": dt.datetime.utcnow() + dt.timedelta(days=TOKEN_DAYS)}, SECRET)
def db():
    s = Session_()
    try: yield s
    finally: s.close()
def me(request: Request, authorization: str = Header(""), s: Session = Depends(db)):
    try: claims = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"]); uid = claims["uid"]
    except Exception: raise HTTPException(401, "Please sign in again")
    u = s.get(User, uid)
    if not u or not u.active: raise HTTPException(401, "Account disabled. Ask your admin.")
    if claims.get("k") != fp(u): raise HTTPException(401, "Your password changed. Please sign in again.")
    if u.must_change and request.url.path not in ("/api/me", "/api/me/password"): raise HTTPException(403, "Please set a new password first")
    return u
def admin(u: User = Depends(me)):
    if u.role != "admin": raise HTTPException(403, "Admins only")
    return u
def staff(u: User = Depends(me)):
    if u.role not in ("admin", "faculty"): raise HTTPException(403, "Admins and faculty only")
    return u
def can_edit(u, course_id, s):  # admins edit everything; faculty only their assigned courses
    if u.role == "admin": return True
    return u.role == "faculty" and s.query(CourseFaculty).filter_by(user_id=u.id, course_id=course_id).first() is not None
def need_edit(u, course_id, s):
    if not can_edit(u, course_id, s): raise HTTPException(403, "You are not assigned to this course")
def setting(s, k, d=""):
    r = s.get(Setting, k); return r.v if r else d

app = FastAPI(title=APP_NAME)
ORIGINS = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]  # the app is same-origin; set this only for a separate front-end
if ORIGINS: app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; "
       "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
SKIP_AUDIT = re.compile(r"/(read|bookmark|attempt)$|/ai/")  # student reading activity is already tracked as progress
def audit_write(uid, method, path, status):
    with Session_() as s: s.add(AuditLog(user_id=uid, method=method, path=path[:200], status=status)); s.commit()
@app.middleware("http")
async def audit(request: Request, call_next):
    r = await call_next(request)
    try:
        p = request.url.path; tok = request.headers.get("authorization", "")[7:]
        if tok and request.method in ("POST", "PUT", "PATCH", "DELETE") and p.startswith("/api/") and not SKIP_AUDIT.search(p):
            await run_in_threadpool(audit_write, jwt.decode(tok, SECRET, algorithms=["HS256"])["uid"], request.method, p, r.status_code)
    except Exception: pass  # logging must never break a request
    return r
@app.middleware("http")
async def secure_headers(request: Request, call_next):
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin", "Content-Security-Policy": CSP,
                      "Permissions-Policy": "camera=(), microphone=(), geolocation=()"})
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https": r.headers["Strict-Transport-Security"] = "max-age=31536000"
    return r

@app.get("/api/config")
def config(): return {"name": APP_NAME, "version": VERSION}
@app.get("/manifest.json")  # served dynamically so the installed app carries APP_NAME
def manifest():
    icons = [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
             {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
             {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    return JSONResponse({"name": APP_NAME, "short_name": APP_NAME[:12], "start_url": "/", "scope": "/", "display": "standalone", "orientation": "portrait",
                         "background_color": "#0e0a1f", "theme_color": "#0e0a1f", "icons": icons})

def _addcol(table, col, typ):
    def go(c):
        if col not in [x["name"] for x in inspect(c).get_columns(table)]: c.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
    return go
# Append new migrations at the END. Each runs once, is recorded in schema_migrations, and must be safe to run on a database that already has the change.
MIGRATIONS = [("0001_topics_unit_id", _addcol("topics", "unit_id", "INT NULL")), ("0002_subjects_semester_id", _addcol("subjects", "semester_id", "INT NULL")),
              ("0003_users_program_id", _addcol("users", "program_id", "INT NULL")), ("0004_users_semester", _addcol("users", "semester", "INT NULL")),
              ("0005_users_must_change", _addcol("users", "must_change", "TINYINT(1) NOT NULL DEFAULT 0")), ("0006_topics_published", _addcol("topics", "published", "TINYINT(1) NOT NULL DEFAULT 1"))]
def upgrade_schema():  # creates any missing tables, then applies pending migrations in order
    Base.metadata.create_all(engine)
    with engine.connect() as c: done = {r[0] for r in c.execute(text("SELECT id FROM schema_migrations"))}
    for mid, fn in MIGRATIONS:
        if mid in done: continue
        with engine.begin() as c:
            fn(c); c.execute(text("INSERT INTO schema_migrations (id, applied_at) VALUES (:i, :t)"), {"i": mid, "t": dt.datetime.utcnow()})
def applied_migrations():
    with engine.connect() as c: return [r[0] for r in c.execute(text("SELECT id FROM schema_migrations ORDER BY id"))]
@app.on_event("startup")
def boot():
    require_secret()
    upgrade_schema()
    with Session_() as s: s.query(AuditLog).filter(AuditLog.at < dt.datetime.utcnow() - dt.timedelta(days=400)).delete(); s.commit()
    with Session_() as s:
        for co in s.query(Course).all():  # topics without a unit go into "General"
            orphans = s.query(Topic).filter(Topic.course_id == co.id, Topic.unit_id.is_(None)).all()
            if orphans:
                un = Unit(name="General", course_id=co.id, owner_id=co.owner_id); s.add(un); s.flush()
                for t in orphans: t.unit_id = un.id
        for p in s.query(Program).all():  # courses without a semester go into "Semester 1"
            orphans = s.query(Course).filter(Course.program_id == p.id, Course.semester_id.is_(None)).all()
            if orphans:
                sem = Semester(name="Semester 1", program_id=p.id, owner_id=p.owner_id); s.add(sem); s.flush()
                for co in orphans: co.semester_id = sem.id
        s.commit()

class Login(BaseModel): email: str; password: str
DUMMY = None  # hashed lazily so a missing account takes as long to reject as a wrong password
def client_ip(request): return (request.client.host if request.client else "?")[:64]
def throttle(s, email, ip):  # 5 misses per account from one address, 20 per account, 200 per address, each per 15 minutes
    since = dt.datetime.utcnow() - dt.timedelta(minutes=15); q = s.query(func.count(LoginFail.id)).filter(LoginFail.at >= since)
    if q.filter(LoginFail.email == email, LoginFail.ip == ip).scalar() >= 5 or q.filter(LoginFail.email == email).scalar() >= 20 or q.filter(LoginFail.ip == ip).scalar() >= 200:
        raise HTTPException(429, "Too many wrong attempts. Please wait 15 minutes and try again.", headers={"Retry-After": "900"})
def note_fail(s, email, ip):
    s.add(LoginFail(email=email, ip=ip)); s.query(LoginFail).filter(LoginFail.at < dt.datetime.utcnow() - dt.timedelta(days=1)).delete(); s.commit()
def clear_fails(s, email, ip): s.query(LoginFail).filter_by(email=email, ip=ip).delete(); s.commit()
@app.post("/api/login")
def login(b: Login, request: Request, s: Session = Depends(db)):
    global DUMMY
    email, ip = b.email.strip().lower()[:190], client_ip(request); throttle(s, email, ip)
    u = s.query(User).filter_by(email=email).first()
    if DUMMY is None: DUMMY = hp("not-a-real-password")
    if not vp(b.password, u.pw if u else DUMMY) or not u: note_fail(s, email, ip); raise HTTPException(401, "Wrong email or password")
    if not u.active: raise HTTPException(403, "Account disabled. Ask your admin.")
    clear_fails(s, email, ip)
    if stale(u.pw) and not u.must_change: u.pw = hp(b.password); s.commit()  # quietly upgrade old hashes
    return {"token": make_token(u), "user": {"id": u.id, "name": u.name, "role": u.role, "must_change": bool(u.must_change)}}
@app.get("/api/admin/audit")
def audit_list(q: str = "", limit: int = 100, offset: int = 0, _: User = Depends(admin), s: Session = Depends(db)):
    qy = s.query(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id)
    if q.strip():
        k = f"%{q.strip()}%"; qy = qy.filter(or_(User.email.ilike(k), User.name.ilike(k), AuditLog.path.ilike(k)))
    total = qy.count(); rows = qy.order_by(AuditLog.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 200)).all()
    return {"total": total, "items": [{"id": a.id, "at": a.at.isoformat() + "Z", "user": u.name if u else "Deleted user", "email": u.email if u else "", "role": u.role if u else "",
                                       "method": a.method, "path": a.path, "status": a.status} for a, u in rows]}
@app.get("/api/health")
def health():
    try:
        with engine.connect() as c: c.execute(text("SELECT 1"))
    except Exception: return JSONResponse({"ok": False, "db": False}, status_code=503)
    return {"ok": True, "db": True}
@app.get("/api/me")
def whoami(u: User = Depends(me)): return {"id": u.id, "name": u.name, "role": u.role, "must_change": bool(u.must_change)}
class PwChange(BaseModel): current: str; new_password: str
@app.post("/api/me/password")
def change_password(b: PwChange, request: Request, u: User = Depends(me), s: Session = Depends(db)):
    ip = client_ip(request); throttle(s, u.email, ip)
    if not vp(b.current, u.pw): note_fail(s, u.email, ip); raise HTTPException(400, "Your current password is wrong")
    if len(b.new_password) < 8: raise HTTPException(400, "Use at least 8 characters")
    if b.new_password == b.current: raise HTTPException(400, "Choose a password different from the current one")
    if b.new_password.strip().lower() == u.email: raise HTTPException(400, "Password can't be your email")
    u.pw = hp(b.new_password); u.must_change = False; s.commit(); clear_fails(s, u.email, ip); return {"ok": True, "token": make_token(u)}

# ---- admin ----
ROLES = ("student", "faculty", "admin")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PWCHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
SEM = re.compile(r"^(?:s|sem|semester)?\s*([1-8])$", re.I)
def gen_pw(): return "".join(secrets.choice(PWCHARS) for _ in range(10))
def to_sem(v):  # 3, "3", "Semester 3", "S3" -> 3; blank -> None; anything else -> error
    if v is None or str(v).strip() == "": return None
    m = SEM.match(str(v).strip())
    if not m: raise HTTPException(400, "Semester must be a number from 1 to 8")
    return int(m.group(1))
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
def sem_no(name):  # "Semester 1", "Sem I", "S3" -> number; None if the name carries no semester number
    m = re.search(r"(?<![\w])(?:[1-8]|viii|vii|vi|iv|v|iii|ii|i)(?![\w])", name or "", re.I)
    return None if not m else (int(m.group(0)) if m.group(0).isdigit() else ROMAN[m.group(0).lower()])
def scoped(u): return u.role == "student" and u.program_id is not None  # unenrolled students keep the old open view
def sem_visible(u, sem):  # a student sees their own program, up to and including their current semester
    if not scoped(u): return True
    if sem.program_id != u.program_id: return False
    n = sem_no(sem.name)
    return u.semester is None or n is None or n <= u.semester
def check_course_access(u, course_id, s):
    if not scoped(u): return
    co = s.get(Course, course_id); sem = s.get(Semester, co.semester_id) if co and co.semester_id else None
    ok = co and co.program_id == u.program_id and (sem is None or sem_visible(u, sem))
    if not ok and co:  # or the course is shared into one of the student's visible semesters
        ok = any(sem_visible(u, x) for x in s.query(Semester).join(CourseLink, CourseLink.semester_id == Semester.id).filter(CourseLink.course_id == co.id))
    if not ok: raise HTTPException(403, "This is not part of your program or semester")
def check_topic_access(u, t, s):
    if u.role == "student" and t.published is False: raise HTTPException(404, "Topic not found")
    check_course_access(u, t.course_id, s)
def check_program(pid, s):
    if pid is not None and not s.get(Program, pid): raise HTTPException(400, "Choose a valid program")
    return pid
class NewUser(BaseModel):
    name: str; email: str; password: str; role: str = "student"; active: bool = True; program_id: int | None = None; semester: int | None = None
class UserPatch(BaseModel):
    name: str | None = None; email: str | None = None; role: str | None = None; active: bool | None = None; password: str | None = None
    program_id: int | None = None; semester: int | None = None  # send null to clear
USORT = {"name": (func.lower(User.name),), "role": (User.role, func.lower(User.name)), "program": (func.lower(func.coalesce(Program.name, "~")), User.semester, func.lower(User.name)),
         "semester": (func.coalesce(User.semester, 99), func.lower(User.name)), "newest": (User.id.desc(),)}
def urow(u, prog): return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active, "program_id": u.program_id, "program": prog, "semester": u.semester}
@app.get("/api/admin/users")
def users(q: str = "", program_id: int | None = None, semester: int | None = None, order: str = "role", limit: int = 50, offset: int = 0,
          _: User = Depends(admin), s: Session = Depends(db)):
    qs = s.query(User, Program.name).outerjoin(Program, Program.id == User.program_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"; conds = [func.lower(User.name).like(like), func.lower(User.email).like(like), func.lower(User.role).like(like), func.lower(Program.name).like(like)]
        m = SEM.match(q.strip())
        if m: conds.append(User.semester == int(m.group(1)))  # "3", "sem 3" and "semester 3" find semester-3 students
        qs = qs.filter(or_(*conds))
    if program_id is not None: qs = qs.filter(User.program_id == program_id)
    if semester is not None: qs = qs.filter(User.semester == semester)
    rows = qs.order_by(*USORT.get(order, USORT["role"]), User.id).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    return {"total": qs.count(), "items": [urow(u, pn) for u, pn in rows]}
@app.get("/api/admin/users/{uid}")
def user_detail(uid: int, _: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    prog = s.get(Program, u.program_id) if u.program_id else None
    n, reads, last = s.query(func.count(Progress.id), func.coalesce(func.sum(Progress.reads), 0), func.max(Progress.last_read)).filter(Progress.user_id == uid).one()
    recent = s.query(Topic.title, Progress.reads, Progress.last_read).join(Progress, Progress.topic_id == Topic.id).filter(Progress.user_id == uid).order_by(Progress.last_read.desc()).limit(10).all()
    return {**urow(u, prog.name if prog else None), "topics_read": n, "reads": int(reads), "last_active": (last.isoformat() + "Z") if last else None,
            "recent": [{"title": t, "reads": r, "last_read": (l.isoformat() + "Z") if l else None} for t, r, l in recent],
            "course_ids": [r.course_id for r in s.query(CourseFaculty).filter_by(user_id=uid)]}
class CoursesIn(BaseModel): course_ids: list[int]
@app.put("/api/admin/users/{uid}/courses")
def assign_courses(uid: int, b: CoursesIn, _: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if u.role != "faculty": raise HTTPException(400, "Only faculty can be assigned courses")
    want = set(b.course_ids)
    if len(want) != s.query(Course).filter(Course.id.in_(want)).count(): raise HTTPException(400, "Choose valid courses")
    s.query(CourseFaculty).filter(CourseFaculty.user_id == uid, ~CourseFaculty.course_id.in_(want or [0])).delete(synchronize_session=False)
    have = {r.course_id for r in s.query(CourseFaculty).filter_by(user_id=uid)}
    for i in want - have: s.add(CourseFaculty(user_id=uid, course_id=i))
    s.commit(); return {"ok": True}
@app.post("/api/admin/users/{uid}/reset-password")
def reset_password(uid: int, _: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    pw = gen_pw(); u.pw = hp(pw); u.must_change = True; s.commit()
    return {"email": u.email, "password": pw}  # shown once; only the hash is stored
@app.post("/api/admin/users")
def add_user(b: NewUser, _: User = Depends(admin), s: Session = Depends(db)):
    e, name = b.email.strip().lower(), b.name.strip()
    if not name: raise HTTPException(400, "Enter a name")
    if not EMAIL.match(e): raise HTTPException(400, "Enter a valid email")
    if b.role not in ROLES: raise HTTPException(400, "Role must be student, faculty or admin")
    if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
    if s.query(User).filter_by(email=e).first(): raise HTTPException(400, "That email is already registered")
    s.add(User(name=name, email=e, pw=hp(b.password), role=b.role, active=b.active, program_id=check_program(b.program_id, s), semester=to_sem(b.semester), must_change=b.role != "admin")); s.commit(); return {"ok": True}
@app.patch("/api/admin/users/{uid}")
def patch_user(uid: int, b: UserPatch, a: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if u.id == a.id and ((b.role and b.role != u.role) or (b.active is not None and b.active != u.active)):
        raise HTTPException(400, "You can't change your own role or status")
    if b.name is not None:
        if not b.name.strip(): raise HTTPException(400, "Name can't be empty")
        u.name = b.name.strip()
    if b.email is not None:
        e = b.email.strip().lower()
        if not EMAIL.match(e): raise HTTPException(400, "Enter a valid email")
        if e != u.email and s.query(User).filter_by(email=e).first(): raise HTTPException(400, "That email is already registered")
        u.email = e
    if b.role:
        if b.role not in ROLES: raise HTTPException(400, "Role must be student, faculty or admin")
        u.role = b.role
    if b.active is not None: u.active = b.active
    sent = b.dict(exclude_unset=True)
    if "program_id" in sent: u.program_id = check_program(b.program_id, s)
    if "semester" in sent: u.semester = to_sem(b.semester)
    if b.password:
        if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
        u.pw = hp(b.password); u.must_change = u.id != a.id
    s.commit(); return {"ok": True}
class UserImportIn(BaseModel): csv: str; dry_run: bool = True
UALIAS = {"full_name": "name", "student": "name", "student_name": "name", "e-mail": "email", "mail": "email", "email_address": "email", "pass": "password", "user_role": "role", "programme": "program", "sem": "semester"}
@app.post("/api/admin/users/import")
def import_users(b: UserImportIn, a: User = Depends(admin), s: Session = Depends(db)):
    text_ = b.csv.lstrip("\ufeff")
    if len(text_) > 1_000_000: raise HTTPException(400, "File is too large (limit 1 MB)")
    rd = csv.DictReader(io.StringIO(text_, newline=""), delimiter=max([",", ";", "\t"], key=text_.split("\n", 1)[0].count))
    rd.fieldnames = [UALIAS.get(h, h) for h in [(h or "").strip().lower().replace(" ", "_") for h in (rd.fieldnames or [])]]
    missing = [c for c in ("name", "email") if c not in rd.fieldnames]
    if missing: raise HTTPException(400, "Missing column(s): " + ", ".join(missing) + ". Download the template to see the format.")
    rows = list(rd)
    if len(rows) > 500: raise HTTPException(400, "Too many rows (limit 500 per file)")
    existing = {u.email: u for u in s.query(User)}; progs = {(p.name or "").strip().lower(): p for p in s.query(Program)}
    seen, errors, creds = set(), [], []; created = updated = generated = 0
    for n, row in enumerate(rows, start=2):
        v = {k: (row.get(k) or "").strip() for k in rd.fieldnames if k}
        if not any(v.values()): continue
        e = v.get("email", "").lower(); role = v.get("role", "").lower() or None; pw = v.get("password", "")
        def bad(msg): errors.append({"row": n, "error": msg})
        if not EMAIL.match(e): bad("Invalid email"); continue
        if e in seen: bad("Duplicate email in this file"); continue
        if role and role not in ROLES: bad("Role must be student, faculty or admin"); continue
        if pw and len(pw) < 8: bad("Password needs 8+ characters"); continue
        name = v.get("name") or e.split("@")[0]
        if len(name) > 100 or len(e) > 190: bad("Name or email is too long"); continue
        prog = progs.get(v.get("program", "").lower()) if v.get("program") else None
        if v.get("program") and not prog: bad("Unknown program '" + v["program"][:40] + "'. Names must match the Programs tab"); continue
        try: sem = to_sem(v.get("semester"))
        except HTTPException: bad("Semester must be a number from 1 to 8"); continue
        seen.add(e); u = existing.get(e)
        if u:
            if u.id == a.id and role and role != u.role: bad("You can't change your own role"); continue
            if v.get("name"): u.name = name
            if role: u.role = role
            if prog: u.program_id = prog.id  # blank program/semester cells leave the current value alone
            if sem: u.semester = sem
            if pw and not b.dry_run: u.pw = hp(pw, TEMP_ITER); u.must_change = u.id != a.id
            updated += 1
        else:
            created += 1; generated += not pw
            if not b.dry_run:
                final = pw or gen_pw()
                s.add(User(name=name, email=e, pw=hp(final, TEMP_ITER), role=role or "student", program_id=prog.id if prog else None, semester=sem, must_change=(role or "student") != "admin"))
                if not pw: creds.append({"name": name, "email": e, "password": final})
    s.rollback() if b.dry_run else s.commit()
    return {"dry_run": b.dry_run, "rows": len(rows), "valid_rows": created + updated, "created": created, "updated": updated, "generated": generated,
            "error_count": len(errors), "errors": errors[:20], "credentials": creds}
PSORT = {"name": lambda stu: (func.lower(Program.name),), "newest": lambda stu: (Program.id.desc(),), "students": lambda stu: (stu.desc(), func.lower(Program.name))}
def nat(name): return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name or "")]  # "Semester 2" before "Semester 10"
def counts(s, ids):
    """Per program: semesters, courses, units, topics, students."""
    c = {i: dict(semesters=0, courses=0, units=0, topics=0, students=0) for i in ids}
    if not ids: return c
    for pid, n in s.query(Semester.program_id, func.count(Semester.id)).filter(Semester.program_id.in_(ids)).group_by(Semester.program_id): c[pid]["semesters"] = n
    for pid, n in s.query(Course.program_id, func.count(Course.id)).filter(Course.program_id.in_(ids)).group_by(Course.program_id): c[pid]["courses"] = n
    for pid, n in s.query(Course.program_id, func.count(Unit.id)).join(Unit, Unit.course_id == Course.id).filter(Course.program_id.in_(ids)).group_by(Course.program_id): c[pid]["units"] = n
    for pid, n in s.query(Course.program_id, func.count(Topic.id)).join(Topic, Topic.course_id == Course.id).filter(Course.program_id.in_(ids)).group_by(Course.program_id): c[pid]["topics"] = n
    for pid, n in s.query(User.program_id, func.count(User.id)).filter(User.program_id.in_(ids)).group_by(User.program_id): c[pid]["students"] = n
    return c
@app.get("/api/admin/programs")
def admin_programs(q: str = "", order: str = "name", limit: int = 50, offset: int = 0, _: User = Depends(admin), s: Session = Depends(db)):
    stu = s.query(func.count(User.id)).filter(User.program_id == Program.id).correlate(Program).scalar_subquery()
    qs = s.query(Program)
    if q.strip():
        like = f"%{q.strip().lower()}%"  # matches the program name, or any of its semester or course names
        qs = qs.filter(or_(func.lower(Program.name).like(like),
            Program.id.in_(s.query(Semester.program_id).filter(func.lower(Semester.name).like(like))),
            Program.id.in_(s.query(Course.program_id).filter(func.lower(Course.name).like(like)))))
    rows = qs.order_by(*PSORT.get(order, PSORT["name"])(stu), Program.id).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    c = counts(s, [p.id for p in rows])
    return {"total": qs.count(), "items": [{"id": p.id, "name": p.name, **c[p.id]} for p in rows]}
@app.get("/api/admin/programs/{pid}")
def admin_program(pid: int, _: User = Depends(admin), s: Session = Depends(db)):
    p = s.get(Program, pid)
    if not p: raise HTTPException(404, "No such program")
    sems = sorted(s.query(Semester).filter_by(program_id=pid).all(), key=lambda x: nat(x.name))
    cc = dict(s.query(Course.semester_id, func.count(Course.id)).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    tc = dict(s.query(Course.semester_id, func.count(Topic.id)).join(Topic, Topic.course_id == Course.id).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    studs = s.query(User).filter_by(program_id=pid).order_by(func.coalesce(User.semester, 99), func.lower(User.name)).limit(50).all()
    return {"id": p.id, "name": p.name, **counts(s, [pid])[pid],
            "semester_list": [{"id": x.id, "name": x.name, "courses": cc.get(x.id, 0), "topics": tc.get(x.id, 0)} for x in sems],
            "student_list": [{"id": u.id, "name": u.name, "semester": u.semester, "active": u.active} for u in studs]}
class Cfg(BaseModel): deepseek_key: str | None = None; model: str | None = None
@app.get("/api/admin/settings")
def get_cfg(_: User = Depends(admin), s: Session = Depends(db)):
    k = setting(s, "deepseek_key")
    return {"key_set": bool(k), "key_hint": ("…" + k[-4:]) if k else "", "model": setting(s, "model", "deepseek-chat")}
@app.put("/api/admin/settings")
def put_cfg(b: Cfg, _: User = Depends(admin), s: Session = Depends(db)):
    for k, v in (("deepseek_key", b.deepseek_key), ("model", b.model)):
        if v: s.merge(Setting(k=k, v=v.strip()))
    s.commit(); return {"ok": True}
@app.get("/api/admin/stats")
def stats(_: User = Depends(admin), s: Session = Depends(db)):
    saved = s.query(func.coalesce(func.sum(AICache.hits * AICache.tokens), 0)).scalar()
    return {"students": s.query(User).filter_by(role="student").count(), "topics": s.query(Topic).count(),
            "cached": s.query(AICache).count(), "tokens_saved": int(saved)}

@app.get("/api/admin/reports")
def reports(_: User = Depends(admin), s: Session = Depends(db)):
    top = s.query(Topic.title, func.count(Progress.id), func.coalesce(func.sum(Progress.reads), 0)).join(Progress, Progress.topic_id == Topic.id) \
        .group_by(Topic.id, Topic.title).order_by(func.sum(Progress.reads).desc()).limit(10).all()
    studs = s.query(User.name, User.email, User.active, func.count(Progress.id), func.max(Progress.last_read)).outerjoin(Progress, Progress.user_id == User.id) \
        .filter(User.role == "student").group_by(User.id, User.name, User.email, User.active).order_by(func.max(Progress.last_read).desc()).all()
    ai = s.query(Topic.title, AICache.kind, AICache.hits, AICache.tokens).join(AICache, AICache.topic_id == Topic.id) \
        .order_by((AICache.hits * AICache.tokens).desc()).limit(10).all()
    return {"top_topics": [{"title": t, "readers": r, "reads": int(n)} for t, r, n in top],
            "students": [{"name": n, "email": e, "active": a, "topics_read": c, "last_active": (l.isoformat() + "Z") if l else None} for n, e, a, c, l in studs],
            "ai": [{"title": t, "kind": k, "hits": h or 0, "tokens": tk or 0, "saved": (h or 0) * (tk or 0)} for t, k, h, tk in ai]}

# ---- course reports (admins see every course; faculty see only their own) ----
def csv_cell(v): v = "" if v is None else v; return "'" + v if isinstance(v, str) and v[:1] in "=+-@\t\r" else v  # stops spreadsheet formula injection
def csv_response(name, header, rows):
    out = io.StringIO(); w = csv.writer(out); w.writerow(header); [w.writerow([csv_cell(c) for c in r]) for r in rows]
    return Response("\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})
def course_audience(c, students, sems, links):  # students who can see this course in their own list
    places = [sems.get(i) for i in [c.semester_id] + links.get(c.id, []) if sems.get(i)]
    def sees(u):
        if u.program_id is None: return False
        if not places: return c.program_id == u.program_id
        return any(x.program_id == u.program_id and (u.semester is None or sem_no(x.name) is None or sem_no(x.name) <= u.semester) for x in places)
    return [u for u in students if sees(u)]
def course_stats(c, aud, s):
    ids = {u.id for u in aud}; tids = [t.id for t in s.query(Topic.id).filter(Topic.course_id == c.id, Topic.published.isnot(False))]
    reads, last = defaultdict(int), {}
    if tids and ids:
        for uid, n, l in s.query(Progress.user_id, func.count(Progress.id), func.max(Progress.last_read)).filter(Progress.topic_id.in_(tids), Progress.user_id.in_(ids)).group_by(Progress.user_id).all(): reads[uid], last[uid] = n, l
    qids = [q.id for q in s.query(Quiz.id).filter(Quiz.course_id == c.id, Quiz.published == True)]  # noqa: E712
    bests = defaultdict(dict)
    if qids and ids:
        for qid, uid, b in s.query(Attempt.quiz_id, Attempt.user_id, func.max(Attempt.percent)).filter(Attempt.quiz_id.in_(qids), Attempt.user_id.in_(ids)).group_by(Attempt.quiz_id, Attempt.user_id).all(): bests[uid][qid] = b
    return tids, reads, last, qids, bests
def my_courses(u, s):
    q = s.query(Course)
    if u.role == "faculty": q = q.filter(Course.id.in_([r.course_id for r in s.query(CourseFaculty).filter_by(user_id=u.id)] or [0]))
    return q.order_by(Course.id).all()
@app.get("/api/reports/courses")
def report_courses(program_id: int = 0, semester: int = 0, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    students = s.query(User).filter_by(role="student", active=True).all(); sems = {x.id: x for x in s.query(Semester)}; pn = {p.id: p.name for p in s.query(Program)}
    links = defaultdict(list)
    for l in s.query(CourseLink): links[l.course_id].append(l.semester_id)
    out = []
    for c in my_courses(u, s):
        sm = sems.get(c.semester_id)
        if program_id and c.program_id != program_id: continue
        if semester and (not sm or sem_no(sm.name) != semester): continue
        aud = course_audience(c, students, sems, links); tids, reads, last, qids, bests = course_stats(c, aud, s)
        comp = [100 * reads[x.id] / len(tids) for x in aud] if tids else []; qb = [b for x in aud for b in bests[x.id].values()]
        out.append({"course_id": c.id, "course": c.name, "program": pn.get(c.program_id, ""), "semester": sm.name if sm else "", "students": len(aud), "topics": len(tids),
                    "avg_completion": round(sum(comp) / len(comp)) if comp else 0, "quizzes": len(qids), "quiz_attempts": s.query(func.count(Attempt.id)).filter(Attempt.quiz_id.in_(qids or [0])).scalar(),
                    "avg_quiz_percent": round(sum(qb) / len(qb)) if qb else None})
    if format == "csv": return csv_response("courses.csv", ["Program", "Semester", "Course", "Students", "Topics", "Average completion %", "Quizzes", "Quiz attempts", "Average best quiz %"],
                                           [[r["program"], r["semester"], r["course"], r["students"], r["topics"], r["avg_completion"], r["quizzes"], r["quiz_attempts"], r["avg_quiz_percent"]] for r in out])
    return out
@app.get("/api/reports/courses/{cid}/students")
def report_students(cid: int, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    students = s.query(User).filter_by(role="student").all(); sems = {x.id: x for x in s.query(Semester)}; pn = {p.id: p.name for p in s.query(Program)}
    links = defaultdict(list)
    for l in s.query(CourseLink).filter_by(course_id=cid): links[cid].append(l.semester_id)
    aud = course_audience(c, students, sems, links); tids, reads, last, qids, bests = course_stats(c, aud, s)
    rows = [{"name": x.name, "email": x.email, "program": pn.get(x.program_id, ""), "semester": x.semester, "active": bool(x.active), "topics_read": reads[x.id], "topics": len(tids),
             "completion": round(100 * reads[x.id] / len(tids)) if tids else 0, "quizzes_taken": len(bests[x.id]), "quizzes": len(qids),
             "avg_quiz_percent": round(sum(bests[x.id].values()) / len(bests[x.id])) if bests[x.id] else None, "last_active": (last[x.id].isoformat() + "Z") if last.get(x.id) else None}
            for x in sorted(aud, key=lambda x: (x.name or "").lower())]
    if format == "csv": return csv_response(f"students-{c.name}.csv".replace(" ", "_"), ["Name", "Email", "Program", "Semester", "Active", "Topics read", "Topics", "Completion %", "Quizzes taken", "Quizzes", "Average best quiz %", "Last active"],
                                           [[r["name"], r["email"], r["program"], r["semester"], "yes" if r["active"] else "no", r["topics_read"], r["topics"], r["completion"], r["quizzes_taken"], r["quizzes"], r["avg_quiz_percent"], r["last_active"]] for r in rows])
    return {"course": c.name, "students": rows}

# ---- content: admin writes, everyone reads ----
class ProgramIn(BaseModel): name: str
class SemesterIn(BaseModel): name: str; program_id: int
class CourseIn(BaseModel): name: str; semester_id: int
class UnitIn(BaseModel): name: str; course_id: int
class TopicIn(BaseModel):
    title: str; unit_id: int; content: str = ""; sample_content: str = ""; question_pattern: str = ""; guideline: str = ""; published: bool = True
M = {"programs": Program, "semesters": Semester, "courses": Course, "units": Unit, "topics": Topic}
@app.get("/api/tree")
def tree(u: User = Depends(me), s: Session = Depends(db)):
    read = {p.topic_id for p in s.query(Progress).filter_by(user_id=u.id)}
    marked = {b.topic_id for b in s.query(Bookmark).filter_by(user_id=u.id)}
    def g(model, k):
        d = defaultdict(list)
        for r in s.query(model).order_by(model.id): d[getattr(r, k)].append(r)
        return d
    tp, un, co, se = g(Topic, "unit_id"), g(Unit, "course_id"), g(Course, "semester_id"), g(Semester, "program_id")
    progs = [p for p in s.query(Program).order_by(Program.id) if not scoped(u) or p.id == u.program_id]
    pname = {p.id: p.name for p in s.query(Program)}; sname = {x.id: f"{pname.get(x.program_id, '')} › {x.name}" for x in s.query(Semester)}
    links = defaultdict(list); linked_to = defaultdict(list)
    for l in s.query(CourseLink): linked_to[l.course_id].append(l.semester_id)
    qcount = dict(s.query(Question.quiz_id, func.count(Question.id)).group_by(Question.quiz_id).all())
    best = dict(s.query(Attempt.quiz_id, func.max(Attempt.percent)).filter(Attempt.user_id == u.id).group_by(Attempt.quiz_id).all())
    qz = defaultdict(list)
    for q in s.query(Quiz).order_by(Quiz.id):
        if u.role != "student" or (q.published and qcount.get(q.id)):
            qz[q.unit_id].append({"id": q.id, "title": q.title, "published": bool(q.published), "questions": qcount.get(q.id, 0), "best": best.get(q.id), "pass_percent": q.pass_percent})
    cbyid = {c.id: c for c in s.query(Course)}
    mine = {r.course_id for r in s.query(CourseFaculty).filter_by(user_id=u.id)} if u.role == "faculty" else set()
    for l in s.query(CourseLink).order_by(CourseLink.id):
        if l.course_id in cbyid: links[l.semester_id].append(cbyid[l.course_id])
    def cj(c, sm):
        shared = c.semester_id != sm.id
        d = {"id": c.id, "name": c.name, "shared": shared, "semester_id": c.semester_id, "home": sname.get(c.semester_id, "") if shared else "",
             "shared_with": len(linked_to[c.id]), "editable": u.role == "admin" or c.id in mine, "units": [
            {"id": n.id, "name": n.name, "quizzes": qz[n.id], "topics": [{"id": t.id, "title": t.title, "read": t.id in read, "bookmarked": t.id in marked, "published": t.published is not False} for t in tp[n.id] if t.published is not False or u.role != "student"]} for n in un[c.id]]}
        if u.role == "admin": d["link_ids"] = linked_to[c.id]
        return d
    return [{"id": p.id, "name": p.name, "semesters": [{"id": sm.id, "name": sm.name, "current": scoped(u) and u.semester is not None and sem_no(sm.name) == u.semester,
        "courses": [cj(c, sm) for c in co[sm.id] + links[sm.id]]} for sm in se[p.id] if sem_visible(u, sm)]} for p in progs]
class PublishIn(BaseModel): published: bool
@app.put("/api/topics/{rid}/publish")
def publish_topic(rid: int, b: PublishIn, u: User = Depends(staff), s: Session = Depends(db)):
    t = s.get(Topic, rid)
    if not t: raise HTTPException(404, "Not found")
    need_edit(u, t.course_id, s); t.published = b.published; s.commit(); return {"ok": True, "changed": 1}
@app.put("/api/units/{rid}/publish")
def publish_unit(rid: int, b: PublishIn, u: User = Depends(staff), s: Session = Depends(db)):
    un = s.get(Unit, rid)
    if not un: raise HTTPException(404, "Not found")
    need_edit(u, un.course_id, s)
    n = s.query(Topic).filter(Topic.unit_id == rid, Topic.published != b.published).update({"published": b.published}, synchronize_session=False)
    s.commit(); return {"ok": True, "changed": n}
class LinksIn(BaseModel): semester_ids: list[int]
@app.put("/api/courses/{cid}/links")
def set_links(cid: int, b: LinksIn, _: User = Depends(admin), s: Session = Depends(db)):
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    want = {i for i in b.semester_ids if i != c.semester_id}
    if len(want) != len(s.query(Semester).filter(Semester.id.in_(want)).all()): raise HTTPException(400, "Choose valid semesters")
    s.query(CourseLink).filter(CourseLink.course_id == cid, ~CourseLink.semester_id.in_(want or [0])).delete(synchronize_session=False)
    have = {l.semester_id for l in s.query(CourseLink).filter_by(course_id=cid)}
    for i in want - have: s.add(CourseLink(course_id=cid, semester_id=i))
    s.commit(); return {"ok": True}
def save_row(row, u, s): row.owner_id = u.id; s.add(row); s.commit(); return {"id": row.id}
def course_fields(b, s):
    sem = s.get(Semester, b.semester_id)
    if not sem: raise HTTPException(400, "Choose a semester for this course")
    return {"name": b.name, "semester_id": sem.id, "program_id": sem.program_id}
def topic_fields(b, s):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this topic")
    return {**b.dict(), "course_id": un.course_id}
def update(row, vals, s):
    if not row: raise HTTPException(404, "Not found")
    for k, v in vals.items(): setattr(row, k, v)
    s.commit(); return {"ok": True}
def program_name(name, s, keep=None):  # names must be unique: the users CSV import finds programs by name
    n = (name or "").strip()
    if not n: raise HTTPException(400, "Enter a program name")
    if len(n) > 150: raise HTTPException(400, "Program name is too long")
    dup = s.query(Program).filter(func.lower(Program.name) == n.lower(), Program.id != (keep or 0)).first()
    if dup: raise HTTPException(400, "A program with that name already exists")
    return n
@app.post("/api/programs")
def new_program(b: ProgramIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Program(name=program_name(b.name, s)), u, s)
@app.post("/api/semesters")
def new_semester(b: SemesterIn, u: User = Depends(admin), s: Session = Depends(db)):
    if not s.get(Program, b.program_id): raise HTTPException(400, "Choose a program for this semester")
    return save_row(Semester(**b.dict()), u, s)
@app.post("/api/courses")
def new_course(b: CourseIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Course(**course_fields(b, s)), u, s)
@app.post("/api/units")
def new_unit(b: UnitIn, u: User = Depends(staff), s: Session = Depends(db)):
    if not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course for this unit")
    need_edit(u, b.course_id, s)
    return save_row(Unit(**b.dict()), u, s)
@app.post("/api/topics")
def new_topic(b: TopicIn, u: User = Depends(staff), s: Session = Depends(db)):
    f = topic_fields(b, s); need_edit(u, f["course_id"], s); return save_row(Topic(**f), u, s)
@app.put("/api/programs/{rid}")
def edit_program(rid: int, b: ProgramIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Program, rid), {"name": program_name(b.name, s, rid)}, s)
@app.put("/api/semesters/{rid}")
def edit_semester(rid: int, b: SemesterIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Semester, rid), b.dict(), s)
@app.put("/api/courses/{rid}")
def edit_course(rid: int, b: CourseIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Course, rid), course_fields(b, s), s)
@app.put("/api/units/{rid}")
def edit_unit(rid: int, b: UnitIn, u: User = Depends(staff), s: Session = Depends(db)):
    x = s.get(Unit, rid)
    if x: need_edit(u, x.course_id, s)
    need_edit(u, b.course_id, s)
    if x: s.query(Quiz).filter_by(unit_id=rid).update({"course_id": b.course_id})
    return update(x, b.dict(), s)
@app.put("/api/topics/{rid}")
def edit_topic(rid: int, b: TopicIn, u: User = Depends(staff), s: Session = Depends(db)):
    x = s.get(Topic, rid)
    if x: need_edit(u, x.course_id, s)
    f = topic_fields(b, s); need_edit(u, f["course_id"], s); return update(x, f, s)
# ---- quizzes: staff write them, students take them and are graded on the server ----
class QuizIn(BaseModel): unit_id: int = 0; title: str; pass_percent: int = 50; published: bool = False
class QuestionIn(BaseModel): text: str; options: list[str]; correct: int; explanation: str = ""
class QuestionsIn(BaseModel): questions: list[QuestionIn]
class AttemptIn(BaseModel): answers: list[int | None]
def quiz_or_404(qid, s):
    q = s.get(Quiz, qid)
    if not q: raise HTTPException(404, "Quiz not found")
    return q
def quiz_fields(b):
    if not b.title.strip(): raise HTTPException(400, "Give the quiz a title")
    if not 1 <= b.pass_percent <= 100: raise HTTPException(400, "Pass mark must be between 1 and 100")
    return {"title": b.title.strip()[:200], "pass_percent": b.pass_percent, "published": b.published}
@app.post("/api/quizzes")
def new_quiz(b: QuizIn, u: User = Depends(staff), s: Session = Depends(db)):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this quiz")
    need_edit(u, un.course_id, s); q = Quiz(unit_id=un.id, course_id=un.course_id, **quiz_fields(b)); s.add(q); s.commit(); return {"id": q.id}
@app.put("/api/quizzes/{qid}")
def edit_quiz(qid: int, b: QuizIn, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, q.course_id, s)
    for k, v in quiz_fields(b).items(): setattr(q, k, v)
    s.commit(); return {"ok": True}
@app.delete("/api/quizzes/{qid}")
def delete_quiz(qid: int, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, q.course_id, s); drop_quizzes(s, Quiz.id == qid); s.commit(); return {"ok": True}
@app.put("/api/quizzes/{qid}/questions")
def set_questions(qid: int, b: QuestionsIn, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, q.course_id, s)
    if len(b.questions) > 100: raise HTTPException(400, "A quiz can have up to 100 questions")
    for i, x in enumerate(b.questions, 1):
        opts = [o.strip() for o in x.options]
        if not x.text.strip(): raise HTTPException(400, f"Question {i} has no text")
        if not 2 <= len(opts) <= 6 or not all(opts): raise HTTPException(400, f"Question {i} needs 2 to 6 answers, none empty")
        if not 0 <= x.correct < len(opts): raise HTTPException(400, f"Question {i}: mark which answer is correct")
    s.query(Question).filter_by(quiz_id=qid).delete()
    for i, x in enumerate(b.questions):
        s.add(Question(quiz_id=qid, pos=i, text=x.text.strip(), options=json.dumps([o.strip() for o in x.options]), correct=x.correct, explanation=x.explanation.strip()))
    s.commit(); return {"ok": True, "count": len(b.questions)}
@app.get("/api/quizzes/{qid}")
def get_quiz(qid: int, u: User = Depends(me), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); staff_view = u.role == "admin" or (u.role == "faculty" and can_edit(u, q.course_id, s))
    if not staff_view:
        if not q.published: raise HTTPException(404, "Quiz not found")
        check_course_access(u, q.course_id, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    mine = s.query(Attempt).filter_by(quiz_id=qid, user_id=u.id).all()
    return {"id": q.id, "title": q.title, "pass_percent": q.pass_percent, "published": bool(q.published), "unit_id": q.unit_id, "can_edit": staff_view,
            "questions": [{"id": x.id, "text": x.text, "options": json.loads(x.options), **({"correct": x.correct, "explanation": x.explanation} if staff_view else {})} for x in qs],
            "attempts": len(mine), "best": max([a.percent for a in mine], default=None)}
@app.post("/api/quizzes/{qid}/attempt")
def attempt_quiz(qid: int, b: AttemptIn, u: User = Depends(me), s: Session = Depends(db)):
    q = quiz_or_404(qid, s)
    if not q.published and not (u.role == "admin" or can_edit(u, q.course_id, s)): raise HTTPException(404, "Quiz not found")
    check_course_access(u, q.course_id, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    if not qs: raise HTTPException(400, "This quiz has no questions yet")
    if len(b.answers) != len(qs): raise HTTPException(400, "Answer every question or leave it blank")
    results = [{"chosen": a, "correct": x.correct, "ok": a == x.correct, "explanation": x.explanation} for a, x in zip(b.answers, qs)]
    score = sum(r["ok"] for r in results); pct = round(100 * score / len(qs))
    s.add(Attempt(quiz_id=qid, user_id=u.id, score=score, total=len(qs), percent=pct)); s.commit()
    return {"score": score, "total": len(qs), "percent": pct, "passed": pct >= q.pass_percent, "pass_percent": q.pass_percent, "results": results}

def drop_quizzes(s, cond):
    ids = [q.id for q in s.query(Quiz).filter(cond)]
    if ids:
        for m in (Attempt, Question): s.query(m).filter(m.quiz_id.in_(ids)).delete(synchronize_session=False)
        s.query(Quiz).filter(Quiz.id.in_(ids)).delete(synchronize_session=False)
@app.delete("/api/{kind}/{rid}")
def remove(kind: str, rid: int, u: User = Depends(staff), s: Session = Depends(db)):
    if kind not in M: raise HTTPException(404, "Unknown item")
    r = s.get(M[kind], rid)
    if not r: raise HTTPException(404, "Not found")
    if kind not in ("units", "topics"): 
        if u.role != "admin": raise HTTPException(403, "Admins only")
    else: need_edit(u, r.course_id, s)
    def drop_course(c): drop_quizzes(s, Quiz.course_id == c.id); s.query(CourseLink).filter_by(course_id=c.id).delete(); s.query(CourseFaculty).filter_by(course_id=c.id).delete(); s.query(Topic).filter_by(course_id=c.id).delete(); s.query(Unit).filter_by(course_id=c.id).delete(); s.delete(c)
    if kind == "programs":
        for c in s.query(Course).filter_by(program_id=rid).all(): drop_course(c)
        s.query(CourseLink).filter(CourseLink.semester_id.in_(s.query(Semester.id).filter_by(program_id=rid))).delete(synchronize_session=False)
        s.query(Semester).filter_by(program_id=rid).delete()
        s.query(User).filter_by(program_id=rid).update({"program_id": None})
    if kind == "semesters":
        s.query(CourseLink).filter_by(semester_id=rid).delete()
        for c in s.query(Course).filter_by(semester_id=rid).all(): drop_course(c)
    if kind == "courses": drop_course(r); r = None
    if kind == "units": drop_quizzes(s, Quiz.unit_id == rid); s.query(Topic).filter_by(unit_id=rid).delete()
    if r is not None: s.delete(r)
    s.commit(); return {"ok": True}

# ---- CSV import (admin) ----
LEVELS = ["program", "semester", "course", "unit"]
TEXT_COLS = ["content", "question_pattern", "sample_content", "guideline"]
ALIAS = {"title": "topic", "topic_title": "topic", "notes": "content", "topic_content": "content", "answer_guideline": "guideline",
         "sample": "sample_content", "pattern": "question_pattern"}
class ImportIn(BaseModel): csv: str; dry_run: bool = True
@app.post("/api/admin/import")
def import_csv(b: ImportIn, a: User = Depends(admin), s: Session = Depends(db)):
    text_ = b.csv.lstrip("\ufeff")
    if len(text_) > 5_000_000: raise HTTPException(400, "File is too large (limit 5 MB)")
    head = text_.split("\n", 1)[0]
    rd = csv.DictReader(io.StringIO(text_, newline=""), delimiter=max([",", ";", "\t"], key=head.count))
    rd.fieldnames = [ALIAS.get(h, h) for h in [(h or "").strip().lower().replace(" ", "_") for h in (rd.fieldnames or [])]]
    missing = [c for c in LEVELS + ["topic"] if c not in rd.fieldnames]
    if missing: raise HTTPException(400, "Missing column(s): " + ", ".join(missing) + ". Download the template to see the format.")
    rows = list(rd)
    if len(rows) > 5000: raise HTTPException(400, "Too many rows (limit 5000 per file)")
    cache = {"program": {(x.name or "").lower(): x for x in s.query(Program)},
             "semester": {(x.program_id, (x.name or "").lower()): x for x in s.query(Semester)},
             "course": {(x.semester_id, (x.name or "").lower()): x for x in s.query(Course)},
             "unit": {(x.course_id, (x.name or "").lower()): x for x in s.query(Unit)},
             "topic": {(x.unit_id, (x.title or "").lower()): x for x in s.query(Topic)}}
    made = {k + "s": 0 for k in cache}; updated = valid = 0; errors = []; carry = {}
    def get(kind, key, make):
        if key not in cache[kind]:
            o = make(); o.owner_id = a.id; s.add(o); s.flush(); cache[kind][key] = o; made[kind + "s"] += 1
        return cache[kind][key]
    try:
        for n, row in enumerate(rows, start=2):
            v = {k: (row.get(k) or "").strip() for k in rd.fieldnames if k}
            if not any(v.values()): continue
            for i, lv in enumerate(LEVELS):  # blank program/semester/course/unit cells repeat the row above
                if v[lv]:
                    if v[lv] != carry.get(lv):
                        for x in LEVELS[i + 1:]: carry.pop(x, None)
                    carry[lv] = v[lv]
                else: v[lv] = carry.get(lv, "")
            gaps = [c for c in LEVELS + ["topic"] if not v[c]]
            if gaps: errors.append({"row": n, "error": "Missing " + ", ".join(gaps)}); continue
            if any(len(v[c]) > 150 for c in LEVELS) or len(v["topic"]) > 200:
                errors.append({"row": n, "error": "A name is too long (150 characters, topics 200)"}); continue
            p = get("program", v["program"].lower(), lambda: Program(name=v["program"]))
            sm = get("semester", (p.id, v["semester"].lower()), lambda: Semester(name=v["semester"], program_id=p.id))
            co = get("course", (sm.id, v["course"].lower()), lambda: Course(name=v["course"], semester_id=sm.id, program_id=p.id))
            un = get("unit", (co.id, v["unit"].lower()), lambda: Unit(name=v["unit"], course_id=co.id))
            vals = {k: v[k] for k in TEXT_COLS if v.get(k)}
            t = cache["topic"].get((un.id, v["topic"].lower()))
            if t:
                for k, val in vals.items(): setattr(t, k, val)
                updated += bool(vals)
            else:
                get("topic", (un.id, v["topic"].lower()), lambda: Topic(title=v["topic"], unit_id=un.id, course_id=co.id, **vals))
            valid += 1
        s.rollback() if b.dry_run else s.commit()
    except Exception:
        s.rollback(); raise HTTPException(500, "Import failed. Nothing was saved.")
    return {"dry_run": b.dry_run, "rows": len(rows), "valid_rows": valid, "created": made, "updated_topics": updated,
            "error_count": len(errors), "errors": errors[:20]}

def full(t, s):
    co = s.get(Course, t.course_id); sem = s.get(Semester, co.semester_id) if co.semester_id else None
    un = s.get(Unit, t.unit_id) if t.unit_id else None
    return {"id": t.id, "title": t.title, "course_id": t.course_id, "unit_id": t.unit_id, "unit": un.name if un else "", "course": co.name,
            "semester": sem.name if sem else "", "program": s.get(Program, co.program_id).name,
            "content": t.content, "sample_content": t.sample_content, "question_pattern": t.question_pattern, "guideline": t.guideline, "published": t.published is not False}
@app.get("/api/topics/{tid}")
def topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    return {**full(t, s), "bookmarked": s.query(Bookmark).filter_by(user_id=u.id, topic_id=tid).first() is not None}
@app.put("/api/topics/{tid}/bookmark")
def add_bookmark(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    if not s.query(Bookmark).filter_by(user_id=u.id, topic_id=tid).first():
        s.add(Bookmark(user_id=u.id, topic_id=tid))
        try: s.commit()
        except Exception: s.rollback()  # a double tap raced us; it is bookmarked either way
    return {"bookmarked": True}
@app.delete("/api/topics/{tid}/bookmark")
def remove_bookmark(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    s.query(Bookmark).filter_by(user_id=u.id, topic_id=tid).delete(); s.commit()
    return {"bookmarked": False}
@app.post("/api/topics/{tid}/read")
def read(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    p = s.query(Progress).filter_by(user_id=u.id, topic_id=tid).first()
    if p: p.reads += 1; p.last_read = dt.datetime.utcnow()
    else: s.add(Progress(user_id=u.id, topic_id=tid))
    s.commit()
    known = [x.title for x in s.query(Topic).join(Progress, Progress.topic_id == Topic.id)
             .filter(Progress.user_id == u.id, Topic.course_id == t.course_id, Topic.id != tid).limit(8)]
    n = s.query(Progress).filter_by(user_id=u.id).count()
    return {"known": known, "topics_read": n}

PROMPTS = {
 "explain": ("You are a warm, sharp engineering tutor for a teenage student. Explain the topic clearly with a hook, an everyday analogy, "
             "the core idea step by step, one worked example, and 3 quick recap bullets. Use Markdown, be concise, stay accurate."),
 "answer": ("You are an engineering exam coach. Write a model answer that follows the given answer guideline and question pattern exactly "
            "(structure, length, marks split, diagrams to sketch, keywords). Use Markdown. Mirror the style of the sample content."),
}
@app.get("/api/topics/{tid}/ai/{kind}")
async def ai(tid: int, kind: str, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t or kind not in PROMPTS: raise HTTPException(404, "Not found")
    check_topic_access(u, t, s)
    f = full(t, s)
    ch = hashlib.sha256("|".join([kind, t.title, t.content or "", t.sample_content or "", t.question_pattern or "", t.guideline or ""]).encode()).hexdigest()
    hit = s.query(AICache).filter_by(topic_id=tid, kind=kind, chash=ch).first()
    if hit: hit.hits += 1; s.commit(); return {"text": hit.text, "cached": True}
    key = setting(s, "deepseek_key")
    if not key: raise HTTPException(503, "AI isn't set up yet. Ask your admin to add the DeepSeek key.")
    msg = f"Program: {f['program']}\nSemester: {f['semester']}\nCourse: {f['course']}\nUnit: {f['unit']}\nTopic: {f['title']}\n\nTopic content:\n{f['content']}\n\n" + (
        "" if kind == "explain" else f"Question pattern:\n{f['question_pattern']}\n\nAnswer guideline:\n{f['guideline']}\n\nSample content:\n{f['sample_content']}\n")
    try:
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {key}"},
                json={"model": setting(s, "model", "deepseek-chat"), "messages": [{"role": "system", "content": PROMPTS[kind]}, {"role": "user", "content": msg}]})
        r.raise_for_status(); j = r.json()
    except Exception: raise HTTPException(502, "DeepSeek didn't respond. Check the API key and try again.")
    text = j["choices"][0]["message"]["content"]
    try: s.add(AICache(topic_id=tid, kind=kind, chash=ch, text=text, tokens=j.get("usage", {}).get("total_tokens", 0))); s.commit()
    except Exception: s.rollback()
    return {"text": text, "cached": False}

UPLOADS = os.path.abspath(os.getenv("UPLOAD_DIR") or os.path.join(os.path.dirname(__file__), "uploads"))
MAX_IMG = 3 * 1024 * 1024
def sniff(b):  # trust the bytes, not the file name or the browser's content type
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if b[:3] == b"\xff\xd8\xff": return "jpg"
    if b[:6] in (b"GIF87a", b"GIF89a"): return "gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "webp"
MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
@app.post("/api/uploads")
async def upload_image(request: Request, _: User = Depends(staff)):
    if int(request.headers.get("content-length") or 0) > MAX_IMG: raise HTTPException(413, "Image is too large. Keep it under 3 MB.")
    b = await request.body()
    if len(b) > MAX_IMG: raise HTTPException(413, "Image is too large. Keep it under 3 MB.")
    ext = sniff(b)
    if not ext: raise HTTPException(400, "Use a PNG, JPG, GIF or WebP image")
    os.makedirs(UPLOADS, exist_ok=True)
    name = f"{os.urandom(16).hex()}.{ext}"
    with open(os.path.join(UPLOADS, name), "wb") as f: f.write(b)
    return {"url": f"/api/uploads/{name}"}
@app.get("/api/uploads/{name}")  # public on purpose: <img> tags can't send a login token; names are random
def get_image(name: str):
    m = re.fullmatch(r"[0-9a-f]{32}\.(png|jpg|gif|webp)", name)
    path = os.path.join(UPLOADS, name)
    if not m or not os.path.isfile(path): raise HTTPException(404, "Not found")
    return FileResponse(path, media_type=MIME[m.group(1)], headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})
dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(dist): app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
