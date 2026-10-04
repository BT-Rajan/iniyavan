from collections import defaultdict
import base64, csv, io, json, logging, os, re, smtplib, hashlib, hmac, secrets, datetime as dt, httpx, jwt
from dotenv import load_dotenv
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, func, or_, and_, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
APP_NAME = (os.getenv("APP_NAME") or "Eng Tutor").strip()
VERSION = "1.1.0"
DB = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/engtutor")
log = logging.getLogger("engtutor")
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
    institution = Column(String(150), nullable=True); id_number = Column(String(60), nullable=True); phone = Column(String(30), nullable=True)  # given at self-registration
    self_registered = Column(Boolean, default=False)  # signed up on their own and verified their email; they use their own AI key, never the shared one
    ai_key = Column(Text, nullable=True)  # their own DeepSeek key, encrypted (see seal); only self-registered users have one
class PendingRegistration(Base):  # someone who has asked for an account but has not yet entered the emailed code; becomes a User only when they do
    __tablename__ = "pending_registrations"
    id = Column(Integer, primary_key=True); email = Column(String(190), unique=True, index=True)
    name = Column(String(100)); institution = Column(String(150)); id_number = Column(String(60)); phone = Column(String(30)); pw = Column(String(200))
    code_hash = Column(String(64)); attempts = Column(Integer, default=0); sends = Column(Integer, default=1)
    ip = Column(String(64), index=True); created_at = Column(DateTime, default=dt.datetime.utcnow); last_sent_at = Column(DateTime, default=dt.datetime.utcnow); expires_at = Column(DateTime)
class CourseFaculty(Base):  # legacy faculty-course assignments from before course owners; kept for reference, grants nothing
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
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    pattern = Column(String(10), default="semester")  # "semester" (B.E., B.Tech) or "year" (annual programs such as M.B.B.S); the terms below are Semester n or Year n
class Semester(Base):
    __tablename__ = "semesters"
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    program_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    semester_no = Column(Integer, nullable=True)  # the semester's place in its program (1 to 8): decides order and which students see it; never read from the name
    __table_args__ = (UniqueConstraint("program_id", "semester_no", name="uq_semesters_program_no"),)
class Course(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    program_id = Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=True)
    faculty_owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # the one faculty member who runs the course; null = not assigned yet
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
class PasswordReset(Base):  # one-time "forgot password" links; only a hash of the link token is stored
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, index=True, nullable=True); token_hash = Column(String(64), unique=True, index=True)
    ip = Column(String(64), index=True); created_at = Column(DateTime, default=dt.datetime.utcnow, index=True); expires_at = Column(DateTime); used = Column(Boolean, default=False)
class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    course_id = Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
    position = Column(Integer, nullable=True)  # order within the course, set by its owner
class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True); title = Column(String(200)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    course_id = Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text); sample_content = Column(Text); question_pattern = Column(Text); guideline = Column(Text)
    published = Column(Boolean, default=True)  # drafts are visible to admins and the course's owner only
    position = Column(Integer, nullable=True)  # order within the unit, set by the course's owner
    learning_due_at = Column(DateTime, nullable=True)  # learn-by deadline, a UTC instant like every timestamp here; null = no deadline
class TopicVersion(Base):  # a snapshot of a topic's text each time it is saved, so an earlier version can be read and restored
    __tablename__ = "topic_versions"
    id = Column(Integer, primary_key=True); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title = Column(String(200)); content = Column(Text); sample_content = Column(Text); question_pattern = Column(Text); guideline = Column(Text)
    saved_by = Column(Integer, nullable=True); saved_at = Column(DateTime, default=dt.datetime.utcnow); note = Column(String(200), default="")
class Quiz(Base):  # a multiple-choice quiz attached to a unit
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True); unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), index=True); course_id = Column(Integer, index=True)
    title = Column(String(200)); pass_percent = Column(Integer, default=50); published = Column(Boolean, default=False)
class Question(Base):
    __tablename__ = "quiz_questions"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); pos = Column(Integer, default=0)
    text = Column(Text); options = Column(Text); correct = Column(Integer); explanation = Column(Text)  # options is a JSON list
    topic_id = Column(Integer, nullable=True)  # the topic this question tests, chosen by the author; must be a topic of the quiz's unit
class BankQuestion(Base):  # a reusable question any faculty member or admin can browse and add to their own quizzes; adding copies it, so later edits never change a live quiz
    __tablename__ = "question_bank"
    id = Column(Integer, primary_key=True); owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True); sig = Column(String(40), index=True)
    text = Column(Text); options = Column(Text); correct = Column(Integer); explanation = Column(Text); tags = Column(String(200), default=""); source = Column(String(200), default="")
    uses = Column(Integer, default=0); created_at = Column(DateTime, default=dt.datetime.utcnow)
class Attempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); user_id = Column(Integer, ForeignKey("users.id"), index=True)
    score = Column(Integer); total = Column(Integer); percent = Column(Integer); at = Column(DateTime, default=dt.datetime.utcnow)
    detail = Column(Text, nullable=True)  # JSON [[question_id, 1 or 0], ...] so strengths and weak areas can be worked out; null on attempts made before this existed
class Progress(Base):  # one row per student and topic, made when they first open it. No row = not started; completed_at null = in progress
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id")); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    reads = Column(Integer, default=1); last_read = Column(DateTime, default=dt.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)  # set when the student marks the topic completed (UTC); cleared only if they undo it
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
def can_edit(u, course_id, s):  # admins edit everything; faculty only the courses they own. me() has already refused disabled accounts
    if u.role == "admin": return True
    co = s.get(Course, course_id) if course_id else None
    return u.role == "faculty" and co is not None and co.faculty_owner_id == u.id
def need_edit(u, course_id, s):
    if not can_edit(u, course_id, s): raise HTTPException(403, "You are not the owner of this course")
def owner_problem(owner):  # why a course's owner can't run it, or "" when they can
    if owner is None: return "Owner not assigned"
    if owner.role != "faculty": return f"Owner {owner.name} is no longer faculty"
    return "" if owner.active else f"Owner {owner.name} is disabled"
def set_owner(s, co, user_id):  # the one place a course's owner changes; content, progress and quizzes are untouched
    if user_id is not None:
        f = s.get(User, user_id)
        if not f or f.role != "faculty" or not f.active: raise HTTPException(400, "The owner must be an active faculty member")
    co.faculty_owner_id = user_id
def setting(s, k, d=""):
    r = s.get(Setting, k); return r.v if r else d

app = FastAPI(title=APP_NAME)
ORIGINS = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]  # the app is same-origin; set this only for a separate front-end
if ORIGINS: app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
       "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
SKIP_AUDIT = re.compile(r"/(read|bookmark|attempt|complete)$|/ai/")  # student reading activity is already tracked as progress
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
def config(s: Session = Depends(db)): return {"self_registration": reg_open(s), "name": setting(s, "app_name", APP_NAME), "logo": setting(s, "logo_url", "") or None, "version": VERSION, "email_reset": mail_on()}
class Branding(BaseModel): name: str | None = None; logo_url: str | None = None; remove_logo: bool = False
LOGO_URL = re.compile(r"/api/uploads/[0-9a-f]{32}\.(png|jpg|gif|webp)")
@app.put("/api/admin/branding")
def put_branding(b: Branding, _: User = Depends(admin), s: Session = Depends(db)):  # the institution's name and logo; the logo is an image already uploaded here, never an outside address
    if b.name is not None:
        n = b.name.strip()
        if len(n) > 60: raise HTTPException(400, "Keep the name under 60 characters")
        if n: s.merge(Setting(k="app_name", v=n))
        else: s.query(Setting).filter_by(k="app_name").delete()  # back to APP_NAME from .env
    if b.remove_logo: s.query(Setting).filter_by(k="logo_url").delete()
    elif b.logo_url:
        if not LOGO_URL.fullmatch(b.logo_url): raise HTTPException(400, "Upload the logo image first, then save")
        s.merge(Setting(k="logo_url", v=b.logo_url))
    s.commit(); return {"ok": True}
# ---- forgot password by email (needs SMTP_HOST, SMTP_FROM and APP_URL in .env) ----
def mail_on(): return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM") and os.getenv("APP_URL"))  # APP_URL is fixed so a forged Host header can't poison reset links
def send_mail(to, subject, body):
    m = EmailMessage(); m["From"], m["To"], m["Subject"] = os.getenv("SMTP_FROM"), to, subject; m.set_content(body)
    host, port, mode = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT") or 587), (os.getenv("SMTP_TLS") or "starttls").lower()
    with (smtplib.SMTP_SSL(host, port, timeout=20) if mode == "ssl" else smtplib.SMTP(host, port, timeout=20)) as c:
        if mode == "starttls": c.starttls()
        if os.getenv("SMTP_USER"): c.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD") or "")
        c.send_message(m)
def deliver_reset(email, name, raw):
    minutes = int(os.getenv("RESET_MINUTES") or 30)
    try: send_mail(email, f"Reset your {APP_NAME} password", f"Hi {name},\n\nSomeone asked to reset the password for your {APP_NAME} account. To choose a new one, open this link within {minutes} minutes:\n\n{os.getenv('APP_URL').rstrip('/')}/#reset={raw}\n\nIf you didn't ask for this, ignore this email. Your password stays the same.\n")
    except Exception as e: log.warning("reset email failed: %s", type(e).__name__)
def tok_hash(raw): return hashlib.sha256(raw.encode()).hexdigest()
class ForgotIn(BaseModel): email: str
@app.post("/api/forgot")
def forgot(b: ForgotIn, request: Request, bg: BackgroundTasks, s: Session = Depends(db)):
    if not mail_on(): raise HTTPException(503, "Reset by email isn't set up here. Ask your admin to reset your password.")
    ip, email, now = client_ip(request), b.email.strip().lower()[:190], dt.datetime.utcnow(); hour = now - dt.timedelta(hours=1)
    if s.query(func.count(PasswordReset.id)).filter(PasswordReset.ip == ip, PasswordReset.created_at >= hour).scalar() >= 20: raise HTTPException(429, "Too many requests. Please try again in an hour.")
    u = s.query(User).filter_by(email=email).first(); u = u if u and u.active else None
    reply = {"ok": True, "message": "If that email has an account, a reset link is on its way. Check your inbox and spam folder."}  # same answer whether or not the account exists
    if u and s.query(func.count(PasswordReset.id)).filter(PasswordReset.user_id == u.id, PasswordReset.created_at >= hour).scalar() >= 3: return reply
    raw = secrets.token_urlsafe(32)
    s.add(PasswordReset(user_id=u.id if u else None, token_hash=tok_hash(raw), ip=ip, expires_at=now + dt.timedelta(minutes=int(os.getenv("RESET_MINUTES") or 30)))); s.commit()
    if u: bg.add_task(deliver_reset, u.email, u.name, raw)
    return reply
def live_reset(raw, s):
    r = s.query(PasswordReset).filter_by(token_hash=tok_hash(raw or "")).first()
    u = s.get(User, r.user_id) if r and r.user_id else None
    return (r, u) if r and not r.used and r.expires_at > dt.datetime.utcnow() and u and u.active else (None, None)
class ResetCheck(BaseModel): token: str
class ResetIn(BaseModel): token: str; new_password: str
@app.post("/api/reset/check")
def reset_check(b: ResetCheck, s: Session = Depends(db)): return {"valid": live_reset(b.token, s)[0] is not None}
@app.post("/api/reset")
def reset_password(b: ResetIn, s: Session = Depends(db)):
    r, u = live_reset(b.token, s)
    if not r: raise HTTPException(400, "This link has expired or was already used. Ask for a new one.")
    if len(b.new_password) < 8: raise HTTPException(400, "Use at least 8 characters")
    if b.new_password.strip().lower() == u.email: raise HTTPException(400, "Password can't be your email")
    u.pw = hp(b.new_password); u.must_change = False; r.used = True  # ends every old session and any older reset links
    s.query(PasswordReset).filter(PasswordReset.user_id == u.id, PasswordReset.id != r.id).delete(); s.query(LoginFail).filter_by(email=u.email).delete(); s.commit()
    return {"token": make_token(u), "user": {"id": u.id, "name": u.name, "role": u.role, "must_change": False}}
# ---- self-registration with an emailed one-time code ----
from cryptography.fernet import Fernet, InvalidToken
def _fernet(): return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"user-ai-key|" + SECRET.encode()).digest()))
def seal(v): return _fernet().encrypt(v.encode()).decode()  # a user's own AI key is stored encrypted; changing JWT_SECRET makes saved keys unreadable, so people simply enter them again
def unseal(v):
    try: return _fernet().decrypt(v.encode()).decode()
    except (InvalidToken, ValueError, TypeError): return ""
OTP_MINUTES, OTP_MAX_TRIES, OTP_MAX_SENDS, OTP_COOLDOWN = 10, 5, 8, 30
def otp_hash(email, code): return hmac.new(SECRET.encode(), f"{email}|{code}".encode(), hashlib.sha256).hexdigest()
def reg_open(s): return setting(s, "self_registration") == "1" and mail_on()
def allowed_domains(s): return [d for d in re.split(r"[,\s]+", setting(s, "allowed_domains").lower()) if d]
PHONE = re.compile(r"\+?[0-9][0-9 ()\-]{5,24}[0-9]")
IDNUM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ./_\-]{0,58}[A-Za-z0-9]|[A-Za-z0-9]")
def deliver_otp(email, name, code, exists=False):
    try:
        if exists: send_mail(email, f"Your {APP_NAME} account", f"Hi {name},\n\nSomeone tried to register {email} on {APP_NAME}, but that email already has an account. If it was you, sign in, or use \"Forgot your password?\" on the sign-in page. If it was not you, ignore this message.")
        else: send_mail(email, f"Your {APP_NAME} verification code: {code}", f"Hi {name},\n\nYour verification code is {code}. It works for {OTP_MINUTES} minutes. Enter it in the app to finish creating your {APP_NAME} account.\n\nIf you did not ask for this, ignore this message; no account is created without the code.")
    except Exception as e: log.warning("registration email failed: %s", type(e).__name__)
class RegisterIn(BaseModel): name: str; institution: str; id_number: str; email: str; phone: str; password: str
def clean_registration(b, s):
    name, inst, idn, email, phone = " ".join(b.name.split()), " ".join(b.institution.split()), " ".join(b.id_number.split()), b.email.strip().lower(), b.phone.strip()
    if not 2 <= len(name) <= 100: raise HTTPException(400, "Enter your full name")
    if not 2 <= len(inst) <= 150: raise HTTPException(400, "Enter your institution")
    if not IDNUM.fullmatch(idn): raise HTTPException(400, "Enter your ID number (letters, numbers, spaces and - / . _ only)")
    if not EMAIL.match(email) or len(email) > 190: raise HTTPException(400, "Enter a valid email")
    if not PHONE.fullmatch(phone) or not 7 <= sum(ch.isdigit() for ch in phone) <= 15: raise HTTPException(400, "Enter a valid phone number, for example +91 98765 43210")
    if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters for the password")
    if b.password.strip().lower() == email: raise HTTPException(400, "Password can't be your email")
    doms = allowed_domains(s)
    if doms and not any(email.endswith("@" + d) or email.endswith("." + d) for d in doms): raise HTTPException(400, "Use your institution email address (" + ", ".join("@" + d for d in doms) + ")")
    return name, inst, idn, email, phone
def same_id(s, inst, idn):
    return s.query(User.id).filter(func.lower(User.institution) == inst.lower(), func.lower(User.id_number) == idn.lower()).first() is not None
@app.get("/api/register/status")
def register_status(s: Session = Depends(db)): return {"open": reg_open(s), "domains": allowed_domains(s)}
@app.post("/api/register/start")
def register_start(b: RegisterIn, request: Request, bg: BackgroundTasks, s: Session = Depends(db)):
    if not reg_open(s): raise HTTPException(403, "Self-registration is not open here. Ask your admin for an account.")
    name, inst, idn, email, phone = clean_registration(b, s); ip, now = client_ip(request), dt.datetime.utcnow()
    if s.query(func.count(PendingRegistration.id)).filter(PendingRegistration.ip == ip, PendingRegistration.last_sent_at >= now - dt.timedelta(hours=1)).scalar() >= 15:
        raise HTTPException(429, "Too many attempts from this network. Please try again in an hour.")
    reply = {"ok": True, "email": email, "message": f"We sent a 6-digit code to {email}. It works for {OTP_MINUTES} minutes."}
    if s.query(User.id).filter_by(email=email).first():  # the same answer as a new address, so nobody can use this form to find out who has an account
        if s.query(func.count(PendingRegistration.id)).filter(PendingRegistration.ip == ip, PendingRegistration.last_sent_at >= now - dt.timedelta(minutes=1)).scalar() < 3: bg.add_task(deliver_otp, email, name, "", True)
        return reply
    if same_id(s, inst, idn): raise HTTPException(400, "An account already exists for that institution ID. Sign in, or ask your admin.")
    code = f"{secrets.randbelow(10 ** 6):06d}"; p = s.query(PendingRegistration).filter_by(email=email).first()
    if p:
        if p.last_sent_at and (now - p.last_sent_at).total_seconds() < OTP_COOLDOWN: raise HTTPException(429, "Wait a moment before asking for another code.")
        if p.sends >= OTP_MAX_SENDS: raise HTTPException(429, "Too many codes were requested for this email. Please try again tomorrow.")
        p.sends += 1
    else: p = PendingRegistration(email=email, sends=1, created_at=now); s.add(p)
    p.name, p.institution, p.id_number, p.phone, p.pw = name, inst, idn, phone, hp(b.password); p.code_hash = otp_hash(email, code); p.attempts = 0; p.ip = ip; p.last_sent_at = now
    p.expires_at = now + dt.timedelta(minutes=OTP_MINUTES); s.commit(); bg.add_task(deliver_otp, email, name, code)
    return reply
class VerifyIn(BaseModel): email: str; code: str
@app.post("/api/register/verify")
def register_verify(b: VerifyIn, s: Session = Depends(db)):
    email, code, now = b.email.strip().lower()[:190], "".join(ch for ch in b.code if ch.isdigit()), dt.datetime.utcnow()
    p = s.query(PendingRegistration).filter_by(email=email).first(); bad = HTTPException(400, "That code has expired or is not valid. Ask for a new one.")
    if not p or p.expires_at < now or p.attempts >= OTP_MAX_TRIES: raise bad
    if not hmac.compare_digest(p.code_hash, otp_hash(email, code)):
        p.attempts += 1; left = OTP_MAX_TRIES - p.attempts; s.commit()
        raise HTTPException(400, f"That code is not right. {left} {'try' if left == 1 else 'tries'} left." if left else "Too many wrong codes. Ask for a new one.")
    if s.query(User.id).filter_by(email=email).first() or same_id(s, p.institution, p.id_number): s.delete(p); s.commit(); raise bad
    u = User(name=p.name, email=email, pw=p.pw, role="student", active=True, must_change=False, institution=p.institution, id_number=p.id_number, phone=p.phone, self_registered=True)
    s.add(u); s.delete(p)
    try: s.commit()
    except IntegrityError: s.rollback(); raise bad
    return {"token": make_token(u), "user": me_json(u)}
@app.post("/api/register/resend")
def register_resend(b: ForgotIn, request: Request, bg: BackgroundTasks, s: Session = Depends(db)):
    email, now = b.email.strip().lower()[:190], dt.datetime.utcnow(); p = s.query(PendingRegistration).filter_by(email=email).first()
    reply = {"ok": True, "message": f"If a registration is waiting for {email}, a new code is on its way."}
    if not reg_open(s) or not p: return reply
    if (now - p.last_sent_at).total_seconds() < OTP_COOLDOWN: raise HTTPException(429, "Wait a moment before asking for another code.")
    if p.sends >= OTP_MAX_SENDS: raise HTTPException(429, "Too many codes were requested for this email. Please try again tomorrow.")
    code = f"{secrets.randbelow(10 ** 6):06d}"; p.code_hash = otp_hash(email, code); p.attempts = 0; p.sends += 1; p.last_sent_at = now; p.expires_at = now + dt.timedelta(minutes=OTP_MINUTES); s.commit()
    bg.add_task(deliver_otp, email, p.name, code); return reply
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
# Copied parent ids (subjects.course_id = program, topics.subject_id / quizzes.course_id = course) are re-derived from the real parent,
# but only where that parent exists; rows with a missing parent are left alone and reported. Plain SQL that MariaDB and SQLite both accept.
REPAIRS = [
    ("subjects", "course_id", "SELECT sm.program_id FROM semesters sm JOIN courses p ON p.id = sm.program_id WHERE sm.id = subjects.semester_id"),
    ("topics", "subject_id", "SELECT un.subject_id FROM units un JOIN subjects co ON co.id = un.subject_id WHERE un.id = topics.unit_id"),
    ("quizzes", "course_id", "SELECT un.subject_id FROM units un JOIN subjects co ON co.id = un.subject_id WHERE un.id = quizzes.unit_id")]
ORPHANS = {  # name -> query for the ids of rows whose parent is missing
    "semesters without a program": "SELECT sm.id FROM semesters sm LEFT JOIN courses p ON p.id = sm.program_id WHERE p.id IS NULL",
    "semesters without a number": "SELECT id FROM semesters WHERE semester_no IS NULL",
    "courses without a semester": "SELECT co.id FROM subjects co LEFT JOIN semesters sm ON sm.id = co.semester_id WHERE sm.id IS NULL",
    "units without a course": "SELECT un.id FROM units un LEFT JOIN subjects co ON co.id = un.subject_id WHERE co.id IS NULL",
    "topics without a unit": "SELECT t.id FROM topics t LEFT JOIN units un ON un.id = t.unit_id WHERE un.id IS NULL",
    "quizzes without a unit": "SELECT q.id FROM quizzes q LEFT JOIN units un ON un.id = q.unit_id WHERE un.id IS NULL"}
def integrity_report(c):  # {problem: [ids]} for every hierarchy row whose parent is missing; nothing is changed
    has_no = "semester_no" in [x["name"] for x in inspect(c).get_columns("semesters")]  # migration 0007 runs before 0010 adds the column on an old database
    return {k: [r[0] for r in c.execute(text(q))] for k, q in ORPHANS.items() if has_no or "semester_no" not in q}
def resync_parent_copies(c):  # returns rows changed per copied column
    fixed = {}
    for table, col, parent in REPAIRS:
        if col not in [x["name"] for x in inspect(c).get_columns(table)]: continue
        fixed[f"{table}.{col}"] = c.execute(text(f"UPDATE {table} SET {col} = ({parent}) WHERE EXISTS ({parent}) AND ({col} IS NULL OR {col} <> ({parent}))")).rowcount
    return fixed
def repair_parent_copies(c):
    fixed = resync_parent_copies(c)
    log.warning("Repaired copied parent ids: %s", fixed)
    for k, v in integrity_report(c).items():
        if v: log.warning("Left alone, %s: %d (ids %s). Fix or delete these by hand.", k, len(v), v[:50])
    return fixed
def add_faculty_owner(c):  # subjects.faculty_owner_id with its index and, where the database supports adding one, its foreign key
    _addcol("subjects", "faculty_owner_id", "INT NULL")(c); ins = inspect(c)
    if "ix_subjects_faculty_owner_id" not in [i["name"] for i in ins.get_indexes("subjects")]:
        c.execute(text("CREATE INDEX ix_subjects_faculty_owner_id ON subjects (faculty_owner_id)"))
    if c.dialect.name != "sqlite" and not any(f["constrained_columns"] == ["faculty_owner_id"] for f in ins.get_foreign_keys("subjects")):
        c.execute(text("ALTER TABLE subjects ADD CONSTRAINT fk_subjects_faculty_owner FOREIGN KEY (faculty_owner_id) REFERENCES users (id) ON DELETE SET NULL"))
def ownership_report(c):
    """Courses without a working owner, with their legacy course_faculty assignments as candidates. Changes nothing."""
    users = {r[0]: r for r in c.execute(text("SELECT id, name, role, active FROM users"))}
    legacy = defaultdict(list)
    for cid, uid in c.execute(text("SELECT course_id, user_id FROM course_faculty ORDER BY id")): legacy[cid].append(uid)
    ok = lambda uid: uid in users and users[uid][2] == "faculty" and bool(users[uid][3])
    rep = {"owned": [], "multiple_assigned": [], "no_faculty": [], "assigned_not_faculty": [], "invalid_owner": []}
    for cid, owner in c.execute(text("SELECT id, faculty_owner_id FROM subjects ORDER BY id")):
        if owner is not None: rep["owned" if ok(owner) else "invalid_owner"].append(cid)
        elif len(legacy[cid]) > 1: rep["multiple_assigned"].append(cid)  # never pick one of several
        elif not legacy[cid]: rep["no_faculty"].append(cid)
        elif not ok(legacy[cid][0]): rep["assigned_not_faculty"].append(cid)
    return rep, legacy, ok
def owners_from_assignments(c):  # a course with exactly one assigned, active faculty member and no owner yet gets them as owner
    rep, legacy, ok = ownership_report(c); made = 0
    for cid, uids in legacy.items():
        if len(uids) == 1 and ok(uids[0]):
            made += c.execute(text("UPDATE subjects SET faculty_owner_id = :u WHERE id = :c AND faculty_owner_id IS NULL"), {"u": uids[0], "c": cid}).rowcount
    rep = ownership_report(c)[0]
    log.warning("Course owners: %d assigned from the only assigned faculty member. Still need an owner: %d with several assigned faculty %s, "
                "%d with no faculty %s, %d whose assigned user is not active faculty %s. Invalid owners: %s", made, len(rep["multiple_assigned"]), rep["multiple_assigned"][:50],
                len(rep["no_faculty"]), rep["no_faculty"][:50], len(rep["assigned_not_faculty"]), rep["assigned_not_faculty"][:50], rep["invalid_owner"][:50])
    return made
def semester_numbers(c):  # semesters.semester_no, filled once from the names where that is unambiguous, then unique per program
    _addcol("semesters", "semester_no", "INT NULL")(c)
    rows = list(c.execute(text("SELECT id, program_id, name, semester_no FROM semesters ORDER BY id")))
    taken, claims = defaultdict(set), defaultdict(list)
    for i, p, n, no in rows:
        if no is not None: taken[p].add(no)
    for i, p, n, no in rows:
        if no is None and sem_no(n) is not None: claims[(p, sem_no(n))].append(i)
    made, left = 0, [i for i, p, n, no in rows if no is None and sem_no(n) is None]
    for (p, k), sids in claims.items():
        if len(sids) == 1 and k not in taken[p]: made += c.execute(text("UPDATE semesters SET semester_no = :k WHERE id = :i"), {"k": k, "i": sids[0]}).rowcount
        else: left += sids  # two semesters of one program read as the same number: an admin decides
    ins = inspect(c)
    if "uq_semesters_program_no" not in [x["name"] for x in ins.get_indexes("semesters")] + [x["name"] for x in ins.get_unique_constraints("semesters")]:
        c.execute(text("CREATE UNIQUE INDEX uq_semesters_program_no ON semesters (program_id, semester_no)"))
    log.warning("Semester numbers: %d set from their names; %d left without a number (ids %s). Set them under Programs.", made, len(left), sorted(left)[:50])
    return made
def positions(c):  # units.position and topics.position, filled in today's order (by id) wherever missing
    for table, parent in (("units", "subject_id"), ("topics", "unit_id")):
        _addcol(table, "position", "INT NULL")(c)
        top = defaultdict(int)
        for pid, mx in c.execute(text(f"SELECT {parent}, MAX(position) FROM {table} GROUP BY {parent}")): top[pid] = mx or 0
        for rid, pid in c.execute(text(f"SELECT id, {parent} FROM {table} WHERE position IS NULL ORDER BY id")).all():
            top[pid] += 1; c.execute(text(f"UPDATE {table} SET position = :p WHERE id = :i"), {"p": top[pid], "i": rid})
def learning_state_columns(c):  # topics.learning_due_at and progress.completed_at; nobody gets an invented deadline or completion
    _addcol("topics", "learning_due_at", "DATETIME NULL")(c); _addcol("progress", "completed_at", "DATETIME NULL")(c)
    ins = inspect(c)  # the (user_id, topic_id) unique key has been there since the first release; make sure, without merging anyone's rows
    if not any(sorted(x["column_names"]) == ["topic_id", "user_id"] for x in ins.get_unique_constraints("progress") + [i for i in ins.get_indexes("progress") if i.get("unique")]):
        dups = c.execute(text("SELECT user_id, topic_id FROM progress GROUP BY user_id, topic_id HAVING COUNT(*) > 1")).all()
        if dups: log.warning("progress has %d duplicated student/topic pairs; the unique key was not added", len(dups))
        else: c.execute(text("CREATE UNIQUE INDEX uq_progress_user_topic ON progress (user_id, topic_id)"))
def program_pattern(c):  # courses.pattern; every existing program is a semester program
    _addcol("courses", "pattern", "VARCHAR(10) DEFAULT 'semester'")(c); c.execute(text("UPDATE courses SET pattern = 'semester' WHERE pattern IS NULL"))
def registration_columns(c):  # users.institution, id_number, phone, self_registered, ai_key; nobody is marked self-registered retroactively
    for col, typ in (("institution", "VARCHAR(150) NULL"), ("id_number", "VARCHAR(60) NULL"), ("phone", "VARCHAR(30) NULL"), ("self_registered", "TINYINT(1) NOT NULL DEFAULT 0"), ("ai_key", "TEXT NULL")):
        _addcol("users", col, typ)(c)
# Append new migrations at the END. Each runs once, is recorded in schema_migrations, and must be safe to run on a database that already has the change.
MIGRATIONS = [("0001_topics_unit_id", _addcol("topics", "unit_id", "INT NULL")), ("0002_subjects_semester_id", _addcol("subjects", "semester_id", "INT NULL")),
              ("0003_users_program_id", _addcol("users", "program_id", "INT NULL")), ("0004_users_semester", _addcol("users", "semester", "INT NULL")),
              ("0005_users_must_change", _addcol("users", "must_change", "TINYINT(1) NOT NULL DEFAULT 0")), ("0006_topics_published", _addcol("topics", "published", "TINYINT(1) NOT NULL DEFAULT 1")),
              ("0007_repair_parent_copies", repair_parent_copies), ("0008_subjects_faculty_owner_id", add_faculty_owner),
              ("0009_course_owners_from_assignments", owners_from_assignments), ("0010_semesters_semester_no", semester_numbers),
              ("0011_unit_topic_positions", positions), ("0012_learning_deadlines", learning_state_columns),
              ("0013_questions_topic_id", _addcol("quiz_questions", "topic_id", "INT NULL")), ("0014_attempts_detail", _addcol("quiz_attempts", "detail", "TEXT NULL")),
              ("0015_users_self_registration", registration_columns), ("0016_program_pattern", program_pattern)]
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
    with Session_() as s: s.query(PasswordReset).filter(PasswordReset.created_at < dt.datetime.utcnow() - dt.timedelta(days=2)).delete(); s.commit()
    with Session_() as s: s.query(PendingRegistration).filter(PendingRegistration.created_at < dt.datetime.utcnow() - dt.timedelta(days=1)).delete(); s.commit()
    with Session_() as s: s.query(AuditLog).filter(AuditLog.at < dt.datetime.utcnow() - dt.timedelta(days=400)).delete(); s.commit()
    with Session_() as s:
        for co in s.query(Course).all():  # topics without a unit go into "General"
            orphans = s.query(Topic).filter(Topic.course_id == co.id, Topic.unit_id.is_(None)).all()
            if orphans:
                un = Unit(name="General", course_id=co.id, created_by=co.created_by, position=next_pos(s, Unit, course_id=co.id)); s.add(un); s.flush()
                for t in orphans: t.unit_id = un.id
        for p in s.query(Program).all():  # courses without a semester go into "Semester 1"
            orphans = s.query(Course).filter(Course.program_id == p.id, Course.semester_id.is_(None)).all()
            if orphans:
                sem = Semester(name="Semester 1", program_id=p.id, created_by=p.created_by); s.add(sem); s.flush()
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
def me_json(u): return {"id": u.id, "name": u.name, "role": u.role, "must_change": bool(u.must_change), "self_registered": bool(u.self_registered), "placed": u.role != "student" or bool(u.program_id)}
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
    return {"token": make_token(u), "user": me_json(u)}
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
def whoami(u: User = Depends(me)): return me_json(u)
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
SEM = re.compile(r"^(?:s|sem|semester|y|yr|year)?\s*([1-8])$", re.I)
PATTERNS = {"semester": "Semester", "year": "Year"}; DEFAULT_TERMS = {"semester": 8, "year": 4}
def term_label(p): return PATTERNS.get(getattr(p, "pattern", None) or "semester", "Semester")
def gen_pw(): return "".join(secrets.choice(PWCHARS) for _ in range(10))
def to_sem(v):  # 3, "3", "Semester 3", "S3" -> 3; blank -> None; anything else -> error
    if v is None or str(v).strip() == "": return None
    m = SEM.match(str(v).strip())
    if not m: raise HTTPException(400, "Semester or year must be a number from 1 to 8")
    return int(m.group(1))
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
def sem_no(name):  # "Semester 1", "Sem I", "S3" -> number. Only used to fill semesters.semester_no once (migration 0010, CSV import)
    m = re.search(r"(?<![\w])(?:[1-8]|viii|vii|vi|iv|v|iii|ii|i)(?![\w])", name or "", re.I)
    return None if not m else (int(m.group(0)) if m.group(0).isdigit() else ROMAN[m.group(0).lower()])
def scoped(u): return u.role == "student"  # a student without a program sees no programs, courses or topics until an admin enrols them
def sem_visible(u, sem):  # a student sees their own program, up to and including their current semester
    if not scoped(u): return True
    if sem.program_id != u.program_id: return False
    n = sem.semester_no
    return u.semester is None or n is None or n <= u.semester
# Parents are read through the real chain (Topic > Unit > Course > Semester > Program). topics.subject_id and
# subjects.course_id are older copies kept in sync for compatibility; they never decide who may see or edit something.
def topic_course_id(t, s):  # None when the chain is broken, which only admins get past
    un = s.get(Unit, t.unit_id) if t.unit_id else None
    return un.course_id if un else None
def quiz_course_id(q, s):
    un = s.get(Unit, q.unit_id) if q.unit_id else None
    return un.course_id if un else None
def check_course_access(u, course_id, s):
    if not scoped(u): return
    co = s.get(Course, course_id) if course_id else None; sem = s.get(Semester, co.semester_id) if co and co.semester_id else None
    ok = co and sem and sem_visible(u, sem)
    if not ok and co:  # or the course is shared into one of the student's visible semesters
        ok = any(sem_visible(u, x) for x in s.query(Semester).join(CourseLink, CourseLink.semester_id == Semester.id).filter(CourseLink.course_id == co.id))
    if not ok: raise HTTPException(403, "This is not part of your program or semester")
def check_topic_access(u, t, s):  # drafts are for admins and the faculty assigned to the course only
    cid = topic_course_id(t, s)
    if t.published is False and not can_edit(u, cid, s): raise HTTPException(404, "Topic not found")
    check_course_access(u, cid, s)
def sem_number(s, program_id, n, keep=None):  # a semester number is 1 to 8 and unique within its program
    lab = term_label(s.get(Program, program_id)).lower()
    if n is None or not 1 <= n <= 8: raise HTTPException(400, f"The {lab} number must be from 1 to 8")
    dup = s.query(Semester).filter(Semester.program_id == program_id, Semester.semester_no == n, Semester.id != (keep or 0)).first()
    if dup: raise HTTPException(400, f"This program already has {lab} {n} ({dup.name})")
    return n
def item_name(v, what):
    n = (v or "").strip()
    if not n: raise HTTPException(400, f"Enter a {what} name")
    if len(n) > 150: raise HTTPException(400, f"The {what} name is too long")
    return n
def utc_iso(d): return d.isoformat() + "Z" if d else None  # stored times are naive UTC
def due_value(v):  # an aware datetime from the API -> naive UTC for the database; None clears the deadline
    if v is None: return None
    if v.tzinfo is None: raise HTTPException(400, "Give the deadline with its time zone, for example 2026-10-05T17:00:00+05:30")
    v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
    if not 2000 <= v.year <= 2100: raise HTTPException(400, "Choose a deadline between the years 2000 and 2100")
    return v
def learning_state(due, p, now):  # status comes from the progress row; overdue and late are worked out, never stored
    status = "completed" if p is not None and p.completed_at else "in_progress" if p is not None else "not_started"
    return {"status": status, "learning_due_at": utc_iso(due), "completed_at": utc_iso(p.completed_at) if p is not None else None,
            "overdue": due is not None and status != "completed" and due < now, "late": bool(status == "completed" and due and p.completed_at > due)}
def progress_row(s, uid, tid):  # the student's row for a topic, made at most once even when two requests race
    p = s.query(Progress).filter_by(user_id=uid, topic_id=tid).first()
    if p: return p
    s.add(Progress(user_id=uid, topic_id=tid, reads=0))
    try: s.commit()
    except IntegrityError: s.rollback()  # the other request made it first; the unique key kept it to one row
    return s.query(Progress).filter_by(user_id=uid, topic_id=tid).one()
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
def urow(u, prog): return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active, "program_id": u.program_id, "program": prog, "semester": u.semester,
                           "self_registered": bool(u.self_registered), "institution": u.institution, "id_number": u.id_number, "phone": u.phone, "own_ai_key": bool(u.ai_key)}
@app.get("/api/admin/users")
def users(q: str = "", program_id: int | None = None, semester: int | None = None, role: str = "", order: str = "role", limit: int = 50, offset: int = 0,
          _: User = Depends(admin), s: Session = Depends(db)):
    qs = s.query(User, Program.name).outerjoin(Program, Program.id == User.program_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"; conds = [func.lower(User.name).like(like), func.lower(User.email).like(like), func.lower(User.role).like(like), func.lower(Program.name).like(like),
                                                                       func.lower(func.coalesce(User.institution, "")).like(like), func.lower(func.coalesce(User.id_number, "")).like(like), func.coalesce(User.phone, "").like(like)]
        m = SEM.match(q.strip())
        if m: conds.append(User.semester == int(m.group(1)))  # "3", "sem 3" and "semester 3" find semester-3 students
        qs = qs.filter(or_(*conds))
    if program_id is not None: qs = qs.filter(User.program_id == program_id)
    if semester is not None: qs = qs.filter(User.semester == semester)
    if role: qs = qs.filter(User.role == role)
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
            "course_ids": [c.id for c in s.query(Course).filter_by(faculty_owner_id=uid).order_by(Course.id)]}  # the courses they own
class CoursesIn(BaseModel): course_ids: list[int]
@app.put("/api/admin/users/{uid}/courses")
def assign_courses(uid: int, b: CoursesIn, _: User = Depends(admin), s: Session = Depends(db)):  # make uid the owner of exactly these courses
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    want = set(b.course_ids)
    if want and u.role != "faculty": raise HTTPException(400, "Only faculty can own courses")
    rows = s.query(Course).filter(Course.id.in_(want)).all() if want else []
    if len(rows) != len(want): raise HTTPException(400, "Choose valid courses")
    for co in s.query(Course).filter(Course.faculty_owner_id == uid, ~Course.id.in_(want or [0])): set_owner(s, co, None)
    for co in rows: set_owner(s, co, uid)  # takes the course over from any previous owner
    s.commit(); return {"ok": True}
class OwnerIn(BaseModel): user_id: int | None = None
@app.put("/api/courses/{cid}/owner")
def course_owner(cid: int, b: OwnerIn, _: User = Depends(admin), s: Session = Depends(db)):  # assign, change or clear (null) the owner
    co = s.get(Course, cid)
    if not co: raise HTTPException(404, "Course not found")
    set_owner(s, co, b.user_id); s.commit(); return {"ok": True}
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
    s.commit()  # owners are never reassigned automatically; the admin is told which courses now need one
    stranded = s.query(Course).filter_by(faculty_owner_id=u.id).count() if owner_problem(u) else 0
    return {"ok": True, "courses_needing_owner": stranded}
class BulkIn(BaseModel):
    ids: list[int]; action: str; program_id: int | None = None; semester: int | None = None
BULK_ACTIONS = ("disable", "enable", "set_placement", "reset_passwords")
@app.post("/api/admin/users/bulk")
def bulk_users(b: BulkIn, a: User = Depends(admin), s: Session = Depends(db)):
    """One action on many accounts. Accounts that can't take it (yourself, non-students for a placement) are skipped and named; the rest go through."""
    if b.action not in BULK_ACTIONS: raise HTTPException(400, "Unknown action")
    ids = list(dict.fromkeys(b.ids))
    if not ids: raise HTTPException(400, "Select at least one user")
    if len(ids) > (200 if b.action == "reset_passwords" else 500): raise HTTPException(400, "Too many users at once. Select fewer.")
    prog = sem = None
    if b.action == "set_placement":
        if b.program_id is None: raise HTTPException(400, "Choose a program")
        prog = check_program(b.program_id, s); sem = to_sem(b.semester)
    users = {u.id: u for u in s.query(User).filter(User.id.in_(ids))}
    changed, skipped, creds = 0, [], []
    for i in ids:
        u = users.get(i)
        if not u: skipped.append({"id": i, "name": f"#{i}", "reason": "No such user"}); continue
        why = None
        if u.id == a.id and b.action in ("disable", "reset_passwords"): why = "That is your own account"
        elif b.action == "set_placement" and u.role != "student": why = "Only students have a program and semester"
        elif b.action == "disable" and not u.active: why = "Already disabled"
        elif b.action == "enable" and u.active: why = "Already enabled"
        if why: skipped.append({"id": u.id, "name": u.name, "reason": why}); continue
        if b.action == "disable": u.active = False
        elif b.action == "enable": u.active = True
        elif b.action == "set_placement": u.program_id, u.semester = prog, sem
        else:
            pw = gen_pw(); u.pw = hp(pw, TEMP_ITER); u.must_change = True; creds.append({"name": u.name, "email": u.email, "password": pw})
        changed += 1
    s.commit()
    stranded = sum(s.query(Course).filter_by(faculty_owner_id=u.id).count() for u in users.values() if b.action == "disable" and not u.active and u.role == "faculty")
    out = {"action": b.action, "changed": changed, "skipped": skipped[:50], "skipped_count": len(skipped), "courses_needing_owner": stranded}
    if creds: out["credentials"] = creds  # shown once; only hashes are stored
    return out
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
SEM_ORDER = (Semester.semester_no.is_(None), Semester.semester_no, Semester.id)  # by number; semesters without one last
ORDER = {Unit: (Unit.position.is_(None), Unit.position, Unit.id), Topic: (Topic.position.is_(None), Topic.position, Topic.id), Semester: SEM_ORDER}
def next_pos(s, model, **parent): return (s.query(func.max(model.position)).filter_by(**parent).scalar() or 0) + 1
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
    return {"total": qs.count(), "items": [{"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), **c[p.id]} for p in rows]}
@app.get("/api/admin/programs/{pid}")
def admin_program(pid: int, _: User = Depends(admin), s: Session = Depends(db)):
    p = s.get(Program, pid)
    if not p: raise HTTPException(404, "No such program")
    sems = s.query(Semester).filter_by(program_id=pid).order_by(*SEM_ORDER).all()
    cc = dict(s.query(Course.semester_id, func.count(Course.id)).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    tc = dict(s.query(Course.semester_id, func.count(Topic.id)).join(Topic, Topic.course_id == Course.id).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    studs = s.query(User).filter_by(program_id=pid).order_by(func.coalesce(User.semester, 99), func.lower(User.name)).limit(50).all()
    cl = defaultdict(list)
    for co, ow in s.query(Course, User).outerjoin(User, User.id == Course.faculty_owner_id).filter(Course.semester_id.in_([x.id for x in sems] or [0])).order_by(Course.id):
        cl[co.semester_id].append({"id": co.id, "name": co.name, "owner_id": co.faculty_owner_id, "owner": ow.name if ow else None, "owner_problem": owner_problem(ow)})
    return {"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), **counts(s, [pid])[pid],
            "semester_list": [{"id": x.id, "name": x.name, "number": x.semester_no, "courses": cc.get(x.id, 0), "topics": tc.get(x.id, 0), "course_list": cl[x.id]} for x in sems],
            "student_list": [{"id": u.id, "name": u.name, "semester": u.semester, "active": u.active} for u in studs]}
AI_DOWN = "AI unavailable. Try again later."
def ai_key(s): return setting(s, "deepseek_key") or (os.getenv("DEEPSEEK_API_KEY") or "").strip()  # one key, set by the admin, serves every student
async def deepseek(key, model, messages, max_tokens=None, timeout=45):
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {key}"},
                         json={"model": model, "messages": messages, **({"max_tokens": max_tokens} if max_tokens else {})})
    r.raise_for_status(); j = r.json(); text = j["choices"][0]["message"]["content"]
    if not text: raise ValueError("empty answer")
    return text, j.get("usage", {}).get("total_tokens", 0)
def ai_down(u, why=""):  # students get the plain message; admins also get a pointer to the likely fix
    return HTTPException(503, AI_DOWN + (f" (Admin: {why})" if why and u.role == "admin" else ""))
def key_for(u, s):  # self-registered people use their own key and never the shared one; everyone else uses the admin's
    return unseal(u.ai_key) if u.self_registered and u.ai_key else "" if u.self_registered else ai_key(s)
NEEDS_OWN_KEY = "Add your own DeepSeek API key under AI key in the menu to use AI help."
@app.get("/api/ai/status")
def ai_status(u: User = Depends(me), s: Session = Depends(db)): return {"available": bool(key_for(u, s)), "own_key": bool(u.self_registered)}
class OwnKey(BaseModel): key: str
@app.get("/api/me/ai-key")
def my_ai_key(u: User = Depends(me)):
    k = unseal(u.ai_key) if u.ai_key else ""
    return {"own_key": bool(u.self_registered), "key_set": bool(k), "key_hint": ("…" + k[-4:]) if k else ""}
@app.put("/api/me/ai-key")
async def set_my_ai_key(b: OwnKey, u: User = Depends(me), s: Session = Depends(db)):
    if not u.self_registered: raise HTTPException(403, "Your account uses the key your admin saved. You do not need your own.")
    k = b.key.strip()
    if not 20 <= len(k) <= 200 or any(ch.isspace() for ch in k): raise HTTPException(400, "That does not look like a DeepSeek API key. Copy the whole key from your DeepSeek account.")
    try: await deepseek(k, setting(s, "model", "deepseek-chat"), [{"role": "user", "content": "Reply with the word OK."}], max_tokens=5, timeout=20)
    except httpx.HTTPStatusError as e: raise HTTPException(400, "DeepSeek rejected this key (" + str(e.response.status_code) + ")." + (" Check that you copied it correctly." if e.response.status_code in (401, 403) else " Check your DeepSeek balance."))
    except Exception: raise HTTPException(400, "Could not reach DeepSeek to check the key. Try again in a moment.")
    me_row = s.get(User, u.id); me_row.ai_key = seal(k); s.commit()
    return {"ok": True, "key_hint": "…" + k[-4:]}
@app.delete("/api/me/ai-key")
def delete_my_ai_key(u: User = Depends(me), s: Session = Depends(db)):
    s.get(User, u.id).ai_key = None; s.commit(); return {"ok": True}
class Cfg(BaseModel): deepseek_key: str | None = None; model: str | None = None; remove_key: bool = False; self_registration: bool | None = None; allowed_domains: str | None = None
@app.get("/api/admin/settings")
def get_cfg(_: User = Depends(admin), s: Session = Depends(db)):
    k = ai_key(s)
    return {"mail_on": mail_on(), "key_set": bool(k), "key_hint": ("…" + k[-4:]) if k else "", "model": setting(s, "model", "deepseek-chat"),
            "self_registration": setting(s, "self_registration") == "1", "allowed_domains": setting(s, "allowed_domains"), "self_registered_users": s.query(User).filter_by(self_registered=True).count()}
@app.put("/api/admin/settings")
def put_cfg(b: Cfg, _: User = Depends(admin), s: Session = Depends(db)):
    if b.remove_key: s.query(Setting).filter_by(k="deepseek_key").delete()  # turns AI off for everyone until a new key is saved
    for k, v in (("deepseek_key", b.deepseek_key), ("model", b.model)):
        if v and v.strip() and not (k == "deepseek_key" and b.remove_key): s.merge(Setting(k=k, v=v.strip()))
    if b.self_registration is not None: s.merge(Setting(k="self_registration", v="1" if b.self_registration else "0"))
    if b.allowed_domains is not None:
        doms = [d.lstrip("@") for d in re.split(r"[,\s]+", b.allowed_domains.lower()) if d]
        if not all(re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", d) for d in doms): raise HTTPException(400, "Enter email domains such as college.edu, separated by commas")
        s.merge(Setting(k="allowed_domains", v=", ".join(doms)))
    s.commit(); return {"ok": True}
@app.post("/api/admin/ai/test")
async def test_ai(_: User = Depends(admin), s: Session = Depends(db)):
    key = ai_key(s)
    if not key: return {"ok": False, "message": "No key saved yet."}
    try: await deepseek(key, setting(s, "model", "deepseek-chat"), [{"role": "user", "content": "Reply with the word OK."}], max_tokens=5, timeout=20)
    except httpx.HTTPStatusError as e: return {"ok": False, "message": "DeepSeek rejected the request (" + str(e.response.status_code) + "). " + ("The key looks invalid." if e.response.status_code in (401, 403) else "Check the model name and your balance." if e.response.status_code in (400, 402, 404) else "Try again shortly.")}
    except Exception: return {"ok": False, "message": "No answer from DeepSeek. Check the server's internet access and try again."}
    return {"ok": True, "message": "The key works. Students can use AI now."}
@app.post("/api/admin/mail/test")
def test_mail(a: User = Depends(admin)):
    if not mail_on(): return {"ok": False, "message": "Email isn't set up. Add SMTP_HOST, SMTP_FROM and APP_URL to .env and restart."}
    try: send_mail(a.email, f"{APP_NAME} test email", "This is a test. Password reset emails can be sent from this server.")
    except Exception as e: return {"ok": False, "message": "Could not send: " + type(e).__name__ + ": " + str(e)[:150]}
    return {"ok": True, "message": "Test email sent to " + a.email}
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
        return any(x.program_id == u.program_id and (u.semester is None or x.semester_no is None or x.semester_no <= u.semester) for x in places)
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
    if u.role == "faculty": q = q.filter(Course.faculty_owner_id == u.id)
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
        if semester and (not sm or sm.semester_no != semester): continue
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
    batches = latest_batches(s, [x.id for x in aud], course_quiz_ids(cid, s)); ctx = area_context(batches, s); per = defaultdict(list)
    for b in batches: per[b[0]].append(b)
    mine = {uid: tally(bs, ctx, True) for uid, bs in per.items()}
    names = lambda uid, st: [a["title"] for a in sorted(mine.get(uid, {}).values(), key=lambda a: (a["percent"], a["title"])) if a["status"] == st]
    rows = [{"strong": names(x.id, "strong"), "needs_study": names(x.id, "needs_study"), "name": x.name, "email": x.email, "program": pn.get(x.program_id, ""), "semester": x.semester, "active": bool(x.active), "topics_read": reads[x.id], "topics": len(tids),
             "completion": round(100 * reads[x.id] / len(tids)) if tids else 0, "quizzes_taken": len(bests[x.id]), "quizzes": len(qids),
             "avg_quiz_percent": round(sum(bests[x.id].values()) / len(bests[x.id])) if bests[x.id] else None, "last_active": (last[x.id].isoformat() + "Z") if last.get(x.id) else None}
            for x in sorted(aud, key=lambda x: (x.name or "").lower())]
    if format == "csv": return csv_response(f"students-{c.name}.csv".replace(" ", "_"), ["Name", "Email", "Program", "Semester", "Active", "Topics read", "Topics", "Completion %", "Quizzes taken", "Quizzes", "Average best quiz %", "Last active", "Strong areas", "Needs another round of study"],
                                           [[r["name"], r["email"], r["program"], r["semester"], "yes" if r["active"] else "no", r["topics_read"], r["topics"], r["completion"], r["quizzes_taken"], r["quizzes"], r["avg_quiz_percent"], r["last_active"], "; ".join(r["strong"]), "; ".join(r["needs_study"])] for r in rows])
    return {"course": c.name, "students": rows}

# ---- content: admin writes, everyone reads ----
@app.get("/api/overview")
def overview(u: User = Depends(staff), s: Session = Depends(db)):  # what needs attention today: admins see the whole college, faculty only their own courses
    mine = my_courses(u, s); cids = [c.id for c in mine]; now = dt.datetime.utcnow(); week = now - dt.timedelta(days=7)
    units = s.query(Unit.id).filter(Unit.course_id.in_(cids or [0]))
    topics = s.query(Topic).filter(Topic.unit_id.in_(units))
    drafts = topics.filter(Topic.published == False).count()  # noqa: E712
    out = {"role": u.role, "courses": len(cids), "topics": topics.count(), "drafts": drafts, "attention": []}
    add = lambda kind, n, text: n and out["attention"].append({"kind": kind, "count": n, "text": text})
    add("drafts", drafts, f"{drafts} draft topic{'s' if drafts != 1 else ''} not yet visible to students")
    empty = [c for c in mine if not s.query(Unit.id).filter_by(course_id=c.id).first()]
    add("empty_courses", len(empty), f"{len(empty)} course{'s have' if len(empty) != 1 else ' has'} no units yet: " + ", ".join(c.name for c in empty[:5]))
    if u.role == "admin":
        stu = s.query(User).filter_by(role="student", active=True)
        out["people"] = {"students": stu.count(), "faculty": s.query(User).filter_by(role="faculty", active=True).count(),
                         "active_week": s.query(func.count(func.distinct(Progress.user_id))).join(User, User.id == Progress.user_id).filter(User.role == "student", Progress.last_read >= week).scalar()}
        out["programs"] = s.query(Program).count()
        noown = [c for c in mine if c.faculty_owner_id is None]
        add("unowned", len(noown), f"{len(noown)} course{'s have' if len(noown) != 1 else ' has'} no owner, so only admins can edit: " + ", ".join(c.name for c in noown[:5]))
        unplaced = stu.filter(or_(User.program_id.is_(None), User.semester.is_(None))).count()
        add("unenrolled", unplaced, f"{unplaced} active student{'s are' if unplaced != 1 else ' is'} not placed in a program and semester, so they see nothing")
        nonum = s.query(Semester).filter(Semester.semester_no.is_(None)).count()
        add("semester_numbers", nonum, f"{nonum} semester{'s have' if nonum != 1 else ' has'} no semester number (set it under Programs)")
        quiet = stu.filter(User.id.notin_(s.query(Progress.user_id))).count()
        add("never_opened", quiet, f"{quiet} active student{'s have' if quiet != 1 else ' has'} never opened a topic")
    return out
class RolloverIn(BaseModel): dry_run: bool = True; finishing: str = "keep"  # keep: leave the last semester's students where they are; deactivate: switch their accounts off
@app.post("/api/admin/programs/{pid}/rollover")
def rollover(pid: int, b: RolloverIn, _: User = Depends(admin), s: Session = Depends(db)):
    """Start of a new term: every active student in the program moves up one semester. Students already in the program's last semester are
    kept or deactivated. Run it once per term; the preview (dry_run) changes nothing."""
    p = s.get(Program, pid)
    if not p: raise HTTPException(404, "Program not found")
    if b.finishing not in ("keep", "deactivate"): raise HTTPException(400, "finishing must be keep or deactivate")
    top = min(8, max([x.semester_no for x in s.query(Semester).filter_by(program_id=pid) if x.semester_no] or [8]))
    stu = s.query(User).filter_by(role="student", active=True, program_id=pid).order_by(User.name).all()
    moving = [x for x in stu if x.semester and x.semester < top]; finishing = [x for x in stu if x.semester and x.semester >= top]; unplaced = [x for x in stu if not x.semester]
    if not b.dry_run:
        for x in moving: x.semester += 1
        if b.finishing == "deactivate":
            for x in finishing: x.active = False
        s.commit()
    names = lambda L: [x.name for x in L[:20]]
    return {"program": p.name, "dry_run": b.dry_run, "last_semester": top, "term": term_label(p), "moved": len(moving), "finishing": len(finishing), "finishing_action": b.finishing, "unplaced": len(unplaced),
            "finishing_names": names(finishing), "unplaced_names": names(unplaced)}
class ProgramIn(BaseModel): name: str; pattern: str | None = None; terms: int | None = None  # pattern: semester or year; terms: how many to create now (new programs only)
class SemesterIn(BaseModel): name: str; program_id: int; semester_no: int | None = None  # on edit, leave out to keep the number
class NewSemesterIn(BaseModel): name: str; semester_no: int
class NewCourseIn(BaseModel): name: str; faculty_owner_id: int | None = None
class CourseIn(BaseModel): name: str; semester_id: int; faculty_owner_id: int | None = None  # leave out to keep the owner, null for none
class UnitIn(BaseModel): name: str; course_id: int
class TopicIn(BaseModel):
    title: str; unit_id: int; content: str = ""; sample_content: str = ""; question_pattern: str = ""; guideline: str = ""; published: bool = True
    learning_due_at: dt.datetime | None = None  # ISO 8601 with a time zone; null removes the deadline; leave out to keep it
M = {"programs": Program, "semesters": Semester, "courses": Course, "units": Unit, "topics": Topic}
@app.get("/api/tree")
def tree(u: User = Depends(me), s: Session = Depends(db)):
    mine_p = {p.topic_id: p for p in s.query(Progress).filter_by(user_id=u.id)}; read = set(mine_p); now = dt.datetime.utcnow()
    marked = {b.topic_id for b in s.query(Bookmark).filter_by(user_id=u.id)}
    def g(model, k):
        d = defaultdict(list)
        for r in s.query(model).order_by(*ORDER.get(model, (model.id,))): d[getattr(r, k)].append(r)
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
        qz[q.unit_id].append({"id": q.id, "title": q.title, "published": bool(q.published), "questions": qcount.get(q.id, 0), "best": best.get(q.id), "pass_percent": q.pass_percent})
    cbyid = {c.id: c for c in s.query(Course)}
    mine = {c.id for c in cbyid.values() if c.faculty_owner_id == u.id} if u.role == "faculty" else set()
    owners = {x.id: x for x in s.query(User).filter(User.id.in_({c.faculty_owner_id for c in cbyid.values() if c.faculty_owner_id} or {0}))}
    for l in s.query(CourseLink).order_by(CourseLink.id):
        if l.course_id in cbyid: links[l.semester_id].append(cbyid[l.course_id])
    def cj(c, sm):
        shared = c.semester_id != sm.id; ed = u.role == "admin" or c.id in mine  # drafts show only to those who can edit the course
        d = {"id": c.id, "name": c.name, "shared": shared, "semester_id": c.semester_id, "home": sname.get(c.semester_id, "") if shared else "",
             "shared_with": len(linked_to[c.id]), "editable": ed, "mine": c.id in mine,
             "owner": owners[c.faculty_owner_id].name if c.faculty_owner_id in owners else None, "units": [
            {"id": n.id, "name": n.name, "quizzes": [q for q in qz[n.id] if ed or (q["published"] and q["questions"])],
             "topics": [{"id": t.id, "title": t.title, "read": t.id in read, "bookmarked": t.id in marked, "published": t.published is not False,
                         "last_read": mine_p[t.id].last_read.isoformat() + "Z" if t.id in mine_p and mine_p[t.id].last_read else None,
                         **learning_state(t.learning_due_at, mine_p.get(t.id), now)} for t in tp[n.id] if t.published is not False or ed]} for n in un[c.id]]}
        if u.role == "admin": d["link_ids"] = linked_to[c.id]; d["owner_id"] = c.faculty_owner_id; d["owner_problem"] = owner_problem(owners.get(c.faculty_owner_id))
        return d
    return [{"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), "semesters": [{"id": sm.id, "name": sm.name, "number": sm.semester_no, "current": scoped(u) and u.semester is not None and sm.semester_no == u.semester,
        "courses": [cj(c, sm) for c in co[sm.id] + links[sm.id]]} for sm in se[p.id] if sem_visible(u, sm)]} for p in progs]
class PublishIn(BaseModel): published: bool
@app.put("/api/topics/{rid}/publish")
def publish_topic(rid: int, b: PublishIn, u: User = Depends(staff), s: Session = Depends(db)):
    t = s.get(Topic, rid)
    if not t: raise HTTPException(404, "Not found")
    need_edit(u, topic_course_id(t, s), s); t.published = b.published; s.commit(); return {"ok": True, "changed": 1}
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
def save_row(row, u, s): row.created_by = u.id; s.add(row); s.commit(); return {"id": row.id}
def course_fields(b, s):
    sem = s.get(Semester, b.semester_id)
    if not sem: raise HTTPException(400, "Choose a semester for this course")
    return {"name": b.name, "semester_id": sem.id, "program_id": sem.program_id}
VFIELDS = ("title", "content", "sample_content", "question_pattern", "guideline")
VERSIONS_KEPT = 100
def topic_state(t): return {k: getattr(t, k) or "" for k in VFIELDS}
def record_version(s, t, before, user_id, note=""):
    """Call after a topic's text changed. before = topic_state() from before the change, or None for a new topic. Nothing is stored when the text did not change.
    A topic that predates version history first gets its old text kept as the baseline, so the first edit can be undone too."""
    now = topic_state(t)
    if before is not None and before == now: return False
    if t.id is None: s.flush()
    if before is not None and not s.query(TopicVersion.id).filter_by(topic_id=t.id).first():
        s.add(TopicVersion(topic_id=t.id, saved_by=None, saved_at=dt.datetime.utcnow() - dt.timedelta(seconds=1), note="Before the first recorded edit", **before))
    s.add(TopicVersion(topic_id=t.id, saved_by=user_id, note=note[:200], **now)); s.flush()
    old = [i for (i,) in s.query(TopicVersion.id).filter_by(topic_id=t.id).order_by(TopicVersion.id.desc()).offset(VERSIONS_KEPT)]
    if old: s.query(TopicVersion).filter(TopicVersion.id.in_(old)).delete(synchronize_session=False)
    return True
def topic_fields(b, s):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this topic")
    title = (b.title or "").strip()
    if not title or len(title) > 200: raise HTTPException(400, "Give the topic a title (up to 200 characters)")
    f = {**b.dict(exclude_unset=True), "title": title, "course_id": un.course_id}  # fields left out are left alone
    if "learning_due_at" in f: f["learning_due_at"] = due_value(b.learning_due_at)
    return f
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
def new_program(b: ProgramIn, u: User = Depends(admin), s: Session = Depends(db)):
    pat = (b.pattern or "semester").strip().lower()
    if pat not in PATTERNS: raise HTTPException(400, "Choose semester or year")
    n = DEFAULT_TERMS[pat] if b.terms is None else b.terms
    if not 0 <= n <= 8: raise HTTPException(400, f"A program can start with 0 to 8 {PATTERNS[pat].lower()}s")
    p = Program(name=program_name(b.name, s), pattern=pat, created_by=u.id); s.add(p); s.flush()
    for i in range(1, n + 1): s.add(Semester(name=f"{PATTERNS[pat]} {i}", program_id=p.id, semester_no=i, created_by=u.id))  # the terms exist from the start, so the admin only has to add courses
    s.commit(); return {"id": p.id, "pattern": pat, "terms": n}
@app.post("/api/semesters")
def new_semester(b: SemesterIn, u: User = Depends(admin), s: Session = Depends(db)):  # older flat form of POST /api/programs/{id}/semesters
    if not s.get(Program, b.program_id): raise HTTPException(400, "Choose a program for this semester")
    return program_semester(b.program_id, NewSemesterIn(name=b.name, semester_no=b.semester_no if b.semester_no is not None else 0), u, s)
@app.post("/api/programs/{pid}/semesters")
def program_semester(pid: int, b: NewSemesterIn, u: User = Depends(admin), s: Session = Depends(db)):  # semesters are made inside a program
    if not s.get(Program, pid): raise HTTPException(404, "No such program")
    return save_row(Semester(name=item_name(b.name, "semester"), program_id=pid, semester_no=sem_number(s, pid, b.semester_no)), u, s)
@app.post("/api/programs/{pid}/semesters/{sid}/courses")
def semester_course(pid: int, sid: int, b: NewCourseIn, u: User = Depends(admin), s: Session = Depends(db)):  # courses are made inside a semester
    sem = s.get(Semester, sid)
    if not sem or sem.program_id != pid: raise HTTPException(404, "That semester is not part of this program")
    co = Course(name=item_name(b.name, "course"), semester_id=sem.id, program_id=sem.program_id); set_owner(s, co, b.faculty_owner_id)
    return save_row(co, u, s)
@app.post("/api/courses")
def new_course(b: CourseIn, u: User = Depends(admin), s: Session = Depends(db)):  # older flat form of POST /api/programs/{id}/semesters/{id}/courses
    sem = s.get(Semester, b.semester_id)
    if not sem: raise HTTPException(400, "Choose a semester for this course")
    return semester_course(sem.program_id, sem.id, NewCourseIn(name=b.name, faculty_owner_id=b.faculty_owner_id), u, s)
@app.post("/api/units")
def new_unit(b: UnitIn, u: User = Depends(staff), s: Session = Depends(db)):
    if not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course for this unit")
    need_edit(u, b.course_id, s)
    return save_row(Unit(name=item_name(b.name, "unit"), course_id=b.course_id, position=next_pos(s, Unit, course_id=b.course_id)), u, s)
@app.post("/api/topics")
def new_topic(b: TopicIn, u: User = Depends(staff), s: Session = Depends(db)):
    f = topic_fields(b, s); need_edit(u, f["course_id"], s)
    t = Topic(**{**f, "published": b.published, "position": next_pos(s, Topic, unit_id=b.unit_id)}); t.created_by = u.id; s.add(t); s.flush()
    record_version(s, t, None, u.id, "Created"); s.commit(); return {"id": t.id}
@app.put("/api/programs/{rid}")
def edit_program(rid: int, b: ProgramIn, _: User = Depends(admin), s: Session = Depends(db)):
    p = s.get(Program, rid)
    if not p: raise HTTPException(404, "Not found")
    vals = {"name": program_name(b.name, s, rid)}
    if b.pattern is not None:
        pat = b.pattern.strip().lower()
        if pat not in PATTERNS: raise HTTPException(400, "Choose semester or year")
        if pat != (p.pattern or "semester"):  # terms still carrying the standard name follow the change; custom names are left alone
            for x in s.query(Semester).filter_by(program_id=rid):
                if re.fullmatch(r"(Semester|Year) \d+", x.name or ""): x.name = f"{PATTERNS[pat]} {x.semester_no}" if x.semester_no else x.name
            vals["pattern"] = pat
    return update(p, vals, s)
@app.put("/api/semesters/{rid}")
def edit_semester(rid: int, b: SemesterIn, _: User = Depends(admin), s: Session = Depends(db)):
    x = s.get(Semester, rid)
    if not x: raise HTTPException(404, "Not found")
    if not s.get(Program, b.program_id): raise HTTPException(400, "Choose a program for this semester")
    n = b.semester_no if "semester_no" in b.dict(exclude_unset=True) else x.semester_no
    vals = {"name": item_name(b.name, "semester"), "program_id": b.program_id, "semester_no": sem_number(s, b.program_id, n, keep=rid) if n is not None else None}
    s.query(Course).filter_by(semester_id=rid).update({"program_id": b.program_id}, synchronize_session=False)  # keep the copied program id in step
    return update(x, vals, s)
@app.put("/api/courses/{rid}")
def edit_course(rid: int, b: CourseIn, _: User = Depends(admin), s: Session = Depends(db)):
    co = s.get(Course, rid)
    if not co: raise HTTPException(404, "Not found")
    if "faculty_owner_id" in b.dict(exclude_unset=True): set_owner(s, co, b.faculty_owner_id)  # moving a course keeps its owner
    f = {**course_fields(b, s), "name": item_name(b.name, "course")}  # program always comes from the new semester
    s.query(CourseLink).filter_by(course_id=rid, semester_id=f["semester_id"]).delete()  # its new home can't also be a shared copy
    return update(co, f, s)
@app.put("/api/units/{rid}")
def edit_unit(rid: int, b: UnitIn, u: User = Depends(staff), s: Session = Depends(db)):
    x = s.get(Unit, rid)
    if not x: raise HTTPException(404, "Not found")
    need_edit(u, x.course_id, s); vals = {"name": item_name(b.name, "unit")}
    if b.course_id != x.course_id:  # moving a unit changes which course it belongs to, which is the admin's call
        if u.role != "admin": raise HTTPException(403, "Only an admin can move a unit to another course")
        if not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course for this unit")
        for m in (Topic, Quiz): s.query(m).filter_by(unit_id=rid).update({"course_id": b.course_id}, synchronize_session=False)  # copies follow
        vals.update(course_id=b.course_id, position=next_pos(s, Unit, course_id=b.course_id))
    return update(x, vals, s)
@app.put("/api/topics/{rid}")
def edit_topic(rid: int, b: TopicIn, u: User = Depends(staff), s: Session = Depends(db)):
    x = s.get(Topic, rid)
    if not x: raise HTTPException(404, "Not found")
    old = topic_course_id(x, s); need_edit(u, old, s)
    f = topic_fields(b, s); need_edit(u, f["course_id"], s)
    if f["course_id"] != old and u.role != "admin": raise HTTPException(403, "A topic can only move to another unit of the same course")
    if f["unit_id"] != x.unit_id: f["position"] = next_pos(s, Topic, unit_id=f["unit_id"])
    before = topic_state(x)
    for k, v in f.items(): setattr(x, k, v)  # published only changes when it is sent: saving content never publishes a draft
    record_version(s, x, before, u.id, "Edited"); s.commit(); return {"ok": True}
def free_name(taken, name, limit):  # "Water", then "Water (copy)", "Water (copy 2)" ... until the name is unused among its siblings
    low = {x.lower() for x in taken}
    if name.lower() not in low: return name
    n = 1
    while True:
        tail = " (copy)" if n == 1 else f" (copy {n})"; cand = name[:limit - len(tail)] + tail
        if cand.lower() not in low: return cand
        n += 1
class CopyIn(BaseModel): unit_id: int | None = None; course_id: int | None = None; with_quizzes: bool = True
def where_is(t, s):
    un = s.get(Unit, t.unit_id) if t.unit_id else None; co = s.get(Course, un.course_id) if un else None
    return f"{co.name if co else '?'} › {un.name if un else '?'}"
@app.post("/api/topics/{tid}/copy")
def copy_topic(tid: int, b: CopyIn, u: User = Depends(staff), s: Session = Depends(db)):
    """A copy of a topic's text in a unit you can edit, as a draft at the end of that unit. Reading progress, bookmarks, deadlines and saved AI answers are not copied."""
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    un = s.get(Unit, b.unit_id) if b.unit_id else None
    if not un: raise HTTPException(400, "Choose the unit to copy it into")
    need_edit(u, un.course_id, s)
    title = free_name([x for (x,) in s.query(Topic.title).filter_by(unit_id=un.id)], t.title, 200)
    n = Topic(title=title, unit_id=un.id, course_id=un.course_id, content=t.content, sample_content=t.sample_content, question_pattern=t.question_pattern, guideline=t.guideline,
              published=False, position=next_pos(s, Topic, unit_id=un.id)); n.created_by = u.id; s.add(n); s.flush()
    record_version(s, n, None, u.id, f"Copied from {where_is(t, s)} › {t.title}"[:200]); s.commit()
    return {"id": n.id, "title": n.title, "unit_id": un.id}
@app.post("/api/units/{uid}/copy")
def copy_unit(uid: int, b: CopyIn, u: User = Depends(staff), s: Session = Depends(db)):
    """A copy of a unit with its topics (and, if you can edit the original course, its quizzes) in a course you can edit. Everything arrives as a draft."""
    src = s.get(Unit, uid)
    if not src: raise HTTPException(404, "Unit not found")
    co = s.get(Course, b.course_id) if b.course_id else None
    if not co: raise HTTPException(400, "Choose the course to copy it into")
    need_edit(u, co.id, s); mine = can_edit(u, src.course_id, s)
    name = free_name([x for (x,) in s.query(Unit.name).filter_by(course_id=co.id)], src.name, 150)
    nu = Unit(name=name, course_id=co.id, position=next_pos(s, Unit, course_id=co.id)); nu.created_by = u.id; s.add(nu); s.flush()
    ids, made = {}, 0
    for t in s.query(Topic).filter_by(unit_id=src.id).order_by(*ORDER.get(Topic, (Topic.id,))):
        if t.published is False and not mine: continue  # someone else's drafts are not yours to take
        n = Topic(title=t.title, unit_id=nu.id, course_id=co.id, content=t.content, sample_content=t.sample_content, question_pattern=t.question_pattern, guideline=t.guideline,
                  published=False, position=next_pos(s, Topic, unit_id=nu.id)); n.created_by = u.id; s.add(n); s.flush(); ids[t.id] = n.id; made += 1
        record_version(s, n, None, u.id, f"Copied from {where_is(t, s)}"[:200])
    quizzes = 0
    if b.with_quizzes and mine:
        for q in s.query(Quiz).filter_by(unit_id=src.id).order_by(Quiz.id):
            nq = Quiz(unit_id=nu.id, course_id=co.id, title=q.title, pass_percent=q.pass_percent, published=False); s.add(nq); s.flush(); quizzes += 1
            for x in s.query(Question).filter_by(quiz_id=q.id).order_by(Question.pos, Question.id):
                s.add(Question(quiz_id=nq.id, pos=x.pos, text=x.text, options=x.options, correct=x.correct, explanation=x.explanation, topic_id=ids.get(x.topic_id)))
    s.commit()
    return {"id": nu.id, "name": nu.name, "topics": made, "quizzes": quizzes}
class OrderIn(BaseModel): ids: list[int]
def reorder(rows, ids):
    if len(ids) != len(set(ids)) or set(ids) != {r.id for r in rows}: raise HTTPException(400, "Send every item exactly once, in the new order")
    pos = {i: n for n, i in enumerate(ids, 1)}
    for r in rows: r.position = pos[r.id]
@app.put("/api/courses/{cid}/units/order")
def order_units(cid: int, b: OrderIn, u: User = Depends(staff), s: Session = Depends(db)):
    if not s.get(Course, cid): raise HTTPException(404, "Course not found")
    need_edit(u, cid, s); reorder(s.query(Unit).filter_by(course_id=cid).all(), b.ids); s.commit(); return {"ok": True}
@app.put("/api/units/{uid}/topics/order")
def order_topics(uid: int, b: OrderIn, u: User = Depends(staff), s: Session = Depends(db)):
    un = s.get(Unit, uid)
    if not un: raise HTTPException(404, "Unit not found")
    need_edit(u, un.course_id, s); reorder(s.query(Topic).filter_by(unit_id=uid).all(), b.ids); s.commit(); return {"ok": True}
# ---- quizzes: staff write them, students take them and are graded on the server ----
class QuizIn(BaseModel): unit_id: int = 0; title: str; pass_percent: int = 50; published: bool = False
class QuestionIn(BaseModel): text: str; options: list[str]; correct: int; explanation: str = ""; topic_id: int | None = None
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
# ---- strengths and weak areas: what a student has mastered, and what needs another round of study ----
STRONG, WEAK = 80, 60  # at or above STRONG is a strength; below WEAK needs another round of study; in between is getting there
def area_status(pct): return "strong" if pct >= STRONG else "needs_study" if pct < WEAK else "getting_there"
def latest_batches(s, user_ids, quiz_ids):
    """Each user's newest attempt of each quiz, so a retake replaces the earlier result. Returns [(user_id, quiz, {question_id: Question}, [[question_id, 1|0], ...])]."""
    if not user_ids or not quiz_ids: return []
    ids = [r[0] for r in s.query(func.max(Attempt.id)).filter(Attempt.user_id.in_(list(user_ids)), Attempt.quiz_id.in_(list(quiz_ids)), Attempt.detail.isnot(None)).group_by(Attempt.user_id, Attempt.quiz_id)]
    atts = s.query(Attempt).filter(Attempt.id.in_(ids or [0])).all(); quizzes = {q.id: q for q in s.query(Quiz).filter(Quiz.id.in_({a.quiz_id for a in atts} or {0}))}
    qm = defaultdict(dict)
    for x in s.query(Question).filter(Question.quiz_id.in_(set(quizzes) or {0})): qm[x.quiz_id][x.id] = x
    return [(a.user_id, quizzes[a.quiz_id], qm[a.quiz_id], json.loads(a.detail)) for a in atts if a.quiz_id in quizzes]
def area_context(batches, s):
    tids = {x.topic_id for _, _, qm, _ in batches for x in qm.values() if x.topic_id}; uids = {q.unit_id for _, q, _, _ in batches}
    topics = {t.id: t for t in s.query(Topic).filter(Topic.id.in_(tids or {0}))}; units = {x.id: x for x in s.query(Unit).filter(Unit.id.in_(uids or {0}))}
    courses = {c.id: c.name for c in s.query(Course).filter(Course.id.in_({x.course_id for x in units.values()} or {0}))}
    return topics, units, courses
def tally(batches, ctx, staff):
    """Groups one person's answers by topic; a question with no topic (or whose topic is a draft they can't see, was deleted or moved) counts under its unit."""
    topics, units, courses = ctx; acc = {}
    for _, q, qm, detail in batches:
        un = units.get(q.unit_id)
        for qid, ok in detail:
            x = qm.get(qid)
            if not x: continue
            t = topics.get(x.topic_id) if x.topic_id else None
            if t and (t.unit_id != q.unit_id or (t.published is False and not staff)): t = None
            key = ("t", t.id) if t else ("u", q.unit_id)
            a = acc.setdefault(key, {"key": key, "topic_id": t.id if t else None, "unit_id": q.unit_id, "unit": un.name if un else "", "course_id": un.course_id if un else None,
                                     "course": courses.get(un.course_id, "") if un else "", "title": t.title if t else ((un.name + " · general questions") if un else q.title), "correct": 0, "total": 0})
            a["correct"] += ok; a["total"] += 1
    for a in acc.values(): a["percent"] = round(100 * a["correct"] / a["total"]); a["status"] = area_status(a["percent"])
    return acc
def areas_for(batches, s, staff, uid=None):
    ctx = area_context(batches, s); acc = tally(batches, ctx, staff)
    study = {}
    if uid and acc:
        for r in s.query(Progress).filter(Progress.user_id == uid, Progress.topic_id.in_([a["topic_id"] for a in acc.values() if a["topic_id"]] or [0])): study[r.topic_id] = "completed" if r.completed_at else "in_progress"
    out = [{k: v for k, v in a.items() if k != "key"} | {"study": (study.get(a["topic_id"], "not_started") if uid else None) if a["topic_id"] else None} for a in acc.values()]
    return sorted(out, key=lambda a: (a["percent"], a["title"]))
@app.get("/api/me/insights")
def my_insights(u: User = Depends(me), s: Session = Depends(db)):
    ok_course = {}
    def allowed(cid):
        if cid not in ok_course:
            try: check_course_access(u, cid, s); ok_course[cid] = True
            except HTTPException: ok_course[cid] = False
        return ok_course[cid]
    qs = [(q, quiz_course_id(q, s)) for q in s.query(Quiz).filter(Quiz.published == True, Quiz.id.in_(s.query(Attempt.quiz_id).filter(Attempt.user_id == u.id)))]  # noqa: E712
    qids = [q.id for q, cid in qs if cid and allowed(cid)]
    areas = areas_for(latest_batches(s, [u.id], qids), s, u.role != "student", u.id)
    by = defaultdict(list)
    for a in areas: by[a["course_id"]].append(a)
    courses = [{"course_id": cid, "course": L[0]["course"], "percent": round(100 * sum(a["correct"] for a in L) / sum(a["total"] for a in L)), "areas": L} for cid, L in by.items()]
    return {"quizzes_taken": len(qids), "courses": courses, "strong": sorted([a for a in areas if a["status"] == "strong"], key=lambda a: (-a["percent"], a["title"])),
            "getting_there": [a for a in areas if a["status"] == "getting_there"], "needs_study": [a for a in areas if a["status"] == "needs_study"]}
def course_quiz_ids(cid, s): return [q.id for q in s.query(Quiz).join(Unit, Unit.id == Quiz.unit_id).filter(Unit.course_id == cid, Quiz.published == True)]  # noqa: E712
def course_users(c, s):
    sems = {x.id: x for x in s.query(Semester)}; links = defaultdict(list)
    for l in s.query(CourseLink).filter_by(course_id=c.id): links[c.id].append(l.semester_id)
    return course_audience(c, s.query(User).filter_by(role="student").all(), sems, links)
@app.get("/api/reports/courses/{cid}/weak-areas")
def class_weak_areas(cid: int, u: User = Depends(staff), s: Session = Depends(db)):
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    aud = [x for x in course_users(c, s) if x.active]; batches = latest_batches(s, [x.id for x in aud], course_quiz_ids(cid, s)); ctx = area_context(batches, s)
    per = defaultdict(list)
    for b in batches: per[b[0]].append(b)
    agg = {}
    for uid, bs in per.items():
        for key, a in tally(bs, ctx, True).items():
            g = agg.setdefault(key, {**{k: v for k, v in a.items() if k not in ("key", "status", "percent")}, "correct": 0, "total": 0, "students": 0, "strong": 0, "getting_there": 0, "needs_study": 0})
            g["correct"] += a["correct"]; g["total"] += a["total"]; g["students"] += 1; g[a["status"]] += 1
    rows = sorted(agg.values(), key=lambda g: (round(100 * g["correct"] / g["total"]), g["title"]))
    return {"course": c.name, "students_with_results": len(per), "areas": [{**g, "percent": round(100 * g["correct"] / g["total"])} for g in rows]}
@app.post("/api/quizzes")
def new_quiz(b: QuizIn, u: User = Depends(staff), s: Session = Depends(db)):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this quiz")
    need_edit(u, un.course_id, s); q = Quiz(unit_id=un.id, course_id=un.course_id, **quiz_fields(b)); s.add(q); s.commit(); return {"id": q.id}
@app.put("/api/quizzes/{qid}")
def edit_quiz(qid: int, b: QuizIn, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, quiz_course_id(q, s), s)
    for k, v in quiz_fields(b).items(): setattr(q, k, v)
    s.commit(); return {"ok": True}
@app.delete("/api/quizzes/{qid}")
def delete_quiz(qid: int, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, quiz_course_id(q, s), s); drop_quizzes(s, Quiz.id == qid); s.commit(); return {"ok": True}
@app.put("/api/quizzes/{qid}/questions")
def set_questions(qid: int, b: QuestionsIn, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, quiz_course_id(q, s), s)
    if len(b.questions) > 100: raise HTTPException(400, "A quiz can have up to 100 questions")
    for i, x in enumerate(b.questions, 1):
        opts = [o.strip() for o in x.options]
        if not x.text.strip(): raise HTTPException(400, f"Question {i} has no text")
        if not 2 <= len(opts) <= 6 or not all(opts): raise HTTPException(400, f"Question {i} needs 2 to 6 answers, none empty")
        if not 0 <= x.correct < len(opts): raise HTTPException(400, f"Question {i}: mark which answer is correct")
        if x.topic_id is not None and not s.query(Topic.id).filter(Topic.id == x.topic_id, Topic.unit_id == q.unit_id).first(): raise HTTPException(400, f"Question {i}: pick a topic from this unit")
    s.query(Question).filter_by(quiz_id=qid).delete()
    for i, x in enumerate(b.questions):
        s.add(Question(quiz_id=qid, pos=i, text=x.text.strip(), options=json.dumps([o.strip() for o in x.options]), correct=x.correct, explanation=x.explanation.strip(), topic_id=x.topic_id))
    s.commit(); return {"ok": True, "count": len(b.questions)}
# ---- shared question bank ----
def q_sig(text, opts, correct): return hashlib.sha1(json.dumps([text.strip().lower(), [o.strip().lower() for o in opts], correct]).encode()).hexdigest()
def check_question(x, label="Question"):
    opts = [o.strip() for o in x.options]
    if not x.text.strip(): raise HTTPException(400, f"{label} has no text")
    if not 2 <= len(opts) <= 6 or not all(opts): raise HTTPException(400, f"{label} needs 2 to 6 answers, none empty")
    if not 0 <= x.correct < len(opts): raise HTTPException(400, f"{label}: mark which answer is correct")
    return opts
def clean_tags(t): return ", ".join(dict.fromkeys(w.strip().lower()[:30] for w in (t or "").split(",") if w.strip()))[:200]
class BankIn(BaseModel): text: str; options: list[str]; correct: int; explanation: str = ""; tags: str = ""; source: str = ""
def bank_row(x, owners, u): return {"id": x.id, "text": x.text, "options": json.loads(x.options), "correct": x.correct, "explanation": x.explanation or "", "tags": [t for t in (x.tags or "").split(", ") if t],
    "source": x.source or "", "uses": x.uses or 0, "owner": owners.get(x.owner_id, ""), "mine": x.owner_id == u.id, "can_edit": u.role == "admin" or x.owner_id == u.id}
def add_to_bank(s, u, text, opts, correct, explanation, tags, source):
    sig = q_sig(text, opts, correct)
    if s.query(BankQuestion.id).filter_by(sig=sig).first(): return False
    s.add(BankQuestion(owner_id=u.id, sig=sig, text=text.strip(), options=json.dumps(opts), correct=correct, explanation=(explanation or "").strip(), tags=clean_tags(tags), source=(source or "")[:200])); return True
@app.get("/api/bank")
def bank_list(q: str = "", tag: str = "", mine: bool = False, limit: int = 30, offset: int = 0, u: User = Depends(staff), s: Session = Depends(db)):
    qs = s.query(BankQuestion)
    if mine: qs = qs.filter(BankQuestion.owner_id == u.id)
    if tag.strip(): qs = qs.filter(BankQuestion.tags.like("%" + tag.strip().lower().replace("%", "") + "%"))
    for w in q.split()[:6]:
        like = "%" + w.replace("%", "").replace("_", " ").strip() + "%"; qs = qs.filter(or_(BankQuestion.text.like(like), BankQuestion.tags.like(like), BankQuestion.source.like(like)))
    total = qs.count(); rows = qs.order_by(BankQuestion.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    owners = {x.id: x.name for x in s.query(User).filter(User.id.in_({r.owner_id for r in rows if r.owner_id} or {0}))}
    alltags = sorted({t for (v,) in s.query(BankQuestion.tags) for t in (v or "").split(", ") if t})[:200]
    return {"total": total, "items": [bank_row(x, owners, u) for x in rows], "tags": alltags}
@app.post("/api/bank")
def bank_add(b: BankIn, u: User = Depends(staff), s: Session = Depends(db)):
    opts = check_question(b); ok = add_to_bank(s, u, b.text, opts, b.correct, b.explanation, b.tags, b.source); s.commit()
    if not ok: raise HTTPException(409, "That exact question is already in the bank")
    return {"ok": True}
def bank_or_404(bid, u, s):
    x = s.get(BankQuestion, bid)
    if not x: raise HTTPException(404, "Question not found")
    return x
@app.put("/api/bank/{bid}")
def bank_edit(bid: int, b: BankIn, u: User = Depends(staff), s: Session = Depends(db)):
    x = bank_or_404(bid, u, s)
    if not (u.role == "admin" or x.owner_id == u.id): raise HTTPException(403, "Only the person who added a question, or an admin, can change it")
    opts = check_question(b); sig = q_sig(b.text, opts, b.correct)
    if s.query(BankQuestion.id).filter(BankQuestion.sig == sig, BankQuestion.id != bid).first(): raise HTTPException(409, "That exact question is already in the bank")
    x.text, x.options, x.correct, x.explanation, x.tags, x.sig = b.text.strip(), json.dumps(opts), b.correct, b.explanation.strip(), clean_tags(b.tags), sig
    if b.source.strip(): x.source = b.source.strip()[:200]
    s.commit(); return {"ok": True}
@app.delete("/api/bank/{bid}")
def bank_delete(bid: int, u: User = Depends(staff), s: Session = Depends(db)):
    x = bank_or_404(bid, u, s)
    if not (u.role == "admin" or x.owner_id == u.id): raise HTTPException(403, "Only the person who added a question, or an admin, can delete it")
    s.delete(x); s.commit(); return {"ok": True}
class FromQuiz(BaseModel): tags: str = ""
@app.post("/api/bank/from-quiz/{qid}")
def bank_from_quiz(qid: int, b: FromQuiz, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); cid = quiz_course_id(q, s); need_edit(u, cid, s); course = s.get(Course, cid); added = skipped = 0
    for x in s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id):
        if add_to_bank(s, u, x.text, json.loads(x.options), x.correct, x.explanation, b.tags, (course.name if course else "") + " · " + q.title): added += 1
        else: skipped += 1
    s.commit(); return {"added": added, "skipped": skipped}
class FromBank(BaseModel): ids: list[int]; topic_id: int | None = None
@app.post("/api/quizzes/{qid}/questions/from-bank")
def questions_from_bank(qid: int, b: FromBank, u: User = Depends(staff), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); need_edit(u, quiz_course_id(q, s), s)
    ids = list(dict.fromkeys(b.ids))
    if not ids: raise HTTPException(400, "Choose at least one question")
    have = s.query(Question).filter_by(quiz_id=qid).count()
    if have + len(ids) > 100: raise HTTPException(400, "A quiz can have up to 100 questions")
    if b.topic_id is not None and not s.query(Topic.id).filter(Topic.id == b.topic_id, Topic.unit_id == q.unit_id).first(): raise HTTPException(400, "Pick a topic from this unit")
    rows = {x.id: x for x in s.query(BankQuestion).filter(BankQuestion.id.in_(ids))}
    if len(rows) != len(ids): raise HTTPException(404, "Some of those questions are no longer in the bank")
    for i, bid in enumerate(ids):
        x = rows[bid]; x.uses = (x.uses or 0) + 1
        s.add(Question(quiz_id=qid, pos=have + i, text=x.text, options=x.options, correct=x.correct, explanation=x.explanation, topic_id=b.topic_id))
    s.commit(); return {"ok": True, "count": have + len(ids)}
@app.get("/api/quizzes/{qid}")
def get_quiz(qid: int, u: User = Depends(me), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); cid = quiz_course_id(q, s); staff_view = u.role == "admin" or (u.role == "faculty" and can_edit(u, cid, s))
    if not staff_view:
        if not q.published: raise HTTPException(404, "Quiz not found")
        check_course_access(u, cid, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    mine = s.query(Attempt).filter_by(quiz_id=qid, user_id=u.id).all()
    return {"id": q.id, "title": q.title, "pass_percent": q.pass_percent, "published": bool(q.published), "unit_id": q.unit_id, "can_edit": staff_view,
            "questions": [{"id": x.id, "text": x.text, "options": json.loads(x.options), **({"correct": x.correct, "explanation": x.explanation, "topic_id": x.topic_id} if staff_view else {})} for x in qs],
            **({"topics": [{"id": t.id, "title": t.title} for t in s.query(Topic).filter_by(unit_id=q.unit_id).order_by(*ORDER[Topic])]} if staff_view else {}),
            "attempts": len(mine), "best": max([a.percent for a in mine], default=None)}
@app.post("/api/quizzes/{qid}/attempt")
def attempt_quiz(qid: int, b: AttemptIn, u: User = Depends(me), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); cid = quiz_course_id(q, s)
    if not q.published and not (u.role == "admin" or can_edit(u, cid, s)): raise HTTPException(404, "Quiz not found")
    check_course_access(u, cid, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    if not qs: raise HTTPException(400, "This quiz has no questions yet")
    if len(b.answers) != len(qs): raise HTTPException(400, "Answer every question or leave it blank")
    key = u.role == "admin" or can_edit(u, cid, s)  # only people who can edit the quiz get the answer key back
    results = [{"chosen": a, "ok": a == x.correct, **({"correct": x.correct, "explanation": x.explanation} if key else {})} for a, x in zip(b.answers, qs)]
    score = sum(r["ok"] for r in results); pct = round(100 * score / len(qs))
    detail = [[x.id, int(r["ok"])] for x, r in zip(qs, results)]
    s.add(Attempt(quiz_id=qid, user_id=u.id, score=score, total=len(qs), percent=pct, detail=json.dumps(detail))); s.commit()
    areas = areas_for([(u.id, q, {x.id: x for x in qs}, detail)], s, u.role != "student", u.id)
    return {"score": score, "total": len(qs), "percent": pct, "passed": pct >= q.pass_percent, "pass_percent": q.pass_percent, "results": results, "areas": areas}

def drop_topics(s, cond):  # topics with their reading progress, bookmarks and saved AI answers (SQLite would not cascade them)
    ids = [i for (i,) in s.query(Topic.id).filter(cond)]
    if ids:
        for m in (Progress, Bookmark, AICache, TopicVersion): s.query(m).filter(m.topic_id.in_(ids)).delete(synchronize_session=False)
        s.query(Topic).filter(Topic.id.in_(ids)).delete(synchronize_session=False)
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
    else: need_edit(u, r.course_id if kind == "units" else topic_course_id(r, s), s)
    # MariaDB cascades deletes along topics.subject_id and subjects.course_id too, so a stale copy would take rows that now live elsewhere
    if kind in ("programs", "semesters", "courses"): resync_parent_copies(s.connection())
    def drop_course(c):  # children are found through their real parents, never through the copied course/program ids
        uids = [i for (i,) in s.query(Unit.id).filter_by(course_id=c.id)] or [0]
        drop_quizzes(s, Quiz.unit_id.in_(uids)); s.query(CourseLink).filter_by(course_id=c.id).delete(); s.query(CourseFaculty).filter_by(course_id=c.id).delete()
        drop_topics(s, or_(Topic.unit_id.in_(uids), and_(Topic.unit_id.is_(None), Topic.course_id == c.id)))
        s.query(Unit).filter_by(course_id=c.id).delete(); s.delete(c)
    if kind == "programs":
        sids = [i for (i,) in s.query(Semester.id).filter_by(program_id=rid)] or [0]
        for c in s.query(Course).filter(or_(Course.semester_id.in_(sids), and_(Course.semester_id.is_(None), Course.program_id == rid))).all(): drop_course(c)
        s.query(CourseLink).filter(CourseLink.semester_id.in_(s.query(Semester.id).filter_by(program_id=rid))).delete(synchronize_session=False)
        s.query(Semester).filter_by(program_id=rid).delete()
        s.query(User).filter_by(program_id=rid).update({"program_id": None})
    if kind == "semesters":
        s.query(CourseLink).filter_by(semester_id=rid).delete()
        for c in s.query(Course).filter_by(semester_id=rid).all(): drop_course(c)
    if kind == "courses": drop_course(r); r = None
    if kind == "units": drop_quizzes(s, Quiz.unit_id == rid); drop_topics(s, Topic.unit_id == rid)
    if kind == "topics": drop_topics(s, Topic.id == rid); r = None
    if r is not None: s.delete(r)
    s.commit(); return {"ok": True}

# ---- CSV import (admin) ----
LEVELS = ["program", "semester", "course", "unit"]
TEXT_COLS = ["content", "question_pattern", "sample_content", "guideline"]
ALIAS = {"sem_no": "semester_no", "semester_number": "semester_no", "title": "topic", "topic_title": "topic", "notes": "content", "topic_content": "content", "answer_guideline": "guideline",
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
    made = {k + "s": 0 for k in cache}; updated = valid = 0; errors = []; warnings = []; carry = {}
    used = defaultdict(set)  # semester numbers already taken in each program
    for x in cache["semester"].values():
        if x.semester_no is not None: used[x.program_id].add(x.semester_no)
    def get(kind, key, make):
        if key not in cache[kind]:
            o = make(); o.created_by = a.id; s.add(o); s.flush(); cache[kind][key] = o; made[kind + "s"] += 1
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
            given = v.get("semester_no", "")
            if given and not (given.isdigit() and 1 <= int(given) <= 8): errors.append({"row": n, "error": "semester_no must be a number from 1 to 8"}); continue
            p = get("program", v["program"].lower(), lambda: Program(name=v["program"], pattern="year" if re.match(r"\s*(year|yr)\b", v["semester"], re.I) else "semester"))
            if (p.id, v["semester"].lower()) not in cache["semester"]:  # a new semester gets semester_no, or else the number in its name, if that is free
                no = int(given) if given else sem_no(v["semester"])
                if given and no in used[p.id]: errors.append({"row": n, "error": f"{v['program']} already has semester {no}"}); continue
                if no in used[p.id] or no is None:
                    warnings.append(f"{v['program']} › {v['semester']} has no semester number yet. Set it under Programs."); no = None
                if no is not None: used[p.id].add(no)
            sm = get("semester", (p.id, v["semester"].lower()), lambda: Semester(name=v["semester"], program_id=p.id, semester_no=no))
            co = get("course", (sm.id, v["course"].lower()), lambda: Course(name=v["course"], semester_id=sm.id, program_id=p.id))
            un = get("unit", (co.id, v["unit"].lower()), lambda: Unit(name=v["unit"], course_id=co.id, position=next_pos(s, Unit, course_id=co.id)))
            vals = {k: v[k] for k in TEXT_COLS if v.get(k)}
            t = cache["topic"].get((un.id, v["topic"].lower()))
            if t:
                before = topic_state(t)
                for k, val in vals.items(): setattr(t, k, val)
                updated += bool(vals); record_version(s, t, before, a.id, "Imported from CSV")
            else:
                nt = get("topic", (un.id, v["topic"].lower()), lambda: Topic(title=v["topic"], unit_id=un.id, course_id=co.id, position=next_pos(s, Topic, unit_id=un.id), **vals))
                record_version(s, nt, None, a.id, "Imported from CSV")
            valid += 1
        s.rollback() if b.dry_run else s.commit()
    except Exception:
        s.rollback(); raise HTTPException(500, "Import failed. Nothing was saved.")
    return {"dry_run": b.dry_run, "rows": len(rows), "valid_rows": valid, "created": made, "updated_topics": updated,
            "error_count": len(errors), "errors": errors[:20], "warnings": warnings[:20]}

def full(t, s):
    co = s.get(Course, topic_course_id(t, s) or t.course_id); sem = s.get(Semester, co.semester_id) if co.semester_id else None
    un = s.get(Unit, t.unit_id) if t.unit_id else None
    return {"id": t.id, "title": t.title, "course_id": co.id, "unit_id": t.unit_id, "unit": un.name if un else "", "course": co.name,
            "semester": sem.name if sem else "", "program": (s.get(Program, sem.program_id if sem else co.program_id) or Program(name="")).name,
            "content": t.content, "sample_content": t.sample_content, "question_pattern": t.question_pattern, "guideline": t.guideline, "published": t.published is not False}
def version_row(v, names, cur): return {"id": v.id, "saved_at": (v.saved_at.isoformat() + "Z") if v.saved_at else None, "by": names.get(v.saved_by) if v.saved_by else None, "note": v.note or "",
                                          "current": all((getattr(v, k) or "") == cur[k] for k in VFIELDS)}
@app.get("/api/topics/{tid}/versions")
def topic_versions(tid: int, u: User = Depends(staff), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    need_edit(u, topic_course_id(t, s), s)
    rows = s.query(TopicVersion).filter_by(topic_id=tid).order_by(TopicVersion.id.desc()).limit(VERSIONS_KEPT).all()
    names = {x.id: x.name for x in s.query(User).filter(User.id.in_({r.saved_by for r in rows if r.saved_by} or {0}))}; cur = topic_state(t)
    return [version_row(v, names, cur) for v in rows]
def version_or_404(vid, u, s):
    v = s.get(TopicVersion, vid); t = s.get(Topic, v.topic_id) if v else None
    if not t: raise HTTPException(404, "Version not found")
    need_edit(u, topic_course_id(t, s), s); return v, t
@app.get("/api/topic-versions/{vid}")
def topic_version(vid: int, u: User = Depends(staff), s: Session = Depends(db)):
    v, t = version_or_404(vid, u, s)
    return {"id": v.id, "topic_id": t.id, "saved_at": (v.saved_at.isoformat() + "Z") if v.saved_at else None, "note": v.note or "", **{k: getattr(v, k) or "" for k in VFIELDS}, "now": topic_state(t)}
@app.post("/api/topic-versions/{vid}/restore")
def restore_topic_version(vid: int, u: User = Depends(staff), s: Session = Depends(db)):  # puts an old text back as the newest version; nothing is lost, the text it replaces stays in the history
    v, t = version_or_404(vid, u, s); before = topic_state(t)
    for k in VFIELDS: setattr(t, k, getattr(v, k) or "")
    if not t.title.strip(): raise HTTPException(400, "That version has no title")
    record_version(s, t, before, u.id, f"Restored the version of {v.saved_at.strftime('%d %b %Y %H:%M') if v.saved_at else 'earlier'} UTC"); s.commit()
    return {"ok": True}
def topic_neighbours(t, edit, s):  # the topics before and after this one in its unit, in the order the course shows them; drafts only for those who can edit
    sibs = [x for x in s.query(Topic).filter(Topic.unit_id == t.unit_id).order_by(*ORDER.get(Topic, (Topic.id,))) if edit or x.published is not False] if t.unit_id else []
    i = next((k for k, x in enumerate(sibs) if x.id == t.id), None)
    if i is None: return {"prev": None, "next": None, "position": None, "total": len(sibs)}
    pick = lambda x: {"id": x.id, "title": x.title}
    return {"prev": pick(sibs[i - 1]) if i > 0 else None, "next": pick(sibs[i + 1]) if i + 1 < len(sibs) else None, "position": i + 1, "total": len(sibs)}
@app.get("/api/topics/{tid}")
def topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    p = s.query(Progress).filter_by(user_id=u.id, topic_id=tid).first()
    edit = can_edit(u, topic_course_id(t, s), s)
    return {**full(t, s), **learning_state(t.learning_due_at, p, dt.datetime.utcnow()), "can_edit": edit, "nav": topic_neighbours(t, edit, s), "bookmarked": s.query(Bookmark).filter_by(user_id=u.id, topic_id=tid).first() is not None}
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
    p = progress_row(s, u.id, tid)  # opening a topic starts it; it never completes it or undoes a completion
    s.query(Progress).filter_by(id=p.id).update({"reads": Progress.reads + 1, "last_read": dt.datetime.utcnow()}, synchronize_session=False); s.commit(); s.refresh(p)
    known = [x.title for x in s.query(Topic).join(Progress, Progress.topic_id == Topic.id)
             .filter(Progress.user_id == u.id, Topic.course_id == t.course_id, Topic.id != tid).limit(8)]
    n = s.query(Progress).filter_by(user_id=u.id).count()
    return {"known": known, "topics_read": n, **learning_state(t.learning_due_at, p, dt.datetime.utcnow())}
@app.put("/api/topics/{tid}/complete")
def complete_topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):  # the student says they have learnt it; repeating it changes nothing
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s); p = progress_row(s, u.id, tid)
    s.query(Progress).filter(Progress.id == p.id, Progress.completed_at.is_(None)).update({"completed_at": dt.datetime.utcnow()}, synchronize_session=False)
    s.commit(); s.refresh(p); return learning_state(t.learning_due_at, p, dt.datetime.utcnow())
@app.delete("/api/topics/{tid}/complete")
def reopen_topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):  # only an explicit undo takes a topic back to in progress
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s); p = progress_row(s, u.id, tid)
    s.query(Progress).filter_by(id=p.id).update({"completed_at": None}, synchronize_session=False); s.commit(); s.refresh(p)
    return learning_state(t.learning_due_at, p, dt.datetime.utcnow())
@app.get("/api/courses/{cid}/progress")
def course_progress(cid: int, u: User = Depends(staff), s: Session = Depends(db)):  # per topic: how many of the course's students completed it, and how many are overdue
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    links = defaultdict(list)
    for l in s.query(CourseLink).filter_by(course_id=cid): links[cid].append(l.semester_id)
    aud = {x.id for x in course_audience(c, s.query(User).filter_by(role="student", active=True).all(), {x.id: x for x in s.query(Semester)}, links)}
    topics = s.query(Topic).join(Unit, Unit.id == Topic.unit_id).filter(Unit.course_id == cid).all()
    done = defaultdict(int)
    if aud and topics:
        for tid, n in s.query(Progress.topic_id, func.count(Progress.id)).filter(Progress.topic_id.in_([x.id for x in topics]), Progress.user_id.in_(aud),
                                                                               Progress.completed_at.isnot(None)).group_by(Progress.topic_id): done[tid] = n
    now = dt.datetime.utcnow()
    return {"students": len(aud), "topics": {x.id: {"completed": done[x.id], "overdue": len(aud) - done[x.id] if x.learning_due_at and x.learning_due_at < now else 0} for x in topics}}

PROMPTS = {
 "explain": ("You are a warm, sharp engineering tutor for a teenage student. Explain the topic clearly with a hook, an everyday analogy, "
             "the core idea step by step, one worked example, and 3 quick recap bullets. Use Markdown, be concise, stay accurate. "
             "Show comparisons, classifications and families of related items as a Markdown table: a header row, a separator row, and every row on its own line."),
 "answer": ("You are an engineering exam coach. Write a model answer that follows the given answer guideline and question pattern exactly "
            "(structure, length, marks split, diagrams to sketch, keywords). Use Markdown (tables, when you use them, with every row on its own line). Mirror the style of the sample content."),
}
@app.get("/api/topics/{tid}/ai/{kind}")
async def ai(tid: int, kind: str, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t or kind not in PROMPTS: raise HTTPException(404, "Not found")
    check_topic_access(u, t, s)
    f = full(t, s)
    ch = hashlib.sha256("|".join([kind, t.title, t.content or "", t.sample_content or "", t.question_pattern or "", t.guideline or ""]).encode()).hexdigest()
    key = key_for(u, s)
    if not key and u.self_registered: raise HTTPException(503, NEEDS_OWN_KEY)
    if not key: raise ai_down(u, "no DeepSeek key is saved. Add one under AI config.")  # without a key AI is off, even for saved answers
    hit = s.query(AICache).filter_by(topic_id=tid, kind=kind, chash=ch).first()
    if hit: hit.hits += 1; s.commit(); return {"text": hit.text, "cached": True}
    msg = f"Program: {f['program']}\nSemester: {f['semester']}\nCourse: {f['course']}\nUnit: {f['unit']}\nTopic: {f['title']}\n\nTopic content:\n{f['content']}\n\n" + (
        "" if kind == "explain" else f"Question pattern:\n{f['question_pattern']}\n\nAnswer guideline:\n{f['guideline']}\n\nSample content:\n{f['sample_content']}\n")
    try: text, tokens = await deepseek(key, setting(s, "model", "deepseek-chat"), [{"role": "system", "content": PROMPTS[kind]}, {"role": "user", "content": msg}], timeout=60)
    except httpx.HTTPStatusError as e:
        log.warning("DeepSeek answered %s", e.response.status_code)
        if u.self_registered: raise HTTPException(503, f"DeepSeek refused your key ({e.response.status_code}). Check it, or your DeepSeek balance, under AI key in the menu.")
        raise ai_down(u, "DeepSeek refused the request (" + str(e.response.status_code) + "). Check the key, model name and balance under AI config.")
    except Exception as e:
        log.warning("DeepSeek call failed: %s", type(e).__name__)
        if u.self_registered: raise HTTPException(503, "DeepSeek did not answer. Try again in a moment.")
        raise ai_down(u, "DeepSeek did not answer.")
    try: s.add(AICache(topic_id=tid, kind=kind, chash=ch, text=text, tokens=tokens)); s.commit()
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
