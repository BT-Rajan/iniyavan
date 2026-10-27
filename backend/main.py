from collections import defaultdict
import anthropic, asyncio, base64, csv, functools, html as htmllib, io, json, logging, os, re, smtplib, subprocess, hashlib, hmac, secrets, threading, time, datetime as dt, httpx, jwt, nh3
from dotenv import load_dotenv
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from guardrails import GUARDRAILS, GUARD_VERSION, SUPPORT, checked, crisis, fence
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, Date, func, or_, and_, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, declarative_base, Session, object_session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
APP_NAME = (os.getenv("APP_NAME") or "Zigora").strip()
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
    semester = Column(Integer, nullable=True)  # current semester, year or grade, 1 to 12
    institution = Column(String(150), nullable=True); id_number = Column(String(60), nullable=True); phone = Column(String(30), nullable=True)  # given at self-registration
    self_registered = Column(Boolean, default=False)  # signed up on their own and verified their email: "lite" on the college's AI key, unless they bring their own key or are made pro
    pro_until = Column(DateTime, nullable=True)  # a self-registered person an admin made "pro": the college's AI key with the usual limits until then
    ai_key = Column(Text, nullable=True)  # their own DeepSeek key, encrypted (see seal); only self-registered users have one
    digest = Column(Boolean, default=False); digest_at = Column(DateTime, nullable=True)
    username = Column(String(40), unique=True, nullable=True)  # sign-in name for a child a parent or teacher created (no email of their own); lower case
    relation = Column(String(10), nullable=True)  # a guardian's relation to the students they manage: "parent" or "teacher"
    level = Column(String(8), nullable=True)  # "school" or "college", chosen at sign-up; a student placed in a program takes it from the program instead
    lang = Column(String(5), nullable=True)  # the language of the app's screens and AI answers for them: en, ar or ta (null = English)  # a daily email of new notifications, if they asked for it; when it last went
class GuardianLink(Base):  # a parent or teacher (role "guardian") and a student they look after; a teacher's invitation waits until the student accepts
    __tablename__ = "guardian_links"
    id = Column(Integer, primary_key=True)
    guardian_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status = Column(String(10), default="active")  # "active", or "invited" until the student accepts
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("guardian_id", "student_id"),)
class PendingRegistration(Base):  # someone who has asked for an account but has not yet entered the emailed code; becomes a User only when they do
    __tablename__ = "pending_registrations"
    id = Column(Integer, primary_key=True); email = Column(String(190), unique=True, index=True)
    name = Column(String(100)); institution = Column(String(150)); id_number = Column(String(60)); phone = Column(String(30)); pw = Column(String(200))
    code_hash = Column(String(64)); attempts = Column(Integer, default=0); sends = Column(Integer, default=1)
    ip = Column(String(64), index=True); created_at = Column(DateTime, default=dt.datetime.utcnow); last_sent_at = Column(DateTime, default=dt.datetime.utcnow); expires_at = Column(DateTime)
    who = Column(String(10), nullable=True); level = Column(String(8), nullable=True)  # student, parent or teacher; school or college
    program_id = Column(Integer, nullable=True); semester = Column(Integer, nullable=True)  # where the student signing up studies
    children = Column(Text, nullable=True)  # a parent's children as JSON: name, username, hashed password, program_id, semester
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
    pattern = Column(String(10), default="semester")  # "semester" (B.E., B.Tech), "year" (annual programs such as M.B.B.S) or "grade" (school, Grade 1 to 12); the terms below are Semester n, Year n or Grade n
    archived_at = Column(DateTime, nullable=True)  # set while this item is archived (hidden from students, nothing deleted); everything under it is archived with it
class Semester(Base):
    __tablename__ = "semesters"
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    program_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    semester_no = Column(Integer, nullable=True)  # the semester's place in its program (1 to 8, or 1 to 12 for grades): decides order and which students see it; never read from the name
    __table_args__ = (UniqueConstraint("program_id", "semester_no", name="uq_semesters_program_no"),)
    archived_at = Column(DateTime, nullable=True)  # set while this item is archived (hidden from students, nothing deleted); everything under it is archived with it
class Course(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True); name = Column(String(150)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    program_id = Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=True)
    faculty_owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # the one faculty member who runs the course; null = not assigned yet
    archived_at = Column(DateTime, nullable=True)  # set while this item is archived (hidden from students, nothing deleted); everything under it is archived with it
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
    archived_at = Column(DateTime, nullable=True)  # set while this item is archived (hidden from students, nothing deleted); everything under it is archived with it
class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True); title = Column(String(200)); created_by = Column("owner_id", Integer, ForeignKey("users.id"))  # who created the row; not an owner
    course_id = Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text); sample_content = Column(Text); question_pattern = Column(Text); guideline = Column(Text)
    content_format = Column(String(10), default="markdown")  # "markdown", or "html" for content uploaded as an HTML file (stored cleaned, never with scripts or styles)
    published = Column(Boolean, default=True)  # drafts are visible to admins and the course's owner only
    position = Column(Integer, nullable=True)  # order within the unit, set by the course's owner
    learning_due_at = Column(DateTime, nullable=True)  # learn-by deadline, a UTC instant like every timestamp here; null = no deadline
    archived_at = Column(DateTime, nullable=True)  # set while this item is archived (hidden from students, nothing deleted); everything under it is archived with it
class TopicVersion(Base):  # a snapshot of a topic's text each time it is saved, so an earlier version can be read and restored
    __tablename__ = "topic_versions"
    id = Column(Integer, primary_key=True); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title = Column(String(200)); content = Column(Text); sample_content = Column(Text); question_pattern = Column(Text); guideline = Column(Text)
    content_format = Column(String(10), default="markdown")
    saved_by = Column(Integer, nullable=True); saved_at = Column(DateTime, default=dt.datetime.utcnow); note = Column(String(200), default="")
class Quiz(Base):  # a multiple-choice quiz attached to a unit, or an MCQ test for a whole course (unit_id null; course_id is then its real parent)
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True); unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), index=True, nullable=True); course_id = Column(Integer, index=True)
    title = Column(String(200)); pass_percent = Column(Integer, default=50); published = Column(Boolean, default=False)
    reveal = Column(Boolean, default=False)  # students see the correct answers and explanations after submitting
class Question(Base):
    __tablename__ = "quiz_questions"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); pos = Column(Integer, default=0)
    text = Column(Text); options = Column(Text); correct = Column(Integer); explanation = Column(Text)  # options is a JSON list
    topic_id = Column(Integer, nullable=True)  # the topic this question tests, chosen by the author; must be a topic of the quiz's unit (or course, for a course test)
    area = Column(String(150), nullable=True)  # a skill or area label for questions not tied to a topic; strengths are grouped by it
    image = Column(String(300), nullable=True); option_images = Column(Text, nullable=True)  # uploaded image urls: one for the question, a JSON list matching options
class BankQuestion(Base):  # a reusable question any faculty member or admin can browse and add to their own quizzes; adding copies it, so later edits never change a live quiz
    __tablename__ = "question_bank"
    id = Column(Integer, primary_key=True); owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True); sig = Column(String(40), index=True)
    text = Column(Text); options = Column(Text); correct = Column(Integer); explanation = Column(Text); tags = Column(String(200), default=""); source = Column(String(200), default="")
    uses = Column(Integer, default=0); created_at = Column(DateTime, default=dt.datetime.utcnow)
class SearchAnswer(Base):  # a saved AI answer to a student's search, shared by everyone who asks the same thing; the key includes the prompt, so editing the prompt starts afresh
    __tablename__ = "search_answers"
    id = Column(Integer, primary_key=True); qhash = Column(String(64), unique=True); query = Column(String(200)); text = Column(Text)
    tokens = Column(Integer, default=0); hits = Column(Integer, default=0); created_at = Column(DateTime, default=dt.datetime.utcnow)
    author_id = Column(Integer, nullable=True, index=True)  # the student whose search first brought this answer (for rewards; never shown to others)
class SearchLog(Base):  # one row per search that actually went to the AI provider; used for the daily limit
    __tablename__ = "search_log"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    refresh = Column(Boolean, default=False); query = Column(String(200)); tokens = Column(Integer, default=0)
class ActivityDay(Base):  # one row per student per local day they opened topics; with completions and quiz attempts it makes the study streak
    __tablename__ = "activity_days"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); day = Column(Date); reads = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)
class LiteUse(Base):  # a lite (self-registered) person's free AI use on one local day: searches asked and minutes spent learning with AI
    __tablename__ = "lite_use"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); day = Column(Date)
    searches = Column(Integer, default=0); minutes = Column(Integer, default=0); last_min = Column(Integer, default=0)  # last_min: the minute (since 1970) last counted
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_lite_user_day"),)
class MoreRequest(Base):  # a lite person asking the admin for more AI; closed when an admin makes them pro (or they bring their own key)
    __tablename__ = "more_requests"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    note = Column(String(300), nullable=True); at = Column(DateTime, default=dt.datetime.utcnow); done_at = Column(DateTime, nullable=True)
class Routine(Base):  # when and how long a student studies; each day's plan is worked out from it
    __tablename__ = "routines"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    days = Column(String(7), default="1111110")  # Monday..Sunday, 1 = a study day
    minutes = Column(Integer, default=30); at = Column(String(5), nullable=True)  # minutes per session; "19:30" (student's day clock), only to say when it is due
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    started_at = Column(DateTime, nullable=True, default=dt.datetime.utcnow)  # when the routine was set up; days before it are never "missed"
class DaySession(Base):  # one day's session, fixed when it is first made so that finishing a topic doesn't add another one
    __tablename__ = "day_sessions"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); day = Column(Date)
    items = Column(Text, default="[]"); done_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_day_session"),)
class Attempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True); user_id = Column(Integer, ForeignKey("users.id"), index=True)
    score = Column(Integer); total = Column(Integer); percent = Column(Integer); at = Column(DateTime, default=dt.datetime.utcnow)
    detail = Column(Text, nullable=True)  # JSON [[question_id, 1 or 0, chosen index or null], ...] (older rows have no chosen index) so strengths and weak areas can be worked out; null on attempts made before this existed
class Progress(Base):  # one row per student and topic, made when they first open it. No row = not started; completed_at null = in progress
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id")); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    reads = Column(Integer, default=1); last_read = Column(DateTime, default=dt.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)  # set when the student marks the topic completed (UTC); cleared only if they undo it
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
class Highlight(Base):  # a passage someone marked in a topic's content; found again by its text and the words just before it
    __tablename__ = "highlights"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    text = Column(Text); prefix = Column(String(200), default=""); created = Column(DateTime, default=dt.datetime.utcnow)
    color = Column(String(10), nullable=True); note = Column(Text, nullable=True)  # one of HL_COLORS (null = coral); the reader's own note on it
class TopicStore(Base):  # what an interactive page keeps in localStorage for one person; the sandbox has no storage, so the page's writes come here
    __tablename__ = "topic_stores"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True); data = Column(Text); updated = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
class AIFlag(Base):  # a student's private "this looks wrong" on an AI reply; the topic's teachers (or an admin, for searches) see it without the student's name
    __tablename__ = "ai_flags"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    source = Column(String(8)); kind = Column(String(10)); ref = Column(Integer, nullable=True)  # "topic" (an ai_cache row) or "search" (a search_answers row), and which
    excerpt = Column(Text); reason = Column(String(300), nullable=True); status = Column(String(10), default="open", index=True); at = Column(DateTime, default=dt.datetime.utcnow)
class StepLog(Base):  # what a student does with a topic's short steps (a step opened, or "I had it" / "Not quite" on a quick check); private to them, used only to adapt the steps
    __tablename__ = "step_log"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True); kind = Column(String(10)); outcome = Column(String(8), nullable=True)
    at = Column(DateTime, default=dt.datetime.utcnow)
class NoteSeen(Base):  # a notification someone has already seen, by its key, so the bell counts only new ones
    __tablename__ = "notes_seen"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); key = Column(String(120)); at = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "key"),)
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
    author_id = Column(Integer, nullable=True, index=True)  # for a highlight explanation: the student who highlighted it first (rewards only)
    __table_args__ = (UniqueConstraint("topic_id", "kind", "chash"),)
class PrivateAnswer(Base):  # an AI answer written for one student from their own notes: sent once, then shown from here, so showing it again sends nothing
    __tablename__ = "private_answers"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    kind = Column(String(10)); chash = Column(String(64)); text = Column(Text); created_at = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id", "kind", "chash"),)
class DoubtAnswer(Base):  # the AI's answer to a doubt, kept so the same doubt is never sent twice; it holds only the phrase and the labels it was asked with
    __tablename__ = "doubt_answers"
    id = Column(Integer, primary_key=True); qhash = Column(String(64), unique=True); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    phrase = Column(String(300)); text = Column(Text); tokens = Column(Integer, default=0); hits = Column(Integer, default=0); created_at = Column(DateTime, default=dt.datetime.utcnow)
    author_id = Column(Integer, nullable=True, index=True)  # the student who asked this doubt first (rewards only)
class ShareUse(Base):  # someone else was shown an answer a student first asked for: at most one row per answer, person and day. Rewards count these.
    __tablename__ = "share_uses"
    id = Column(Integer, primary_key=True); author_id = Column(Integer, index=True); viewer_id = Column(Integer)
    source = Column(String(8)); ref = Column(Integer); day = Column(Date)
    __table_args__ = (UniqueConstraint("source", "ref", "viewer_id", "day"),)
class AIEgress(Base):  # one row for every request that left for the AI provider: what kind, about which topic, how many characters, and whether it was answered. Never the text itself.
    __tablename__ = "ai_egress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, index=True); kind = Column(String(20)); topic_id = Column(Integer, nullable=True)
    chars = Column(Integer, default=0); ok = Column(Boolean, default=True); at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    tokens = Column(Integer, default=0); own = Column(Boolean, default=False)  # tokens the provider billed; own = paid with the person's own key, not the college's

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
    if claims.get("use"): raise HTTPException(401, "Please sign in again")  # a pass for one topic's frame is not a sign-in
    u = s.get(User, uid)
    if not u or not u.active: raise HTTPException(401, "Account disabled. Ask your admin.")
    if claims.get("k") != fp(u): raise HTTPException(401, "Your password changed. Please sign in again.")
    if u.must_change and request.url.path not in ("/api/me", "/api/me/password"): raise HTTPException(403, "Please set a new password first")
    return u
def admin(u: User = Depends(me)):
    if u.role != "admin": raise HTTPException(403, "Admins only")
    return u
def is_staff(u): return u.role in ("admin", "faculty")  # everyone else (students, parents, teachers who signed up) sees only their own program and has the daily AI limits
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
app.add_middleware(GZipMiddleware, minimum_size=1000)  # the app bundle is ~850 KB; compressed it is about a quarter of that
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
       "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
FRAME_PATH = re.compile(r"^/api/(topics/\d+/frame|frame-preview/[\w-]+)$")
SKIP_AUDIT = re.compile(r"/(read|bookmark|attempt|complete)$|/ai/|^/api/me/lang$")  # student reading activity is already tracked as progress; a language choice is only a preference
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
    if FRAME_PATH.match(request.url.path): r.headers["X-Content-Type-Options"] = "nosniff"; return r  # an interactive topic sets its own sandbox headers
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin", "Content-Security-Policy": CSP,
                      "Permissions-Policy": "camera=(), microphone=(), geolocation=()"})
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https": r.headers["Strict-Transport-Security"] = "max-age=31536000"
    p = request.url.path
    if not p.startswith("/api/") and "cache-control" not in r.headers:  # the screens: built files carry a hash in their name and never change;
        r.headers["Cache-Control"] = "public, max-age=31536000, immutable" if "/assets/" in p else "no-cache"  # the page, sw.js and icons are checked on every load, so an update shows at once
    return r

@app.get("/api/config")
def config(s: Session = Depends(db)): return {"self_registration": reg_open(s), "name": setting(s, "app_name", APP_NAME), "logo": setting(s, "logo_url", "") or None, "version": VERSION, "email_reset": mail_on(s)}
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
# ---- email: password resets, registration codes and daily summaries ----
# The sender is set up in the app (Settings > Email) with a Gmail address and a Google App Password, sealed like the students' AI keys.
# A server set up before that keeps working from SMTP_* in .env; a Gmail account saved in the app takes over from it.
# Links in emails use the site address saved in the app, or APP_URL from .env: never the request's Host header, so a forged
# request can't make a reset link point somewhere else.
from email.utils import formataddr
GMAIL_HOST, GMAIL_PORT = "smtp.gmail.com", 587
class MailLog(Base):  # what was sent, to whom and whether it went: never the text, which can hold a reset link or a code
    __tablename__ = "mail_log"
    id = Column(Integer, primary_key=True); at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    kind = Column(String(20)); to = Column(String(190)); ok = Column(Boolean, default=True); error = Column(String(300), nullable=True)
MAIL_KINDS = {"reset": "Password reset", "code": "Registration code", "account": "Already registered", "digest": "Daily summary", "test": "Test", "pro": "More AI given"}
class MailError(Exception): pass  # a message written for the admin
def site_url(s): return (setting(s, "app_url") or os.getenv("APP_URL") or "").rstrip("/")
def mail_conf(s):
    """How mail goes out: {"via", "host", "port", "tls", "user", "password", "sender"}, or None when nothing is set up."""
    gm, pw = setting(s, "mail_gmail"), unseal(setting(s, "mail_gmail_pw"))
    if gm and pw: return {"via": "gmail", "host": GMAIL_HOST, "port": GMAIL_PORT, "tls": "starttls", "user": gm, "password": pw, "sender": gm}
    if os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"):
        return {"via": "server", "host": os.getenv("SMTP_HOST"), "port": int(os.getenv("SMTP_PORT") or 587), "tls": (os.getenv("SMTP_TLS") or "starttls").lower(),
                "user": os.getenv("SMTP_USER") or "", "password": os.getenv("SMTP_PASSWORD") or "", "sender": os.getenv("SMTP_FROM")}
    return None
def mail_on(s=None):  # a sender and a site address for the links: without both, the app offers no email features at all
    if s is None:
        with Session_() as s2: return mail_on(s2)
    return bool(mail_conf(s) and site_url(s))
def mail_html(name, body, link):  # the same words as the text part, with the link as a button; inline styles, because mail apps drop style sheets
    paras = "".join(f'<p style="margin:0 0 14px">{htmllib.escape(x).replace(chr(10), "<br>")}</p>' for x in body.strip().split("\n\n") if not (link and x.strip() == link))
    button = (f'<p style="margin:6px 0 20px"><a href="{htmllib.escape(link)}" style="background:#722f99;color:#fff;text-decoration:none;padding:12px 20px;'
              f'border-radius:999px;font-weight:600;display:inline-block">Open {htmllib.escape(name)}</a></p>') if link else ""
    return (f'<div style="font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;color:#1e1626;max-width:560px;margin:0 auto;padding:24px">'
            f'<p style="margin:0 0 20px;font-weight:700;font-size:18px;color:#722f99">{htmllib.escape(name)}</p>{paras}{button}</div>')
def gmail_login_help(e):
    return ("Gmail did not accept the sign-in (" + (getattr(e, "smtp_error", b"") or b"").decode(errors="replace").strip()[:120] + "). Usually: the account's own password was "
            "entered instead of a 16-letter App Password (Google Account > Security > 2-Step Verification > App passwords); 2-Step Verification is off, so App "
            "Passwords aren't available; or Google flagged this server's sign-in: look for a security alert in that Gmail inbox.")
def send_mail(to, subject, body, kind="mail", link=None):
    """Sends one email (plain text with an HTML copy) and records how it went. Raises MailError with a message for the admin."""
    with Session_() as s:
        c, name = mail_conf(s), setting(s, "app_name", APP_NAME)
        if not c: raise MailError("No sender is set up. Add a Gmail account under Settings > Email.")
        m = EmailMessage(); m["From"] = formataddr((name, c["sender"])) if c["via"] == "gmail" else c["sender"]; m["To"], m["Subject"] = to, subject
        m.set_content(body); m.add_alternative(mail_html(name, body, link), subtype="html")
        try:
            with (smtplib.SMTP_SSL(c["host"], c["port"], timeout=20) if c["tls"] == "ssl" else smtplib.SMTP(c["host"], c["port"], timeout=20)) as srv:
                if c["tls"] == "starttls": srv.starttls()
                if c["user"]: srv.login(c["user"], c["password"])
                srv.send_message(m)
        except smtplib.SMTPAuthenticationError as e: err = gmail_login_help(e) if c["via"] == "gmail" else "The mail server did not accept the sign-in. Check SMTP_USER and SMTP_PASSWORD."
        except smtplib.SMTPRecipientsRefused: err = f"The mail server refused the address {to}."
        except smtplib.SMTPException as e: err = f"The mail server refused the email: {str(e)[:160]}"
        except OSError as e: err = f"Could not reach {c['host']}:{c['port']} ({type(e).__name__}). Check the server's internet access."
        else: err = None
        now = dt.datetime.utcnow()
        try:
            s.add(MailLog(kind=kind[:20], to=to[:190], ok=err is None, error=err and err[:300]))
            if err is None: s.merge(Setting(k="mail_ok_at", v=now.isoformat())); s.merge(Setting(k="mail_fails", v="0"))
            else:
                s.merge(Setting(k="mail_fail_at", v=now.isoformat())); s.merge(Setting(k="mail_fail_msg", v=err[:300]))
                s.merge(Setting(k="mail_fails", v=str(int(setting(s, "mail_fails", "0") or 0) + 1)))
            s.commit()
        except Exception: s.rollback()  # the record must never stop an email
        if err: log.warning("%s email to user failed: %s", kind, err[:80]); raise MailError(err)
def deliver_reset(email, name, raw):
    minutes = int(os.getenv("RESET_MINUTES") or 30)
    with Session_() as s: link = f"{site_url(s)}/app/#reset={raw}"
    try: send_mail(email, f"Reset your {APP_NAME} password", f"Hi {name},\n\nSomeone asked to reset the password for your {APP_NAME} account. To choose a new one, open this link within {minutes} minutes:\n\n{link}\n\nIf you didn't ask for this, ignore this email. Your password stays the same.\n", kind="reset", link=link)
    except MailError: pass  # recorded in the email log for the admin; the person sees the same answer either way
def tok_hash(raw): return hashlib.sha256(raw.encode()).hexdigest()
class ForgotIn(BaseModel): email: str
@app.post("/api/forgot")
def forgot(b: ForgotIn, request: Request, bg: BackgroundTasks, s: Session = Depends(db)):
    if not mail_on(s): raise HTTPException(503, "Reset by email isn't set up here. Ask your admin to reset your password.")
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
def reg_open(s): return setting(s, "self_registration") == "1" and mail_on(s)
def allowed_domains(s): return [d for d in re.split(r"[,\s]+", setting(s, "allowed_domains").lower()) if d]
PHONE = re.compile(r"\+?[0-9][0-9 ()\-]{5,24}[0-9]")
IDNUM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ./_\-]{0,58}[A-Za-z0-9]|[A-Za-z0-9]")
def deliver_otp(email, name, code, exists=False):
    try:
        if exists: send_mail(email, f"Your {APP_NAME} account", kind="account", body=f"Hi {name},\n\nSomeone tried to register {email} on {APP_NAME}, but that email already has an account. If it was you, sign in, or use \"Forgot your password?\" on the sign-in page. If it was not you, ignore this message.")
        else: send_mail(email, f"Your {APP_NAME} verification code: {code}", kind="code", body=f"Hi {name},\n\nYour verification code is {code}. It works for {OTP_MINUTES} minutes. Enter it in the app to finish creating your {APP_NAME} account.\n\nIf you did not ask for this, ignore this message; no account is created without the code.")
    except MailError: pass  # recorded in the email log
class ChildIn(BaseModel): name: str; username: str; password: str; program_id: int | None = None; semester: int | None = None
class RegisterIn(BaseModel):  # who and level are new: an older app sends neither and gets the old student sign-up
    name: str; institution: str = ""; id_number: str = ""; email: str; phone: str; password: str
    who: str = "student"; level: str | None = None; program_id: int | None = None; semester: int | None = None; children: list[ChildIn] = []
USERNAME = re.compile(r"[a-z][a-z0-9._-]{2,29}")  # a child's sign-in name: no @, so it never looks like an email
MAX_CHILDREN = 8
def clean_registration(b, s):
    name, inst, idn, email, phone = " ".join(b.name.split()), " ".join(b.institution.split()), " ".join(b.id_number.split()), b.email.strip().lower(), b.phone.strip()
    if not 2 <= len(name) <= 100: raise HTTPException(400, "Enter your full name")
    if b.who not in ("student", "parent", "teacher"): raise HTTPException(400, "Choose who is signing up")
    if b.level is not None and b.level not in ("school", "college"): raise HTTPException(400, "Choose school or college")
    if b.who != "student" and b.level is None: raise HTTPException(400, "Choose school or college")
    if b.who != "parent" and not 2 <= len(inst) <= 150: raise HTTPException(400, "Enter your institution")  # a parent's children each have their own school
    if inst and len(inst) > 150: raise HTTPException(400, "Enter your institution")
    need_id = b.who == "student" and b.level != "school"  # a roll number is for college students; school students and parents may not have one
    if (need_id or idn) and not IDNUM.fullmatch(idn): raise HTTPException(400, "Enter your ID number (letters, numbers, spaces and - / . _ only)")
    if not EMAIL.match(email) or len(email) > 190: raise HTTPException(400, "Enter a valid email")
    if not PHONE.fullmatch(phone) or not 7 <= sum(ch.isdigit() for ch in phone) <= 15: raise HTTPException(400, "Enter a valid phone number, for example +91 98765 43210")
    if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters for the password")
    if b.password.strip().lower() == email: raise HTTPException(400, "Password can't be your email")
    doms = allowed_domains(s)
    if doms and b.who != "parent" and not any(email.endswith("@" + d) or email.endswith("." + d) for d in doms): raise HTTPException(400, "Use your institution email address (" + ", ".join("@" + d for d in doms) + ")")
    return name, inst, idn, email, phone
def open_terms(s, p):  # the semester, year or grade numbers of a program that someone can join now
    return sorted(n for (n,) in s.query(Semester.semester_no).filter(Semester.program_id == p.id, Semester.semester_no.isnot(None), Semester.archived_at.is_(None)))
def check_place(s, level, pid, sem):  # a program of the chosen level and one of its terms; no program means an admin places them later
    if pid is None: return None, None
    p = s.get(Program, pid)
    if not p or p.archived_at is not None or program_level(p) != level: raise HTTPException(400, "Choose a program from the list")
    if sem not in open_terms(s, p): raise HTTPException(400, f"Choose a {term_label(p).lower()} from the list")
    return p.id, sem
def clean_children(b, s):  # a parent adds each child with their own sign-in name and password
    if b.who != "parent": return []
    if not 1 <= len(b.children) <= MAX_CHILDREN: raise HTTPException(400, f"Add between 1 and {MAX_CHILDREN} children")
    out, seen = [], set()
    for c in b.children:
        name, un = " ".join(c.name.split()), c.username.strip().lower()
        if not 2 <= len(name) <= 100: raise HTTPException(400, "Enter each child's name")
        if not USERNAME.fullmatch(un): raise HTTPException(400, f"Usernames are 3 to 30 letters, numbers, dots, dashes or underscores, starting with a letter: {un or '(empty)'}")
        if un in seen or s.query(User.id).filter_by(username=un).first(): raise HTTPException(400, f"The username {un} is taken. Choose another.")
        if len(c.password) < 8: raise HTTPException(400, f"Use at least 8 characters for {name}'s password")
        if c.password.strip().lower() == un: raise HTTPException(400, "A password can't be the username")
        pid, sem = check_place(s, b.level, c.program_id, c.semester)
        seen.add(un); out.append({"name": name, "username": un, "pw": hp(c.password), "program_id": pid, "semester": sem})
    return out
def same_id(s, inst, idn):
    return s.query(User.id).filter(func.lower(User.institution) == inst.lower(), func.lower(User.id_number) == idn.lower()).first() is not None
@app.get("/api/register/status")
def register_status(s: Session = Depends(db)): return {"open": reg_open(s), "domains": allowed_domains(s)}
@app.get("/api/register/options")
def register_options(s: Session = Depends(db)):  # the programs someone signing up can pick, by school or college, with the terms open in each
    out = {"school": [], "college": []}
    if not reg_open(s): return out
    for p in s.query(Program).filter(Program.archived_at.is_(None)).order_by(Program.name):
        terms = open_terms(s, p)
        if terms: out[program_level(p)].append({"id": p.id, "name": p.name, "term": term_label(p), "terms": terms})
    return out
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
    if idn and same_id(s, inst, idn): raise HTTPException(400, "An account already exists for that institution ID. Sign in, or ask your admin.")
    pid, sem = check_place(s, b.level, b.program_id, b.semester) if b.who == "student" and b.level else (None, None)
    kids = clean_children(b, s)
    code = f"{secrets.randbelow(10 ** 6):06d}"; p = s.query(PendingRegistration).filter_by(email=email).first()
    if p:
        if p.last_sent_at and (now - p.last_sent_at).total_seconds() < OTP_COOLDOWN: raise HTTPException(429, "Wait a moment before asking for another code.")
        if p.sends >= OTP_MAX_SENDS: raise HTTPException(429, "Too many codes were requested for this email. Please try again tomorrow.")
        p.sends += 1
    else: p = PendingRegistration(email=email, sends=1, created_at=now); s.add(p)
    p.name, p.institution, p.id_number, p.phone, p.pw = name, inst, idn, phone, hp(b.password)
    p.who, p.level, p.program_id, p.semester, p.children = b.who, b.level, pid, sem, json.dumps(kids) if kids else None; p.code_hash = otp_hash(email, code); p.attempts = 0; p.ip = ip; p.last_sent_at = now
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
    if s.query(User.id).filter_by(email=email).first() or (p.id_number and same_id(s, p.institution, p.id_number)): s.delete(p); s.commit(); raise bad
    kids = json.loads(p.children or "[]")
    for k in kids:  # someone may have taken a username since the code was sent
        if s.query(User.id).filter_by(username=k["username"]).first(): raise HTTPException(400, f"The username {k['username']} was taken meanwhile. Go back, change it and ask for a new code.")
    guardian = (p.who or "student") != "student"
    u = User(name=p.name, email=email, pw=p.pw, role="guardian" if guardian else "student", relation=p.who if guardian else None, level=p.level, active=True, must_change=False,
             institution=p.institution or None, id_number=p.id_number or None, phone=p.phone, self_registered=True,
             program_id=None if guardian else p.program_id, semester=None if guardian else p.semester)
    s.add(u); s.flush()
    for k in kids:  # each child signs in on their own with the username their parent chose
        c = User(name=k["name"], email=None, username=k["username"], pw=k["pw"], role="student", level=p.level, active=True, must_change=False,
                 program_id=k["program_id"], semester=k["semester"], self_registered=True)
        s.add(c); s.flush(); s.add(GuardianLink(guardian_id=u.id, student_id=c.id, status="active"))
    s.delete(p)
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
@app.get("/manifest.json")
@app.get("/app/manifest.json")  # served dynamically so the installed app carries APP_NAME (the app lives under /app/)
def manifest():
    icons = [{"src": "/app/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
             {"src": "/app/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
             {"src": "/app/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    return JSONResponse({"name": APP_NAME, "short_name": APP_NAME[:12], "start_url": "/app/", "scope": "/app/", "display": "standalone", "orientation": "portrait",
                         "background_color": "#f6f4f7", "theme_color": "#722f99", "icons": icons})

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
def mcq_columns(c):  # course-level MCQ tests: images, areas and revealing answers
    _addcol("quizzes", "reveal", "TINYINT(1) NOT NULL DEFAULT 0")(c)
    for col, typ in (("area", "VARCHAR(150) NULL"), ("image", "VARCHAR(300) NULL"), ("option_images", "TEXT NULL")): _addcol("quiz_questions", col, typ)(c)
def content_format_columns(c):  # topics can hold an uploaded HTML file; HTML runs longer, so MariaDB/MySQL get MEDIUMTEXT (16 MB) for the content
    for t in ("topics", "topic_versions"):
        _addcol(t, "content_format", "VARCHAR(10) NOT NULL DEFAULT 'markdown'")(c)
        if c.dialect.name != "sqlite": c.execute(text(f"ALTER TABLE {t} MODIFY content MEDIUMTEXT"))
# Append new migrations at the END. Each runs once, is recorded in schema_migrations, and must be safe to run on a database that already has the change.
def guardian_columns(c):  # sign-in names for children, a guardian's relation, and school or college
    for col, typ in (("username", "VARCHAR(40) NULL"), ("relation", "VARCHAR(10) NULL"), ("level", "VARCHAR(8) NULL")): _addcol("users", col, typ)(c)
    if not any(set(ix.get("column_names") or []) == {"username"} for ix in inspect(c).get_indexes("users") + [dict(column_names=u["column_names"]) for u in inspect(c).get_unique_constraints("users")]):
        c.execute(text("CREATE UNIQUE INDEX ux_users_username ON users (username)"))
MIGRATIONS = [("0001_topics_unit_id", _addcol("topics", "unit_id", "INT NULL")), ("0002_subjects_semester_id", _addcol("subjects", "semester_id", "INT NULL")),
              ("0003_users_program_id", _addcol("users", "program_id", "INT NULL")), ("0004_users_semester", _addcol("users", "semester", "INT NULL")),
              ("0005_users_must_change", _addcol("users", "must_change", "TINYINT(1) NOT NULL DEFAULT 0")), ("0006_topics_published", _addcol("topics", "published", "TINYINT(1) NOT NULL DEFAULT 1")),
              ("0007_repair_parent_copies", repair_parent_copies), ("0008_subjects_faculty_owner_id", add_faculty_owner),
              ("0009_course_owners_from_assignments", owners_from_assignments), ("0010_semesters_semester_no", semester_numbers),
              ("0011_unit_topic_positions", positions), ("0012_learning_deadlines", learning_state_columns),
              ("0013_questions_topic_id", _addcol("quiz_questions", "topic_id", "INT NULL")), ("0014_attempts_detail", _addcol("quiz_attempts", "detail", "TEXT NULL")),
              ("0015_users_self_registration", registration_columns), ("0016_program_pattern", program_pattern),
              ("0017_archive_columns", lambda c: [_addcol(t, "archived_at", "DATETIME NULL")(c) for t in ("courses", "semesters", "subjects", "units", "topics")]),
              ("0018_mcq_tests", mcq_columns), ("0019_topic_content_format", content_format_columns),
              ("0020_practice_on_staff_topics", lambda c: _addcol("study_quizzes", "src_topic_id", "INT NULL")(c) if "study_quizzes" in inspect(c).get_table_names() else None),
              ("0021_routine_started_at", _addcol("routines", "started_at", "DATETIME NULL")),
              ("0022_highlight_colors_and_digest", lambda c: [_addcol(*x)(c) for x in (("highlights", "color", "VARCHAR(10) NULL"), ("highlights", "note", "TEXT NULL"),
                                                                                     ("users", "digest", "TINYINT(1) NOT NULL DEFAULT 0"), ("users", "digest_at", "DATETIME NULL"))]),
              ("0023_users_lang", _addcol("users", "lang", "VARCHAR(5) NULL")),
              ("0024_answer_authors", lambda c: [_addcol(t, "author_id", "INTEGER NULL")(c) for t in ("search_answers", "doubt_answers", "ai_cache")]),
              ("0025_egress_tokens", lambda c: [_addcol("ai_egress", "tokens", "INTEGER NOT NULL DEFAULT 0")(c), _addcol("ai_egress", "own", "BOOLEAN NOT NULL DEFAULT 0")(c)]),
              ("0026_users_pro_until", _addcol("users", "pro_until", "DATETIME NULL")),
              ("0027_users_guardians", guardian_columns),
              ("0028_pending_onboarding", lambda c: [_addcol("pending_registrations", col, typ)(c) for col, typ in (("who", "VARCHAR(10) NULL"), ("level", "VARCHAR(8) NULL"),
                                                     ("program_id", "INTEGER NULL"), ("semester", "INTEGER NULL"), ("children", "TEXT NULL"))])]
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
    spawn(digest_loop)  # daily summaries by email, for those who ask (it checks each time whether email is set up)
    with Session_() as s: s.query(MailLog).filter(MailLog.at < dt.datetime.utcnow() - dt.timedelta(days=90)).delete(); s.commit()
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
def program_level(p): return "school" if p is not None and p.pattern == "grade" else "college"  # school programs count in grades
def stage_of(u):  # school or college: from the program a student is placed in, else what they chose at sign-up; staff have none
    if is_staff(u): return None
    s = object_session(u); p = s.get(Program, u.program_id) if s is not None and u.program_id else None
    return program_level(p) if p is not None else (u.level if u.level in ("school", "college") else None)
def place_line(s, u):  # "B.E. Mechanical · Semester 3", or "" when not placed yet
    p = s.get(Program, u.program_id) if u.program_id else None
    return f"{p.name} · {term_label(p)} {u.semester}" if p and u.semester else (p.name if p else "")
def guardian_students(s, gid, status="active"): return s.query(User).join(GuardianLink, GuardianLink.student_id == User.id).filter(GuardianLink.guardian_id == gid, GuardianLink.status == status).all()
def guardians_of(s, sid, status="active"): return s.query(User).join(GuardianLink, GuardianLink.guardian_id == User.id).filter(GuardianLink.student_id == sid, GuardianLink.status == status).all()
def me_json(u): return {"id": u.id, "name": u.name, "role": u.role, "must_change": bool(u.must_change), "self_registered": bool(u.self_registered), "placed": is_staff(u) or bool(u.program_id), "lang": u.lang or "en",
                     "username": u.username, "relation": u.relation, "level": stage_of(u)}
@app.post("/api/login")
def login(b: Login, request: Request, s: Session = Depends(db)):
    global DUMMY
    email, ip = b.email.strip().lower()[:190], client_ip(request); throttle(s, email, ip)
    u = s.query(User).filter_by(email=email).first() if "@" in email else s.query(User).filter_by(username=email).first()  # a child signs in with the name their parent or teacher gave them
    if DUMMY is None: DUMMY = hp("not-a-real-password")
    if not vp(b.password, u.pw if u else DUMMY) or not u: note_fail(s, email, ip); raise HTTPException(401, "Wrong email or password")
    if not u.active: raise HTTPException(403, "Account disabled. Ask your admin.")
    clear_fails(s, email, ip)
    if stale(u.pw) and not u.must_change: u.pw = hp(b.password); s.commit()  # quietly upgrade old hashes
    return {"token": make_token(u), "user": me_json(u)}
AUDIT_ACTIONS = {"created": ["POST"], "changed": ["PUT", "PATCH"], "deleted": ["DELETE"]}
@app.get("/api/admin/audit")
def audit_list(q: str = "", action: str = "", result: str = "", days: int = 0, sort: str = "newest", format: str = "json", limit: int = 100, offset: int = 0,
               _: User = Depends(admin), s: Session = Depends(db)):
    qy = s.query(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id)
    if q.strip():
        k = f"%{q.strip()}%"; qy = qy.filter(or_(User.email.ilike(k), User.name.ilike(k), AuditLog.path.ilike(k)))
    if action in AUDIT_ACTIONS: qy = qy.filter(AuditLog.method.in_(AUDIT_ACTIONS[action]))
    if result == "ok": qy = qy.filter(AuditLog.status < 400)
    elif result == "failed": qy = qy.filter(AuditLog.status >= 400)
    if days > 0: qy = qy.filter(AuditLog.at >= dt.datetime.utcnow() - dt.timedelta(days=days))
    qy = qy.order_by(AuditLog.id.asc() if sort == "oldest" else AuditLog.id.desc())
    if format == "csv": return csv_response("activity-log.csv", ["When (UTC)", "Person", "Email", "Method", "Path", "Status"],
                                           [[a.at.isoformat(timespec="seconds"), u.name if u else "Deleted user", u.email if u else "", a.method, a.path, a.status] for a, u in qy.limit(50000).all()])
    total = qy.count(); rows = qy.offset(max(offset, 0)).limit(min(max(limit, 1), 200)).all()
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
@app.get("/api/guardian/students")
def my_students(u: User = Depends(me), s: Session = Depends(db)):  # the children or students a parent or teacher looks after
    if u.role != "guardian": raise HTTPException(403, "For parents and teachers")
    row = lambda x, st: {"id": x.id, "name": x.name, "username": x.username, "place": place_line(s, x), "status": st, "active": bool(x.active)}
    return {"students": [row(x, "active") for x in guardian_students(s, u.id)] + [row(x, "invited") for x in guardian_students(s, u.id, "invited")]}
LANGS = {"en": "English", "ar": "Arabic", "ta": "Tamil"}
class LangIn(BaseModel): lang: str
@app.put("/api/me/lang")
def set_lang(b: LangIn, u: User = Depends(me), s: Session = Depends(db)):  # the person's language for the screens and for AI answers
    if b.lang not in LANGS: raise HTTPException(400, "Choose English, Arabic or Tamil")
    u.lang = None if b.lang == "en" else b.lang; s.commit(); return me_json(u)
def in_lang(u, prompt):  # AI answers come in the reader's language; the prompt (and so the saved-answer key) differs per language
    lang = getattr(u, "lang", None) or "en"
    if lang == "en": return prompt
    return prompt + f"\n\nWrite the whole answer in {LANGS[lang]}. Keep formulas, equations, chemical symbols, units, code and the Markdown formatting as they are."
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
SEM = re.compile(r"^(?:s|sem|semester|y|yr|year|g|gr|grade|std|class)?\s*(1[0-2]|[1-9])$", re.I)
PATTERNS = {"semester": "Semester", "year": "Year", "grade": "Grade"}; DEFAULT_TERMS = {"semester": 8, "year": 4, "grade": 12}
MAX_TERMS = {"semester": 8, "year": 8, "grade": 12}; TOP_TERM = max(MAX_TERMS.values())  # school programs run Grade 1 to 12
def term_max(p): return MAX_TERMS.get(getattr(p, "pattern", None) or "semester", 8)
def term_label(p): return PATTERNS.get(getattr(p, "pattern", None) or "semester", "Semester")
def gen_pw(): return "".join(secrets.choice(PWCHARS) for _ in range(10))
def term_header(terms): return next(iter(terms)) if len(terms) == 1 else "Term"  # CSV column title: Semester, Year or Grade when every row shares it
def to_sem(v):  # 3, "3", "Semester 3", "S3" -> 3; blank -> None; anything else -> error
    if v is None or str(v).strip() == "": return None
    m = SEM.match(str(v).strip())
    if not m: raise HTTPException(400, f"Semester, year or grade must be a number from 1 to {TOP_TERM}")
    return int(m.group(1))
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
def sem_no(name):  # "Semester 1", "Sem I", "S3" -> number. Only used to fill semesters.semester_no once (migration 0010, CSV import)
    m = re.search(r"(?<![\w])(?:1[0-2]|[1-9]|xii|xi|ix|x|viii|vii|vi|iv|v|iii|ii|i)(?![\w])", name or "", re.I)
    return None if not m else (int(m.group(0)) if m.group(0).isdigit() else ROMAN[m.group(0).lower()])
def scoped(u): return not is_staff(u)  # a student without a program sees no programs, courses or topics until an admin enrols them
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
def quiz_unit_open(q, s):
    un = s.get(Unit, q.unit_id) if q.unit_id else None
    if un is not None and un.archived_at: raise HTTPException(403, "This quiz is unavailable right now")
def quiz_course_id(q, s):  # a unit quiz belongs to its unit's course; a course test to its course
    if not q.unit_id: return q.course_id
    un = s.get(Unit, q.unit_id)
    return un.course_id if un else None
UNAVAILABLE = "This course is unavailable right now"
def sem_off(s, sem):  # a semester is off when it or its program is archived
    p = s.get(Program, sem.program_id) if sem.program_id else None
    return bool(sem.archived_at or (p and p.archived_at))
def course_places(s, co):  # the semesters a course is shown in: its home first, then the ones it is shared into
    ids = [co.semester_id] + [l.semester_id for l in s.query(CourseLink).filter_by(course_id=co.id)]
    return [x for i in ids if i and (x := s.get(Semester, i))]
def course_off(s, co):  # archived itself, or every place it is shown in is archived (an archived program or semester takes its courses with it)
    if co.archived_at: return True
    places = course_places(s, co)
    return bool(places) and all(sem_off(s, x) for x in places)
def check_course_access(u, course_id, s):
    co = s.get(Course, course_id) if course_id else None
    if co is not None and not can_edit(u, course_id, s) and course_off(s, co): raise HTTPException(403, UNAVAILABLE)  # admins and the course's owner can still open it, to restore it
    if not scoped(u): return
    sem = s.get(Semester, co.semester_id) if co and co.semester_id else None
    ok = co and sem and sem_visible(u, sem)
    if not ok and co:  # or the course is shared into one of the student's visible semesters
        ok = any(sem_visible(u, x) for x in s.query(Semester).join(CourseLink, CourseLink.semester_id == Semester.id).filter(CourseLink.course_id == co.id))
    if not ok: raise HTTPException(403, "This is not part of your program or semester")
    if not any(sem_visible(u, x) and not sem_off(s, x) for x in course_places(s, co)): raise HTTPException(403, UNAVAILABLE)  # the only places they see it are archived
def topic_off(s, t):  # the topic or its unit is archived (the course chain is checked on its own)
    un = s.get(Unit, t.unit_id) if t.unit_id else None
    return bool(t.archived_at or (un and un.archived_at))
def check_topic_access(u, t, s):  # drafts are for admins and the faculty assigned to the course only
    cid = topic_course_id(t, s)
    if t.published is False and not can_edit(u, cid, s): raise HTTPException(404, "Topic not found")
    check_course_access(u, cid, s)
    if topic_off(s, t) and not can_edit(u, cid, s): raise HTTPException(403, "This topic is unavailable right now")
def sem_number(s, program_id, n, keep=None):  # a semester number is 1 to 8 (grades 1 to 12) and unique within its program
    p = s.get(Program, program_id); lab, top = term_label(p).lower(), term_max(p)
    if n is None or not 1 <= n <= top: raise HTTPException(400, f"The {lab} number must be from 1 to {top}")
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
def fit_sem(s, pid, sem):  # a student's number must exist in their program: up to 8 for semesters and years, 12 for grades
    p = s.get(Program, pid) if pid and sem else None
    if p and sem > term_max(p): raise HTTPException(400, f"{p.name} goes up to {term_label(p).lower()} {term_max(p)}")
    return sem
class NewUser(BaseModel):
    name: str; email: str; password: str; role: str = "student"; active: bool = True; program_id: int | None = None; semester: int | None = None
class UserPatch(BaseModel):
    name: str | None = None; email: str | None = None; role: str | None = None; active: bool | None = None; password: str | None = None
    program_id: int | None = None; semester: int | None = None  # send null to clear
USORT = {"name": (func.lower(User.name),), "role": (User.role, func.lower(User.name)), "program": (func.lower(func.coalesce(Program.name, "~")), User.semester, func.lower(User.name)),
         "semester": (func.coalesce(User.semester, 99), func.lower(User.name)), "newest": (User.id.desc(),)}
def urow(u, prog): return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active, "program_id": u.program_id, "program": prog, "semester": u.semester,
                           "self_registered": bool(u.self_registered), "institution": u.institution, "id_number": u.id_number, "phone": u.phone, "own_ai_key": bool(u.ai_key),
                           "plan": ai_plan(u), "pro_until": utc_iso(u.pro_until) if pro_active(u) else None}
@app.get("/api/admin/users")
def users(q: str = "", program_id: int | None = None, semester: int | None = None, role: str = "", order: str = "role", limit: int = 50, offset: int = 0, plan: str = "",
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
    now = dt.datetime.utcnow(); asking = s.query(MoreRequest.user_id).filter(MoreRequest.done_at.is_(None))
    if plan == "asked": qs = qs.filter(User.id.in_(asking))  # self-registered people asking for more AI
    elif plan == "pro": qs = qs.filter(User.self_registered == True, User.pro_until > now)  # noqa: E712
    elif plan == "lite": qs = qs.filter(User.self_registered == True, User.ai_key.is_(None), or_(User.pro_until.is_(None), User.pro_until <= now))  # noqa: E712
    rows = qs.order_by(*USORT.get(order, USORT["role"]), User.id).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    asked = {i for (i,) in asking.filter(MoreRequest.user_id.in_([u.id for u, _ in rows] or [0]))}
    return {"total": qs.count(), "items": [{**urow(u, pn), "asked": u.id in asked} for u, pn in rows]}
@app.get("/api/admin/users/{uid}")
def user_detail(uid: int, a: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    prog = s.get(Program, u.program_id) if u.program_id else None
    live = live_topic_ids(s, [c.id for c in live_courses(a, s)])  # same rule as the Reports screens
    n, reads, last = s.query(func.count(Progress.id), func.coalesce(func.sum(Progress.reads), 0), func.max(Progress.last_read)).filter(Progress.user_id == uid, Progress.topic_id.in_(live)).one()
    recent = s.query(Topic.title, Progress.reads, Progress.last_read).join(Progress, Progress.topic_id == Topic.id).filter(Progress.user_id == uid, Topic.id.in_(live)).order_by(Progress.last_read.desc()).limit(500).all()
    req = s.query(MoreRequest).filter_by(user_id=uid, done_at=None).order_by(MoreRequest.id.desc()).first()
    return {**urow(u, prog.name if prog else None), "asked": {"at": req.at.isoformat() + "Z", "note": req.note or ""} if req else None, "topics_read": n, "reads": int(reads), "last_active": (last.isoformat() + "Z") if last else None,
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
    s.add(User(name=name, email=e, pw=hp(b.password), role=b.role, active=b.active, program_id=check_program(b.program_id, s), semester=fit_sem(s, b.program_id, to_sem(b.semester)), must_change=b.role != "admin")); s.commit(); return {"ok": True}
@app.delete("/api/admin/users/{uid}")
def delete_user(uid: int, a: User = Depends(admin), s: Session = Depends(db)):
    """Removes an account for good with the person's own records (progress, test attempts, bookmarks, their study courses and so on).
    Programs, courses and topics they created stay; they just no longer name a creator. The activity log keeps its rows."""
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if u.id == a.id: raise HTTPException(400, "You can't delete your own account")
    for t in reversed(Base.metadata.sorted_tables):  # rows that point at this user, children before parents
        for fk in t.foreign_keys:
            if fk.column.table.name != "users": continue
            col = fk.parent
            if fk.ondelete == "SET NULL" or (fk.ondelete is None and col.name == "owner_id"): s.execute(t.update().where(col == uid).values({col.name: None}))
            else: s.execute(t.delete().where(col == uid))
    s.query(PasswordReset).filter_by(user_id=uid).delete()
    s.delete(u); s.commit(); return {"ok": True}
@app.patch("/api/admin/users/{uid}")
def patch_user(uid: int, b: UserPatch, a: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if u.id == a.id and ((b.role and b.role != u.role) or (b.active is not None and b.active != u.active)):
        raise HTTPException(400, "You can't change your own role or status")
    if b.name is not None:
        if not b.name.strip(): raise HTTPException(400, "Name can't be empty")
        u.name = b.name.strip()
    if b.email is not None and not (u.username and not b.email.strip()):  # a child a parent signed up has a username and may have no email
        e = b.email.strip().lower()
        if not EMAIL.match(e): raise HTTPException(400, "Enter a valid email")
        if e != u.email and s.query(User).filter_by(email=e).first(): raise HTTPException(400, "That email is already registered")
        u.email = e
    if b.role and b.role != u.role:  # a parent or teacher who signed up keeps "guardian" when an admin edits other details
        if b.role not in ROLES: raise HTTPException(400, "Role must be student, faculty or admin")
        u.role = b.role
    if b.active is not None: u.active = b.active
    sent = b.dict(exclude_unset=True)
    if "program_id" in sent: u.program_id = check_program(b.program_id, s)
    if "semester" in sent: u.semester = to_sem(b.semester)
    if "program_id" in sent or "semester" in sent: fit_sem(s, u.program_id, u.semester)
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
        prog = check_program(b.program_id, s); sem = fit_sem(s, prog, to_sem(b.semester))
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
        except HTTPException: bad(f"Semester, year or grade must be a number from 1 to {TOP_TERM}"); continue
        u = existing.get(e)
        try: fit_sem(s, prog.id if prog else u.program_id if u else None, sem or (u.semester if u and prog else None))
        except HTTPException as x: bad(x.detail); continue
        seen.add(e)
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
def admin_programs(q: str = "", order: str = "name", status: str = "active", limit: int = 50, offset: int = 0, _: User = Depends(admin), s: Session = Depends(db)):
    stu = s.query(func.count(User.id)).filter(User.program_id == Program.id).correlate(Program).scalar_subquery()
    qs = s.query(Program)
    if status == "archived": qs = qs.filter(Program.archived_at.isnot(None))
    elif status != "all": qs = qs.filter(Program.archived_at.is_(None))  # archived programs are out of the way unless asked for
    if q.strip():
        like = f"%{q.strip().lower()}%"  # matches the program name, or any of its semester or course names
        qs = qs.filter(or_(func.lower(Program.name).like(like),
            Program.id.in_(s.query(Semester.program_id).filter(func.lower(Semester.name).like(like))),
            Program.id.in_(s.query(Course.program_id).filter(func.lower(Course.name).like(like)))))
    rows = qs.order_by(*PSORT.get(order, PSORT["name"])(stu), Program.id).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    c = counts(s, [p.id for p in rows])
    return {"total": qs.count(), "items": [{"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), "archived": bool(p.archived_at), **c[p.id]} for p in rows]}
@app.get("/api/admin/courses")
def admin_courses(q: str = "", program_id: int | None = None, order: str = "name", status: str = "active", limit: int = 25, offset: int = 0, _: User = Depends(admin), s: Session = Depends(db)):
    """Every course in one list for admins: search (course, program, semester or owner), a program filter, sorting and paging."""
    units = s.query(func.count(Unit.id)).filter(Unit.course_id == Course.id, Unit.archived_at.is_(None)).correlate(Course).scalar_subquery()
    topics = s.query(func.count(Topic.id)).filter(Topic.course_id == Course.id, Topic.archived_at.is_(None)).correlate(Course).scalar_subquery()
    qs = s.query(Course, Program, Semester, User, units, topics).outerjoin(Program, Program.id == Course.program_id) \
        .outerjoin(Semester, Semester.id == Course.semester_id).outerjoin(User, User.id == Course.faculty_owner_id)
    live = and_(Course.archived_at.is_(None), Semester.archived_at.is_(None), Program.archived_at.is_(None))  # a course is archived with its semester or program
    if status == "archived": qs = qs.filter(~live)
    elif status != "all": qs = qs.filter(live)
    if program_id is not None: qs = qs.filter(Course.program_id == program_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        qs = qs.filter(or_(*[func.lower(func.coalesce(c, "")).like(like) for c in (Course.name, Program.name, Semester.name, User.name)]))
    name = [func.lower(Course.name)]
    by = {"program": [func.lower(Program.name), func.coalesce(Semester.semester_no, 99), *name], "topics": [topics.desc(), *name], "newest": [Course.id.desc()], "name_desc": [func.lower(Course.name).desc()]}
    total = qs.count()
    rows = qs.order_by(*by.get(order, name), Course.id).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    return {"total": total, "items": [{"id": c.id, "name": c.name, "program_id": c.program_id, "program": p.name if p else None, "semester_id": c.semester_id,
                                       "semester": sm.name if sm else None, "term": term_label(p) if p else "Semester", "owner_id": c.faculty_owner_id, "owner": ow.name if ow else None,
                                       "owner_problem": owner_problem(ow), "units": un, "topics": tp,
                                       "archived": bool(c.archived_at or (sm and sm.archived_at) or (p and p.archived_at))} for c, p, sm, ow, un, tp in rows]}
@app.get("/api/admin/programs/{pid}")
def admin_program(pid: int, _: User = Depends(admin), s: Session = Depends(db)):
    p = s.get(Program, pid)
    if not p: raise HTTPException(404, "No such program")
    sems = s.query(Semester).filter_by(program_id=pid).order_by(*SEM_ORDER).all()
    cc = dict(s.query(Course.semester_id, func.count(Course.id)).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    tc = dict(s.query(Course.semester_id, func.count(Topic.id)).join(Topic, Topic.course_id == Course.id).filter(Course.program_id == pid).group_by(Course.semester_id).all())
    studs = s.query(User).filter_by(program_id=pid).order_by(func.coalesce(User.semester, 99), func.lower(User.name)).limit(5000).all()
    cl = defaultdict(list); sem_arch = {x.id: bool(x.archived_at) for x in sems}
    for co, ow in s.query(Course, User).outerjoin(User, User.id == Course.faculty_owner_id).filter(Course.semester_id.in_([x.id for x in sems] or [0])).order_by(Course.id):
        cl[co.semester_id].append({"id": co.id, "name": co.name, "owner_id": co.faculty_owner_id, "owner": ow.name if ow else None, "owner_problem": owner_problem(ow),
                                "archived": bool(co.archived_at or p.archived_at or sem_arch.get(co.semester_id)), "archived_self": bool(co.archived_at)})
    return {"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), "archived": bool(p.archived_at), **counts(s, [pid])[pid],
            "semester_list": [{"id": x.id, "name": x.name, "number": x.semester_no, "courses": cc.get(x.id, 0), "topics": tc.get(x.id, 0), "course_list": cl[x.id],
                               "archived": bool(x.archived_at or p.archived_at), "archived_self": bool(x.archived_at)} for x in sems],
            "student_list": [{"id": u.id, "name": u.name, "semester": u.semester, "active": u.active} for u in studs]}
AI_DOWN = "AI unavailable. Try again later."
def ai_key(s): return setting(s, "deepseek_key") or (os.getenv("DEEPSEEK_API_KEY") or "").strip()  # one key, set by the admin, serves every student
async def deepseek(key, model, messages, max_tokens=None, timeout=45):
    """The only way a text request leaves the server (photos go through vision(), which does the same). The built-in safety rules (guardrails.py) always go first, ahead of any task prompt an admin
    can edit; what people wrote is fenced as material, not instructions; and a reply that leaks the rules is withheld."""
    sent = [{"role": "system", "content": GUARDRAILS}] + [{"role": m["role"], "content": fence(m["content"]) if m["role"] == "user" else m["content"]} for m in messages]
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {key}"},
                         json={"model": model, "messages": sent, **({"max_tokens": max_tokens} if max_tokens else {})})
    r.raise_for_status(); j = r.json(); text = j["choices"][0]["message"]["content"]
    if not text: raise ValueError("empty answer")
    return checked(text), j.get("usage", {}).get("total_tokens", 0)
VISION_MODEL = "claude-opus-5-5"  # the default model for photos of diagrams; an admin can choose another under Settings
def vision_key(s): return setting(s, "vision_key") or (os.getenv("ANTHROPIC_API_KEY") or "").strip()
def vision_on(u, s): return bool(vision_key(s)) and (not u.self_registered or pro_active(u))  # the college's Claude key: not for lite people, whose own key can only be DeepSeek
REFUSED = "I can't help with that photo. Ask me about something you are studying."
async def vision(key, model, system, image_jpeg, text, max_tokens=4000):
    """The only way a photo leaves the server: to Claude, which can see diagrams. Like deepseek(), the built-in safety rules come first,
    what people wrote is fenced as material, and a reply that leaks the rules is withheld. Returns (text, tokens)."""
    client = anthropic.AsyncAnthropic(api_key=key, max_retries=1, timeout=90)
    r = await client.beta.messages.create(
        model=model, max_tokens=max_tokens, system=GUARDRAILS + "\n\n" + system, output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",  # a declined request is retried on a fallback model by the API itself
        messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(image_jpeg).decode()}},
                                               {"type": "text", "text": fence(text)}]}])
    if r.stop_reason == "refusal": return REFUSED, 0
    out = "".join(b.text for b in r.content if b.type == "text").strip()
    if not out: raise ValueError("empty answer")
    return checked(out), (r.usage.input_tokens or 0) + (r.usage.output_tokens or 0)
def ai_down(u, why=""):  # students get the plain message; admins also get a pointer to the likely fix
    return HTTPException(503, AI_DOWN + (f" (Admin: {why})" if why and u.role == "admin" else ""))
def key_for(u, s):  # a self-registered person's own key when they saved one; otherwise the admin's (for lite people, within the free daily allowance)
    return unseal(u.ai_key) if u.self_registered and u.ai_key else ai_key(s)
NEEDS_OWN_KEY = "Add your own DeepSeek API key under AI key in the menu to use AI help."
@app.get("/api/ai/status")
def ai_status(u: User = Depends(me), s: Session = Depends(db)):
    return {"available": bool(key_for(u, s)), "own_key": bool(u.self_registered), "vision": vision_on(u, s), "ocr": ocr_ready(), "plan": ai_plan(u)}
class OwnKey(BaseModel): key: str
KEY_TRIES = 10  # saving a key checks it with DeepSeek; at most this many tries an hour per person
@app.get("/api/me/ai-key")
def my_ai_key(u: User = Depends(me)):
    k = unseal(u.ai_key) if u.ai_key else ""
    return {"own_key": bool(u.self_registered), "key_set": bool(k), "key_hint": ("…" + k[-4:]) if k else ""}
@app.put("/api/me/ai-key")
async def set_my_ai_key(b: OwnKey, u: User = Depends(me), s: Session = Depends(db)):
    if not u.self_registered: raise HTTPException(403, "Your account uses the key your admin saved. You do not need your own.")
    if s.query(func.count(AuditLog.id)).filter(AuditLog.user_id == u.id, AuditLog.method == "PUT", AuditLog.path == "/api/me/ai-key",
                                                AuditLog.at >= dt.datetime.utcnow() - dt.timedelta(hours=1)).scalar() >= KEY_TRIES:
        raise HTTPException(429, "Too many tries. Wait an hour, then save your key again.")  # each try asks DeepSeek, so this must not become a way to test stolen keys
    k = b.key.strip()
    if not 20 <= len(k) <= 200 or any(ch.isspace() for ch in k): raise HTTPException(400, "That does not look like a DeepSeek API key. Copy the whole key from your DeepSeek account.")
    try: await deepseek(k, setting(s, "model", "deepseek-chat"), [{"role": "user", "content": "Reply with the word OK."}], max_tokens=5, timeout=20)
    except httpx.HTTPStatusError as e: raise HTTPException(400, "DeepSeek rejected this key (" + str(e.response.status_code) + ")." + (" Check that you copied it correctly." if e.response.status_code in (401, 403) else " Check your DeepSeek balance."))
    except Exception: raise HTTPException(400, "Could not reach DeepSeek to check the key. Try again in a moment.")
    me_row = s.get(User, u.id); me_row.ai_key = seal(k); close_requests(s, u.id); s.commit()
    return {"ok": True, "key_hint": "…" + k[-4:]}
@app.delete("/api/me/ai-key")
def delete_my_ai_key(u: User = Depends(me), s: Session = Depends(db)):
    s.get(User, u.id).ai_key = None; s.commit(); return {"ok": True}
class Cfg(BaseModel):
    deepseek_key: str | None = None; model: str | None = None; remove_key: bool = False; self_registration: bool | None = None; allowed_domains: str | None = None
    vision_key: str | None = None; vision_model: str | None = None; remove_vision_key: bool = False
    budget_deepseek: int | None = None; budget_claude: int | None = None  # tokens a month on the college's keys; 0 means no limit
    lite_searches: int | None = None; lite_minutes: int | None = None  # the free daily allowance of self-registered (lite) people
@app.get("/api/admin/settings")
def get_cfg(_: User = Depends(admin), s: Session = Depends(db)):
    k = ai_key(s)
    vk = vision_key(s)
    return {"mail_on": mail_on(s), "key_set": bool(k), "key_hint": ("…" + k[-4:]) if k else "", "model": setting(s, "model", "deepseek-chat"),
            "vision_set": bool(vk), "vision_hint": ("…" + vk[-4:]) if vk else "", "vision_model": setting(s, "vision_model", VISION_MODEL), "ocr": ocr_ready(),
            "budget": {p: budget(s, p) for p in ("deepseek", "claude")},
            "self_registration": setting(s, "self_registration") == "1", "allowed_domains": setting(s, "allowed_domains"), "self_registered_users": s.query(User).filter_by(self_registered=True).count(),
            "lite": dict(zip(("searches", "minutes"), lite_limits(s)))}
@app.put("/api/admin/settings")
def put_cfg(b: Cfg, _: User = Depends(admin), s: Session = Depends(db)):
    if b.remove_key: s.query(Setting).filter_by(k="deepseek_key").delete()  # turns AI off for everyone until a new key is saved
    for k, v in (("deepseek_key", b.deepseek_key), ("model", b.model)):
        if v and v.strip() and not (k == "deepseek_key" and b.remove_key): s.merge(Setting(k=k, v=v.strip()))
    for p, v in (("deepseek", b.budget_deepseek), ("claude", b.budget_claude)):
        if v is not None:
            if not 0 <= v <= 10**12: raise HTTPException(400, "Enter a monthly allowance in tokens, or 0 for no limit")
            s.merge(Setting(k="budget_" + p, v=str(v)))
    if b.remove_vision_key: s.query(Setting).filter_by(k="vision_key").delete()  # photos of diagrams stop going to Claude; text from photos still works
    for k, v in (("vision_key", b.vision_key), ("vision_model", b.vision_model)):
        if v and v.strip() and not (k == "vision_key" and b.remove_vision_key): s.merge(Setting(k=k, v=v.strip()))
    if b.self_registration is not None: s.merge(Setting(k="self_registration", v="1" if b.self_registration else "0"))
    for k, v in (("lite_searches", b.lite_searches), ("lite_minutes", b.lite_minutes)):
        if v is not None:
            if not 0 <= v <= 1000: raise HTTPException(400, "Enter a number from 0 to 1000")
            s.merge(Setting(k=k, v=str(v)))
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
@app.post("/api/admin/vision/test")
async def test_vision(_: User = Depends(admin), s: Session = Depends(db)):
    key = vision_key(s)
    if not key: return {"ok": False, "message": "No Claude key saved yet."}
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (16, 16), "white").save(buf, "JPEG")
    try: await vision(key, setting(s, "vision_model", VISION_MODEL), "Reply with the word OK.", buf.getvalue(), "Reply with the word OK.", max_tokens=200)
    except anthropic.AuthenticationError: return {"ok": False, "message": "Claude rejected the key. Check it and save it again."}
    except anthropic.NotFoundError: return {"ok": False, "message": "Claude does not know that model name. Check it under Vision model."}
    except anthropic.APIStatusError as e: return {"ok": False, "message": f"Claude answered with an error ({e.status_code})."}
    except Exception: return {"ok": False, "message": "No answer from Claude. Check the server's internet access and try again."}
    return {"ok": True, "message": "The key works. Students can ask about diagrams in photos now."}
# ---- Settings > Email: the Gmail sender, the site address for links, how sending is going, and what was sent ----
APP_PW_JUNK = re.compile(r"[\s\u200b\u200c\u200d\u2060\ufeff]+")  # Google shows App Passwords as "abcd efgh ijkl mnop"; copying can bring invisible characters too
class MailIn(BaseModel): gmail: str | None = None; app_password: str | None = None; app_url: str | None = None; remove_gmail: bool = False
def mail_state(s):
    c = mail_conf(s); fails = int(setting(s, "mail_fails", "0") or 0)
    return {"on": mail_on(s), "via": c["via"] if c else None, "sender": c["sender"] if c else "", "gmail": setting(s, "mail_gmail"), "gmail_saved": bool(setting(s, "mail_gmail_pw")),
            "env_server": bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")), "app_url": site_url(s), "app_url_saved": setting(s, "app_url"), "env_app_url": os.getenv("APP_URL", ""),
            "health": {"ok_at": (setting(s, "mail_ok_at") or None) and setting(s, "mail_ok_at") + "Z", "fail_at": (setting(s, "mail_fail_at") or None) and setting(s, "mail_fail_at") + "Z",
                       "fail_message": setting(s, "mail_fail_msg") if fails else "", "fails_in_a_row": fails}}
@app.get("/api/admin/mail")
def get_mail(_: User = Depends(admin), s: Session = Depends(db)): return mail_state(s)
@app.put("/api/admin/mail")
def put_mail(b: MailIn, _: User = Depends(admin), s: Session = Depends(db)):
    if b.remove_gmail:
        for k in ("mail_gmail", "mail_gmail_pw"): s.query(Setting).filter_by(k=k).delete()
    if b.gmail is not None and not b.remove_gmail:
        g = b.gmail.strip().lower()
        if g and not EMAIL.match(g): raise HTTPException(400, "Enter the Gmail address that sends the emails, such as zigora.college@gmail.com")
        s.merge(Setting(k="mail_gmail", v=g))
    if b.app_password and not b.remove_gmail:
        pw = APP_PW_JUNK.sub("", b.app_password)
        if not re.fullmatch(r"[A-Za-z]{16}", pw):
            raise HTTPException(400, f"A Gmail App Password is 16 letters (yours has {len(pw)} characters after removing spaces). Make one under Google Account > Security > 2-Step Verification > App passwords, and paste it as it is.")
        s.merge(Setting(k="mail_gmail_pw", v=seal(pw)))
    if b.app_password or b.remove_gmail or b.gmail is not None:  # a new sender starts with a clean record, so an old failure streak doesn't hang over it
        for k in ("mail_fails", "mail_fail_at", "mail_fail_msg"): s.query(Setting).filter_by(k=k).delete()
    if b.app_url is not None:
        u = b.app_url.strip().rstrip("/")
        u = re.sub(r"/app$", "", u)
        if u and not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?", u): raise HTTPException(400, "Enter the site's address only, such as https://learn.yourcollege.edu or http://169.58.13.213:5252")
        if u: s.merge(Setting(k="app_url", v=u))
        else: s.query(Setting).filter_by(k="app_url").delete()  # back to APP_URL from .env
    s.commit(); return mail_state(s)
@app.post("/api/admin/mail/test")
def test_mail(a: User = Depends(admin), s: Session = Depends(db)):
    if not mail_conf(s): return {"ok": False, "message": "No sender yet. Save a Gmail address and its App Password first."}
    if not site_url(s): return {"ok": False, "message": "Add the site's address first: links in emails need it."}
    try: send_mail(a.email, f"{APP_NAME} test email", "This is a test from your Zigora server. Password reset emails, registration codes and daily summaries can be sent.", kind="test", link=site_url(s) + "/app/")
    except MailError as e: return {"ok": False, "message": str(e)}
    return {"ok": True, "message": "Test email sent to " + a.email + ". Check the inbox (and spam)."}
@app.get("/api/admin/mail/log")
def mail_log(limit: int = 10, offset: int = 0, failed: bool = False, _: User = Depends(admin), s: Session = Depends(db)):
    q = s.query(MailLog).filter(MailLog.ok == False) if failed else s.query(MailLog)  # noqa: E712
    total = q.count(); rows = q.order_by(MailLog.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    return {"total": total, "items": [{"id": r.id, "at": r.at.isoformat() + "Z", "kind": r.kind, "label": MAIL_KINDS.get(r.kind, r.kind), "to": r.to, "ok": bool(r.ok), "error": r.error or ""} for r in rows]}
def live_topic_ids(s, cids):  # the one rule for "a topic students can read": published, not archived, not in an archived unit, in one of these courses
    off_units = s.query(Unit.id).filter(Unit.archived_at.isnot(None))
    return s.query(Topic.id).filter(Topic.course_id.in_(cids or [0]), Topic.published.isnot(False), Topic.archived_at.is_(None), or_(Topic.unit_id.is_(None), Topic.unit_id.notin_(off_units)))
@app.get("/api/admin/stats")
def stats(a: User = Depends(admin), s: Session = Depends(db)):
    saved = s.query(func.coalesce(func.sum(AICache.hits * AICache.tokens), 0)).scalar()
    return {"students": s.query(User).filter_by(role="student").count(), "topics": live_topic_ids(s, [c.id for c in live_courses(a, s)]).count(),
            "cached": s.query(AICache).count(), "tokens_saved": int(saved)}

@app.get("/api/admin/reports/{kind}")
def report_list(kind: str, q: str = "", show: str = "", sort: str = "", limit: int = 25, offset: int = 0, a: User = Depends(admin), s: Session = Depends(db)):
    """One page of a Reports list (topics read, students, saved AI answers), searched, filtered and sorted on the server."""
    live = live_topic_ids(s, [c.id for c in live_courses(a, s)]); k = f"%{q.strip()}%" if q.strip() else None
    if kind == "topics":
        readers, reads = func.count(Progress.id), func.coalesce(func.sum(Progress.reads), 0)
        qy = s.query(Topic.id, Topic.title, Course.name, readers, reads).join(Progress, Progress.topic_id == Topic.id).join(Course, Course.id == Topic.course_id) \
            .filter(Topic.id.in_(live)).group_by(Topic.id, Topic.title, Course.name)
        if k: qy = qy.filter(or_(Topic.title.ilike(k), Course.name.ilike(k)))
        qy = qy.order_by(*{"readers": [readers.desc()], "least": [reads.asc()], "title": [Topic.title.asc()]}.get(sort, [reads.desc()]), Topic.id)
        row = lambda r: {"id": r[0], "title": r[1], "course": r[2], "readers": r[3], "reads": int(r[4])}
    elif kind == "students":
        opened, last = func.count(Progress.id), func.max(Progress.last_read)
        qy = s.query(User.id, User.name, User.email, User.active, opened, last).outerjoin(Progress, and_(Progress.user_id == User.id, Progress.topic_id.in_(live))) \
            .filter(User.role == "student").group_by(User.id, User.name, User.email, User.active)
        if k: qy = qy.filter(or_(User.name.ilike(k), User.email.ilike(k)))
        if show == "active": qy = qy.filter(User.active == True)  # noqa: E712
        elif show == "disabled": qy = qy.filter(User.active == False)  # noqa: E712
        elif show == "never": qy = qy.having(opened == 0)
        elif show == "quiet": qy = qy.having(or_(last.is_(None), last < dt.datetime.utcnow() - dt.timedelta(days=7)))
        qy = qy.order_by(*{"quiet": [last.is_(None).desc(), last.asc()], "name": [User.name.asc()], "most": [opened.desc()], "least": [opened.asc()]}.get(sort, [last.is_(None).asc(), last.desc()]), User.id)
        row = lambda r: {"id": r[0], "name": r[1], "email": r[2], "active": bool(r[3]), "topics_read": r[4], "last_active": (r[5].isoformat() + "Z") if r[5] else None}
    elif kind == "ai":
        saved = AICache.hits * AICache.tokens
        qy = s.query(AICache.id, Topic.title, AICache.kind, AICache.hits, AICache.tokens).join(Topic, Topic.id == AICache.topic_id)
        if k: qy = qy.filter(Topic.title.ilike(k))
        if show in ("explain", "answer"): qy = qy.filter(AICache.kind == show)
        qy = qy.order_by(*{"hits": [AICache.hits.desc()], "newest": [AICache.id.desc()], "title": [Topic.title.asc()]}.get(sort, [saved.desc()]), AICache.id)
        row = lambda r: {"id": r[0], "title": r[1], "kind": r[2], "hits": r[3] or 0, "tokens": r[4] or 0, "saved": (r[3] or 0) * (r[4] or 0)}
    else: raise HTTPException(404, "Not found")
    total = qy.count(); rows = qy.offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    return {"total": total, "items": [row(r) for r in rows]}

# ---- course reports (admins see every course; faculty see only their own) ----
def csv_cell(v): v = "" if v is None else v; return "'" + v if isinstance(v, str) and v[:1] and v[:1] in "=+-@\t\r" else v  # stops spreadsheet formula injection
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
    ids = {u.id for u in aud}; off_units = s.query(Unit.id).filter(Unit.archived_at.isnot(None)); tids = [t.id for t in live_topic_ids(s, [c.id])]
    reads, done, last = defaultdict(int), defaultdict(int), {}  # topics opened, topics marked completed
    if tids and ids:
        for uid, n, d, l in s.query(Progress.user_id, func.count(Progress.id), func.count(Progress.completed_at), func.max(Progress.last_read)).filter(Progress.topic_id.in_(tids), Progress.user_id.in_(ids)).group_by(Progress.user_id).all(): reads[uid], done[uid], last[uid] = n, d, l
    qids = [q.id for q in s.query(Quiz.id).filter(Quiz.course_id == c.id, Quiz.published == True, or_(Quiz.unit_id.is_(None), Quiz.unit_id.notin_(off_units)))]  # noqa: E712
    bests = defaultdict(dict)
    if qids and ids:
        for qid, uid, b in s.query(Attempt.quiz_id, Attempt.user_id, func.max(Attempt.percent)).filter(Attempt.quiz_id.in_(qids), Attempt.user_id.in_(ids)).group_by(Attempt.quiz_id, Attempt.user_id).all(): bests[uid][qid] = b
    return tids, reads, done, last, qids, bests
def my_courses(u, s):
    q = s.query(Course)
    if u.role == "faculty": q = q.filter(Course.faculty_owner_id == u.id)
    return q.order_by(Course.id).all()
def live_courses(u, s): return [c for c in my_courses(u, s) if not course_off(s, c)]  # what the dashboard and reports count: archived courses are left out
def live_units(s, cids): return s.query(Unit.id).filter(Unit.course_id.in_(cids or [0]), Unit.archived_at.is_(None))
@app.get("/api/reports/courses")
def report_courses(program_id: int = 0, semester: int = 0, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    students = s.query(User).filter_by(role="student", active=True).all(); sems = {x.id: x for x in s.query(Semester)}; pn = {p.id: p.name for p in s.query(Program)}
    links = defaultdict(list); pt = {p.id: term_label(p) for p in s.query(Program)}; used = set()
    for l in s.query(CourseLink): links[l.course_id].append(l.semester_id)
    out = []
    for c in live_courses(u, s):
        sm = sems.get(c.semester_id)
        if program_id and c.program_id != program_id: continue
        if semester and (not sm or sm.semester_no != semester): continue
        used.add(pt.get(c.program_id, "Semester")); aud = course_audience(c, students, sems, links); tids, reads, done, last, qids, bests = course_stats(c, aud, s)
        comp = [100 * done[x.id] / len(tids) for x in aud] if tids else []; opened = [100 * reads[x.id] / len(tids) for x in aud] if tids else []; qb = [b for x in aud for b in bests[x.id].values()]
        out.append({"course_id": c.id, "course": c.name, "program": pn.get(c.program_id, ""), "semester": sm.name if sm else "", "students": len(aud), "topics": len(tids),
                    "avg_completion": round(sum(comp) / len(comp)) if comp else 0, "avg_opened": round(sum(opened) / len(opened)) if opened else 0, "quizzes": len(qids), "quiz_attempts": s.query(func.count(Attempt.id)).filter(Attempt.quiz_id.in_(qids or [0])).scalar(),
                    "avg_quiz_percent": round(sum(qb) / len(qb)) if qb else None})
    if format == "csv": return csv_response("courses.csv", ["Program", term_header(used), "Course", "Students", "Topics", "Average completion %", "Average opened %", "Quizzes", "Quiz attempts", "Average best quiz %"],
                                           [[r["program"], r["semester"], r["course"], r["students"], r["topics"], r["avg_completion"], r["avg_opened"], r["quizzes"], r["quiz_attempts"], r["avg_quiz_percent"]] for r in out])
    return out
@app.get("/api/reports/courses/{cid}/students")
def report_students(cid: int, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    students = s.query(User).filter_by(role="student").all(); sems = {x.id: x for x in s.query(Semester)}; pn = {p.id: p.name for p in s.query(Program)}
    links = defaultdict(list)
    for l in s.query(CourseLink).filter_by(course_id=cid): links[cid].append(l.semester_id)
    aud = course_audience(c, students, sems, links); tids, reads, done, last, qids, bests = course_stats(c, aud, s)
    pt = {p.id: term_label(p) for p in s.query(Program)}; used = {pt.get(x.program_id, "Semester") for x in aud}
    batches = latest_batches(s, [x.id for x in aud], course_quiz_ids(cid, s)); ctx = area_context(batches, s); per = defaultdict(list)
    for b in batches: per[b[0]].append(b)
    mine = {uid: tally(bs, ctx, True) for uid, bs in per.items()}
    names = lambda uid, st: [a["title"] for a in sorted(mine.get(uid, {}).values(), key=lambda a: (a["percent"], a["title"])) if a["status"] == st]
    rows = [{"strong": names(x.id, "strong"), "needs_study": names(x.id, "needs_study"), "name": x.name, "email": x.email, "program": pn.get(x.program_id, ""), "semester": x.semester, "active": bool(x.active), "topics_read": reads[x.id], "topics_completed": done[x.id], "topics": len(tids),
             "completion": round(100 * done[x.id] / len(tids)) if tids else 0, "quizzes_taken": len(bests[x.id]), "quizzes": len(qids),
             "avg_quiz_percent": round(sum(bests[x.id].values()) / len(bests[x.id])) if bests[x.id] else None, "last_active": (last[x.id].isoformat() + "Z") if last.get(x.id) else None}
            for x in sorted(aud, key=lambda x: (x.name or "").lower())]
    if format == "csv": return csv_response(f"students-{c.name}.csv".replace(" ", "_"), ["Name", "Email", "Program", term_header(used), "Active", "Topics read", "Topics completed", "Topics", "Completion %", "Quizzes taken", "Quizzes", "Average best quiz %", "Last active", "Strong areas", "Needs another round of study"],
                                           [[r["name"], r["email"], r["program"], r["semester"], "yes" if r["active"] else "no", r["topics_read"], r["topics_completed"], r["topics"], r["completion"], r["quizzes_taken"], r["quizzes"], r["avg_quiz_percent"], r["last_active"], "; ".join(r["strong"]), "; ".join(r["needs_study"])] for r in rows])
    return {"course": c.name, "students": rows}

# ---- dashboard cards: the list behind each number ----
LIST_TITLES = {"students": "Active students", "active_week": "Studied this week", "faculty": "Faculty", "courses": "Courses", "topics": "Topics", "drafts": "Draft topics",
               "empty_courses": "Courses with no units", "unowned": "Courses with no owner", "unenrolled": "Students not placed", "semester_numbers": "Terms with no number",
               "never_opened": "Students who never opened a topic"}
ADMIN_LISTS = {"students", "active_week", "faculty", "unowned", "unenrolled", "semester_numbers", "never_opened"}
@app.get("/api/overview/list")
def overview_list(kind: str, q: str = "", order: str = "name", limit: int = 5, offset: int = 0, u: User = Depends(staff), s: Session = Depends(db)):
    """The rows behind one dashboard card, with search, sorting and paging. Each item says where its details page is (target). Faculty see only their own courses."""
    if kind not in LIST_TITLES: raise HTTPException(404, "Unknown list")
    if kind in ADMIN_LISTS and u.role != "admin": raise HTTPException(403, "Admins only")
    mine = live_courses(u, s); pn = {p.id: p for p in s.query(Program)}; sems = {x.id: x for x in s.query(Semester)}; items = []
    def person(x, extra=""):
        p = pn.get(x.program_id); t = term_label(p) if p else "Semester"
        place = (p.name + (f" · {t} {x.semester}" if x.semester else "")) if p else "No program"
        return {"id": x.id, "title": x.name, "sub": x.email, "detail": place + extra, "sort": (x.name or "").lower(), "target": {"type": "user", "id": x.id}}
    def course(c, extra=""):
        sm = sems.get(c.semester_id); p = pn.get(c.program_id)
        return {"id": c.id, "title": c.name, "sub": " · ".join(x for x in [p.name if p else "", sm.name if sm else ""] if x), "detail": extra, "sort": (c.name or "").lower(),
                "target": {"type": "course", "program_id": c.program_id, "semester_id": c.semester_id, "id": c.id}}
    stu = s.query(User).filter_by(role="student", active=True)
    if kind == "students": items = [person(x) for x in stu]
    elif kind == "faculty": items = [{**person(x), "detail": "Active", "sub": x.email} for x in s.query(User).filter_by(role="faculty", active=True)]
    elif kind == "active_week":
        last = dict(s.query(Progress.user_id, func.max(Progress.last_read)).group_by(Progress.user_id).all()); week = dt.datetime.utcnow() - dt.timedelta(days=7)
        items = [{**person(x, f" · last read {last[x.id]:%d %b %Y}"), "recent": last[x.id].isoformat()} for x in stu if last.get(x.id) and last[x.id] >= week]
    elif kind == "unenrolled": items = [person(x) for x in stu.filter(or_(User.program_id.is_(None), User.semester.is_(None)))]
    elif kind == "never_opened": items = [person(x) for x in stu.filter(User.id.notin_(s.query(Progress.user_id)))]
    elif kind == "courses": items = [course(c, f"Owner: {u2.name}" if (u2 := s.get(User, c.faculty_owner_id) if c.faculty_owner_id else None) else "No owner") for c in mine]
    elif kind == "unowned": items = [course(c, "No owner") for c in mine if c.faculty_owner_id is None]
    elif kind == "empty_courses": items = [course(c, "No units yet") for c in mine if not live_units(s, [c.id]).first()]
    elif kind == "semester_numbers":
        for x in s.query(Semester).filter(Semester.semester_no.is_(None)):
            p = pn.get(x.program_id); items.append({"id": x.id, "title": x.name, "sub": p.name if p else "", "detail": "No number set", "sort": (x.name or "").lower(), "target": {"type": "program", "id": x.program_id}})
    else:  # topics, drafts
        cids = [c.id for c in mine]; cn = {c.id: c for c in mine}; un = {x.id: x for x in s.query(Unit).filter(Unit.course_id.in_(cids or [0]), Unit.archived_at.is_(None))}
        tq = s.query(Topic).filter(Topic.unit_id.in_(list(un) or [0]), Topic.archived_at.is_(None))
        tq = tq.filter(Topic.published == False) if kind == "drafts" else tq.filter(Topic.published.isnot(False))  # noqa: E712  (the Topics card counts published topics only; drafts are their own card)
        for t in tq:
            un_ = un.get(t.unit_id); c = cn.get(un_.course_id) if un_ else None
            items.append({"id": t.id, "title": t.title, "sub": " › ".join(x for x in [c.name if c else "", un_.name if un_ else ""] if x), "detail": "Published" if t.published else "Draft",
                          "sort": (t.title or "").lower(), "target": {"type": "topic", "id": t.id}})
    if q.strip():
        needle = q.strip().lower(); items = [i for i in items if needle in " ".join([i["title"] or "", i["sub"] or "", i["detail"] or ""]).lower()]
    if order == "recent" and any("recent" in i for i in items): items.sort(key=lambda i: (i.get("recent") or "", i["id"]), reverse=True)
    elif order == "detail": items.sort(key=lambda i: ((i["detail"] or "").lower(), i["sort"], i["id"]))
    elif order == "name_desc": items.sort(key=lambda i: (i["sort"], i["id"]), reverse=True)
    elif order == "newest": items.sort(key=lambda i: i["id"], reverse=True)
    else: items.sort(key=lambda i: (i["sort"], i["id"]))
    limit = min(max(limit, 1), 50); offset = max(offset, 0)
    return {"kind": kind, "title": LIST_TITLES[kind], "total": len(items), "items": [{k: v for k, v in i.items() if k not in ("sort", "recent")} for i in items[offset:offset + limit]],
            "can_recent": any("recent" in i for i in items)}
# ---- content: admin writes, everyone reads ----
@app.get("/api/overview")
def overview(u: User = Depends(staff), s: Session = Depends(db)):  # what needs attention today: admins see the whole college, faculty only their own courses
    mine = live_courses(u, s); cids = [c.id for c in mine]; now = dt.datetime.utcnow(); week = now - dt.timedelta(days=7)
    units = live_units(s, cids)
    topics = s.query(Topic).filter(Topic.unit_id.in_(units), Topic.archived_at.is_(None))
    drafts = topics.filter(Topic.published == False).count()  # noqa: E712
    out = {"role": u.role, "courses": len(cids), "topics": topics.filter(Topic.published.isnot(False)).count(), "drafts": drafts, "attention": []}  # topics are the published ones, as in the course rows; drafts have their own count
    add = lambda kind, n, text: n and out["attention"].append({"kind": kind, "count": n, "text": text})
    add("drafts", drafts, f"{drafts} draft topic{'s' if drafts != 1 else ''} not yet visible to students")
    empty = [c for c in mine if not live_units(s, [c.id]).first()]
    add("empty_courses", len(empty), f"{len(empty)} course{'s have' if len(empty) != 1 else ' has'} no units yet: " + ", ".join(c.name for c in empty[:5]))
    if u.role == "admin":
        stu = s.query(User).filter_by(role="student", active=True)
        out["people"] = {"students": stu.count(), "faculty": s.query(User).filter_by(role="faculty", active=True).count(),
                         "active_week": s.query(func.count(func.distinct(Progress.user_id))).join(User, User.id == Progress.user_id).filter(User.role == "student", Progress.last_read >= week).scalar()}
        out["programs"] = s.query(Program).count()
        noown = [c for c in mine if c.faculty_owner_id is None]
        add("unowned", len(noown), f"{len(noown)} course{'s have' if len(noown) != 1 else ' has'} no owner, so only admins can edit: " + ", ".join(c.name for c in noown[:5]))
        unplaced = stu.filter(or_(User.program_id.is_(None), User.semester.is_(None))).count()
        add("unenrolled", unplaced, f"{unplaced} active student{'s are' if unplaced != 1 else ' is'} not placed in a program and semester or year, so they see nothing")
        more = s.query(func.count(func.distinct(MoreRequest.user_id))).filter(MoreRequest.done_at.is_(None)).scalar()
        add("more_ai", more, f"{more} self-registered {'people ask' if more != 1 else 'person asks'} for more AI (Users > Asked for more)")
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
    top = min(term_max(p), max([x.semester_no for x in s.query(Semester).filter_by(program_id=pid) if x.semester_no] or [term_max(p)]))
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
class ProgramIn(BaseModel): name: str; pattern: str | None = None; terms: int | None = None  # pattern: semester, year or grade; terms: how many to create now (new programs only)
class SemesterIn(BaseModel): name: str; program_id: int; semester_no: int | None = None  # on edit, leave out to keep the number
class NewSemesterIn(BaseModel): name: str; semester_no: int
class NewCourseIn(BaseModel): name: str; faculty_owner_id: int | None = None
class CourseIn(BaseModel): name: str; semester_id: int; faculty_owner_id: int | None = None  # leave out to keep the owner, null for none
class UnitIn(BaseModel): name: str; course_id: int
class TopicIn(BaseModel):
    title: str; unit_id: int; content: str = ""; sample_content: str = ""; question_pattern: str = ""; guideline: str = ""; published: bool = True
    content_format: str = "markdown"  # "markdown" or "html"; HTML is cleaned when it is saved
    learning_due_at: dt.datetime | None = None  # ISO 8601 with a time zone; null removes the deadline; leave out to keep it
M = {"programs": Program, "semesters": Semester, "courses": Course, "units": Unit, "topics": Topic}
@app.get("/api/tree")
def tree(u: User = Depends(me), s: Session = Depends(db)):
    mine_p = {p.topic_id: p for p in s.query(Progress).filter_by(user_id=u.id)}; read = set(mine_p); now = dt.datetime.utcnow()
    noted = {i for (i,) in s.query(TopicNote.topic_id).filter_by(user_id=u.id)}  # topics that have this student's own notes
    marked = set() if u.role == "admin" else {b.topic_id for b in s.query(Bookmark).filter_by(user_id=u.id)}  # admins have no bookmarks, even old ones
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
    qz, tests = defaultdict(list), defaultdict(list)  # unit quizzes by unit; course tests by course
    for q in s.query(Quiz).order_by(Quiz.id):
        (qz[q.unit_id] if q.unit_id else tests[q.course_id]).append({"id": q.id, "title": q.title, "published": bool(q.published), "questions": qcount.get(q.id, 0), "best": best.get(q.id), "pass_percent": q.pass_percent})
    cbyid = {c.id: c for c in s.query(Course)}
    pa = {p.id for p in s.query(Program) if p.archived_at}; semoff = {x.id: bool(x.archived_at or x.program_id in pa) for x in s.query(Semester)}  # a semester is off when it or its program is archived
    mine = {c.id for c in cbyid.values() if c.faculty_owner_id == u.id} if u.role == "faculty" else set()
    owners = {x.id: x for x in s.query(User).filter(User.id.in_({c.faculty_owner_id for c in cbyid.values() if c.faculty_owner_id} or {0}))}
    for l in s.query(CourseLink).order_by(CourseLink.id):
        if l.course_id in cbyid: links[l.semester_id].append(cbyid[l.course_id])
    def cj(c, sm):
        shared = c.semester_id != sm.id; ed = u.role == "admin" or c.id in mine  # drafts show only to those who can edit the course
        off = bool(c.archived_at) or semoff.get(sm.id, False)  # archived itself, or shown in an archived semester or program
        d = {"id": c.id, "name": c.name, "shared": shared, "semester_id": c.semester_id, "home": sname.get(c.semester_id, "") if shared else "",
             "shared_with": len(linked_to[c.id]), "editable": ed, "mine": c.id in mine, "archived": off, "archived_self": bool(c.archived_at),
             "owner": owners[c.faculty_owner_id].name if c.faculty_owner_id in owners else None,
             "tests": [] if off and not ed else [q for q in tests[c.id] if ed or (q["published"] and q["questions"])], "units": [] if off and not ed else [  # everyone else sees an archived course as a locked name, nothing inside
            {"id": n.id, "name": n.name, "archived": off or bool(n.archived_at), "archived_self": bool(n.archived_at), "quizzes": [q for q in qz[n.id] if ed or (q["published"] and q["questions"])],
             "topics": [{"id": t.id, "title": t.title, "read": t.id in read, "bookmarked": t.id in marked, "published": t.published is not False, "has_notes": t.id in noted,
                         "archived": off or bool(n.archived_at) or bool(t.archived_at), "archived_self": bool(t.archived_at),
                         "last_read": mine_p[t.id].last_read.isoformat() + "Z" if t.id in mine_p and mine_p[t.id].last_read else None,
                         **learning_state(t.learning_due_at, mine_p.get(t.id), now)} for t in tp[n.id] if (t.published is not False or ed) and (ed or not t.archived_at)]} for n in un[c.id] if ed or not n.archived_at]}
        if u.role == "admin": d["link_ids"] = linked_to[c.id]; d["owner_id"] = c.faculty_owner_id; d["owner_problem"] = owner_problem(owners.get(c.faculty_owner_id))
        return d
    return [{"id": p.id, "name": p.name, "pattern": p.pattern or "semester", "term": term_label(p), "archived": p.id in pa, "archived_self": p.id in pa, "semesters": [{"id": sm.id, "name": sm.name, "number": sm.semester_no, "archived": semoff.get(sm.id, False), "archived_self": bool(sm.archived_at), "current": scoped(u) and u.semester is not None and sm.semester_no == u.semester,
        "courses": [cj(c, sm) for c in co[sm.id] + links[sm.id]]} for sm in se[p.id] if sem_visible(u, sm)]} for p in progs]
class ArchiveIn(BaseModel): archived: bool
def archived_ancestor(s, kind, r):
    """The nearest archived parent of an item, as (kind, name), or None. Programs have no parent."""
    chain = []
    if kind == "topics":
        un = s.get(Unit, r.unit_id) if r.unit_id else None; co = s.get(Course, un.course_id if un else r.course_id) if (un or r.course_id) else None; chain.append(("unit", un)); chain.append(("course", co))
    elif kind == "units": co = s.get(Course, r.course_id) if r.course_id else None; chain.append(("course", co))
    elif kind == "courses": co = r
    if kind in ("topics", "units", "courses"):
        sem = s.get(Semester, co.semester_id) if co and co.semester_id else None; chain.append(("semester", sem)); prog = s.get(Program, (sem.program_id if sem else co.program_id) if (sem or co) else 0) if (sem or co) else None
    elif kind == "semesters": chain.append(("program", s.get(Program, r.program_id) if r.program_id else None))
    if kind in ("topics", "units", "courses"): chain.append(("program", prog))
    for label, x in chain:
        if x is not None and x.archived_at: return label, x.name
    return None
@app.put("/api/{kind}/{rid}/archive")
def archive_item(kind: str, rid: int, b: ArchiveIn, u: User = Depends(staff), s: Session = Depends(db)):
    """Archive or restore one item. Archiving hides it and everything under it from students and counts; nothing is deleted. Restoring brings back what was archived with it."""
    if kind not in M: raise HTTPException(404, "Unknown item")
    r = s.get(M[kind], rid)
    if not r: raise HTTPException(404, "Not found")
    if kind in ("programs", "semesters"):
        if u.role != "admin": raise HTTPException(403, "Admins only")
    else: need_edit(u, r.id if kind == "courses" else r.course_id if kind == "units" else topic_course_id(r, s), s)
    if not b.archived:
        up = archived_ancestor(s, kind, r)
        if up:
            who = "Ask an admin to restore" if up[0] in ("program", "semester") and u.role != "admin" else "Restore"
            raise HTTPException(400, f"This is archived because its {up[0]} “{up[1]}” is archived. {who} that first.")
    if b.archived and not r.archived_at: r.archived_at = dt.datetime.utcnow()
    elif not b.archived: r.archived_at = None
    s.commit(); return {"ok": True, "archived": bool(r.archived_at)}
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
VFIELDS = ("title", "content", "sample_content", "question_pattern", "guideline", "content_format")
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
FORMATS = ("markdown", "html", "interactive")  # interactive: an HTML page with its own scripts, kept as uploaded and run only in a sandboxed frame
def fmt_of(t): f = getattr(t, "content_format", None); return f if f in ("html", "interactive") else "markdown"
HTML_TAGS = {"p", "br", "hr", "div", "span", "section", "article", "header", "footer", "aside", "main", "figure", "figcaption", "blockquote", "pre", "code", "kbd", "samp",
             "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "s", "del", "ins", "mark", "small", "sub", "sup", "abbr", "cite", "q", "dfn", "time", "bdi", "bdo",
             "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col", "a", "img", "details", "summary", "ruby", "rt", "rp", "input"}
HTML_ATTRS = {"*": {"dir", "lang", "title"}, "a": {"href"}, "img": {"src", "alt", "width", "height"}, "td": {"colspan", "rowspan", "align"}, "th": {"colspan", "rowspan", "align", "scope"},
              "ol": {"start", "type", "reversed"}, "li": {"value"}, "col": {"span"}, "colgroup": {"span"}, "time": {"datetime"}, "abbr": {"title"}, "input": {"type", "checked", "disabled"}}
def clean_html(raw):
    """An uploaded HTML file -> the safe part of its body: no scripts, styles, event handlers, forms or javascript: links; only http(s), mailto and relative links."""
    raw = raw or ""
    m = re.search(r"<body[^>]*>(.*)</body>", raw, re.S | re.I)
    out = nh3.clean(m.group(1) if m else raw, tags=HTML_TAGS, attributes=HTML_ATTRS, url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer",
                    set_tag_attribute_values={"input": {"disabled": "disabled"}})
    return re.sub(r"<input(?![^>]*type=\"checkbox\")[^>]*>", "", out).strip()  # only task-list checkboxes, never a real form field
def html_text(h): return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(br|/p|/li|/tr|/h\d|/div)[^>]*>", "\n", h or "")))).strip()
def shown_content(t): return clean_html(t.content) if fmt_of(t) == "html" else t.content  # cleaned again on the way out, whatever path saved it; interactive pages are only ever run in the sandboxed frame
def words_of(text, fmt):  # the words of a topic's content, for search and the AI: no tags, and none of an interactive page's scripts or styles
    if fmt == "markdown": return text or ""
    return html_text(re.sub(r"<(script|style|noscript|template)\b.*?</\1\s*>", " ", text or "", flags=re.S | re.I))
INTERACTIVE_MAX = 2_000_000
def topic_fields(b, s, keep_fmt=None):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this topic")
    title = (b.title or "").strip()
    if not title or len(title) > 200: raise HTTPException(400, "Give the topic a title (up to 200 characters)")
    f = {**b.dict(exclude_unset=True), "title": title, "course_id": un.course_id}  # fields left out are left alone
    if "learning_due_at" in f: f["learning_due_at"] = due_value(b.learning_due_at)
    if "content_format" in f or "content" in f:
        fmt = f.get("content_format") or keep_fmt or "markdown"  # content sent without a format keeps the topic's format
        if fmt not in FORMATS: raise HTTPException(400, "Content format must be markdown or html")
        f["content_format"] = fmt
        if fmt == "html" and "content" in f: f["content"] = clean_html(f["content"])
        if fmt == "interactive" and len(f.get("content") or "") > INTERACTIVE_MAX: raise HTTPException(413, "The page is over 2 MB. Split it into smaller topics.")
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
    if pat not in PATTERNS: raise HTTPException(400, "Choose semester, year or grade")
    n = DEFAULT_TERMS[pat] if b.terms is None else b.terms
    if not 0 <= n <= MAX_TERMS[pat]: raise HTTPException(400, f"A program can start with 0 to {MAX_TERMS[pat]} {PATTERNS[pat].lower()}s")
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
def edit_program(rid: int, b: ProgramIn, a: User = Depends(admin), s: Session = Depends(db)):
    p = s.get(Program, rid)
    if not p: raise HTTPException(404, "Not found")
    vals = {"name": program_name(b.name, s, rid)}
    if b.pattern is not None:
        pat = b.pattern.strip().lower()
        if pat not in PATTERNS: raise HTTPException(400, "Choose semester, year or grade")
        if pat != (p.pattern or "semester"):  # terms still carrying the standard name follow the change; custom names are left alone
            terms = s.query(Semester).filter_by(program_id=rid).all()
            if any((x.semester_no or 0) > MAX_TERMS[pat] for x in terms): raise HTTPException(400, f"A {pat} program goes up to {PATTERNS[pat].lower()} {MAX_TERMS[pat]}. Delete or renumber the terms above it first")
            for x in terms:
                if re.fullmatch(r"(Semester|Year|Grade) \d+", x.name or ""): x.name = f"{PATTERNS[pat]} {x.semester_no}" if x.semester_no else x.name
            vals["pattern"] = pat
            if pat == "grade" and terms:  # a school runs Grade 1 to 12: fill in the grades it does not have yet
                have = {x.semester_no for x in terms}
                for i in range(1, MAX_TERMS[pat] + 1):
                    if i not in have: s.add(Semester(name=f"Grade {i}", program_id=rid, semester_no=i, created_by=a.id))
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
    f = topic_fields(b, s, fmt_of(x)); need_edit(u, f["course_id"], s)
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
    n = Topic(title=title, unit_id=un.id, course_id=un.course_id, content=t.content, content_format=fmt_of(t), sample_content=t.sample_content, question_pattern=t.question_pattern, guideline=t.guideline,
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
        n = Topic(title=t.title, unit_id=nu.id, course_id=co.id, content=t.content, content_format=fmt_of(t), sample_content=t.sample_content, question_pattern=t.question_pattern, guideline=t.guideline,
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
MAX_QUESTIONS = 200  # a course test; a unit quiz stays short
def max_questions(q): return 100 if q.unit_id else MAX_QUESTIONS
class QuizIn(BaseModel): unit_id: int = 0; course_id: int = 0; title: str; pass_percent: int = 50; published: bool = False; reveal: bool = False  # unit_id for a unit quiz, else course_id for a course test
class QuestionIn(BaseModel):
    text: str; options: list[str]; correct: int; explanation: str = ""; topic_id: int | None = None
    area: str = ""; image: str = ""; option_images: list[str] = []  # images are urls from POST /api/uploads
class QuestionsIn(BaseModel): questions: list[QuestionIn]
class AttemptIn(BaseModel): answers: list[int | None]
def quiz_or_404(qid, s):
    q = s.get(Quiz, qid)
    if not q: raise HTTPException(404, "Quiz not found")
    return q
def quiz_fields(b):
    if not b.title.strip(): raise HTTPException(400, "Give the quiz a title")
    if not 1 <= b.pass_percent <= 100: raise HTTPException(400, "Pass mark must be between 1 and 100")
    return {"title": b.title.strip()[:200], "pass_percent": b.pass_percent, "published": b.published, "reveal": b.reveal}
IMG_URL = re.compile(r"/api/uploads/[0-9a-f]{32}\.(png|jpg|gif|webp)")
def img_or_none(v, label):
    v = (v or "").strip()
    if v and not IMG_URL.fullmatch(v): raise HTTPException(400, f"{label}: upload the image here first")
    return v or None
def topic_fits(q, tid, s):  # a question's topic must be in the quiz's unit, or anywhere in the course for a course test
    qs = s.query(Topic.id).filter(Topic.id == tid)
    qs = qs.filter(Topic.unit_id == q.unit_id) if q.unit_id else qs.join(Unit, Unit.id == Topic.unit_id).filter(Unit.course_id == q.course_id)
    return qs.first() is not None
def clean_question(q, x, i, s):  # -> the column values of one question, or a 400 naming what is wrong
    opts = [o.strip() for o in x.options]; oimg = [img_or_none(v, f"Question {i}, answer {k + 1}") for k, v in enumerate(x.option_images[:len(opts)])]
    oimg += [None] * (len(opts) - len(oimg))
    if not x.text.strip() and not x.image: raise HTTPException(400, f"Question {i} has no text")
    if not 2 <= len(opts) <= 6 or not all(o or im for o, im in zip(opts, oimg)): raise HTTPException(400, f"Question {i} needs 2 to 6 answers, each with text or an image")
    if not 0 <= x.correct < len(opts): raise HTTPException(400, f"Question {i}: mark which answer is correct")
    if x.topic_id is not None and not topic_fits(q, x.topic_id, s): raise HTTPException(400, f"Question {i}: pick a topic from this {'unit' if q.unit_id else 'course'}")
    return {"text": x.text.strip(), "options": json.dumps(opts), "correct": x.correct, "explanation": x.explanation.strip(), "topic_id": x.topic_id,
            "area": x.area.strip()[:150] or None, "image": img_or_none(x.image, f"Question {i}"), "option_images": json.dumps(oimg) if any(oimg) else None}
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
    tids = {x.topic_id for _, _, qm, _ in batches for x in qm.values() if x.topic_id}
    topics = {t.id: t for t in s.query(Topic).filter(Topic.id.in_(tids or {0}))}
    uids = {q.unit_id for _, q, _, _ in batches if q.unit_id} | {t.unit_id for t in topics.values() if t.unit_id}
    units = {x.id: x for x in s.query(Unit).filter(Unit.id.in_(uids or {0}))}
    cids = {x.course_id for x in units.values()} | {q.course_id for _, q, _, _ in batches if not q.unit_id}
    courses = {c.id: c.name for c in s.query(Course).filter(Course.id.in_(cids or {0}))}
    return topics, units, courses
def tally(batches, ctx, staff):
    """Groups one person's answers by topic. A question with no topic (or whose topic is a draft they can't see, was deleted or moved out of the quiz's
    unit or course) counts under its area label if it has one, else under its unit, else under the course test itself."""
    topics, units, courses = ctx; acc = {}
    for _, q, qm, detail in batches:
        un = units.get(q.unit_id) if q.unit_id else None; cid = un.course_id if un else (q.course_id if not q.unit_id else None)
        for d in detail:
            qid, ok = d[0], d[1]; x = qm.get(qid)
            if not x: continue
            t = topics.get(x.topic_id) if x.topic_id else None
            if t and (t.published is False and not staff): t = None
            if t and (t.unit_id != q.unit_id if q.unit_id else (units.get(t.unit_id) is None or units[t.unit_id].course_id != cid)): t = None
            tu = units.get(t.unit_id) if t else un
            if t: key, title = ("t", t.id), t.title
            elif x.area: key, title = ("a", cid, x.area.strip().lower()), x.area.strip()
            elif q.unit_id: key, title = ("u", q.unit_id), (un.name + " · general questions") if un else q.title
            else: key, title = ("q", q.id), q.title + " · general questions"
            a = acc.setdefault(key, {"key": key, "topic_id": t.id if t else None, "unit_id": tu.id if tu else None, "unit": tu.name if tu else "", "course_id": cid,
                                     "course": courses.get(cid, ""), "title": title, "area": key[0] == "a", "correct": 0, "total": 0})
            a["correct"] += ok; a["total"] += 1
    for a in acc.values(): a["percent"] = round(100 * a["correct"] / a["total"]); a["status"] = area_status(a["percent"])
    return acc
def area_summary(areas):  # one plain sentence on what the learner is good at and what to revisit
    good = [a["title"] for a in sorted(areas, key=lambda a: -a["percent"]) if a["status"] == "strong"][:3]; weak = [a["title"] for a in areas if a["status"] == "needs_study"][:3]
    if not areas: return ""
    if good and weak: return f"Good at {', '.join(good)}. Needs another round: {', '.join(weak)}."
    if good: return f"Good at {', '.join(good)}." + ("" if len(good) == len(areas) else " Keep going on the rest.")
    if weak: return f"Needs another round: {', '.join(weak)}."
    return "Getting there in every area. One more round of practice should make them strong."
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
    areas = areas_for(latest_batches(s, [u.id], qids), s, is_staff(u), u.id)
    by = defaultdict(list)
    for a in areas: by[a["course_id"]].append(a)
    courses = [{"course_id": cid, "course": L[0]["course"], "percent": round(100 * sum(a["correct"] for a in L) / sum(a["total"] for a in L)), "areas": L} for cid, L in by.items()]
    return {"quizzes_taken": len(qids), "courses": courses, "strong": sorted([a for a in areas if a["status"] == "strong"], key=lambda a: (-a["percent"], a["title"])),
            "getting_there": [a for a in areas if a["status"] == "getting_there"], "needs_study": [a for a in areas if a["status"] == "needs_study"]}
def course_quiz_ids(cid, s):  # published unit quizzes and course tests of a course
    return [q.id for q in s.query(Quiz).join(Unit, Unit.id == Quiz.unit_id).filter(Unit.course_id == cid, Quiz.published == True)] + \
           [i for (i,) in s.query(Quiz.id).filter(Quiz.unit_id.is_(None), Quiz.course_id == cid, Quiz.published == True)]  # noqa: E712
def course_users(c, s):
    sems = {x.id: x for x in s.query(Semester)}; links = defaultdict(list)
    for l in s.query(CourseLink).filter_by(course_id=c.id): links[c.id].append(l.semester_id)
    return course_audience(c, s.query(User).filter_by(role="student").all(), sems, links)
@app.get("/api/reports/courses/{cid}/weak-areas")
def class_weak_areas(cid: int, u: User = Depends(staff), s: Session = Depends(db)):
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    aud = [x for x in course_users(c, s) if x.active]; batches = latest_batches(s, [x.id for x in aud], course_quiz_ids(cid, s))
    n, areas = class_areas(batches, s)
    return {"course": c.name, "students_with_results": n, "areas": areas}
def class_areas(batches, s):  # every student's areas added up: (students with results, rows weakest first)
    ctx = area_context(batches, s); per = defaultdict(list)
    for b in batches: per[b[0]].append(b)
    agg = {}
    for uid, bs in per.items():
        for key, a in tally(bs, ctx, True).items():
            g = agg.setdefault(key, {**{k: v for k, v in a.items() if k not in ("key", "status", "percent")}, "correct": 0, "total": 0, "students": 0, "strong": 0, "getting_there": 0, "needs_study": 0})
            g["correct"] += a["correct"]; g["total"] += a["total"]; g["students"] += 1; g[a["status"]] += 1
    rows = sorted(agg.values(), key=lambda g: (round(100 * g["correct"] / g["total"]), g["title"]))
    return len(per), [{**g, "percent": round(100 * g["correct"] / g["total"])} for g in rows]
@app.post("/api/quizzes")
def new_quiz(b: QuizIn, u: User = Depends(staff), s: Session = Depends(db)):
    if b.unit_id:
        un = s.get(Unit, b.unit_id)
        if not un: raise HTTPException(400, "Choose a unit for this quiz")
        need_edit(u, un.course_id, s); q = Quiz(unit_id=un.id, course_id=un.course_id, **quiz_fields(b))
    else:
        if not b.course_id or not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course or unit for this quiz")
        need_edit(u, b.course_id, s); q = Quiz(unit_id=None, course_id=b.course_id, **quiz_fields(b))
    s.add(q); s.commit(); return {"id": q.id}
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
    if len(b.questions) > max_questions(q): raise HTTPException(400, f"A quiz can have up to {max_questions(q)} questions")
    rows = [clean_question(q, x, i, s) for i, x in enumerate(b.questions, 1)]
    s.query(Question).filter_by(quiz_id=qid).delete()  # past attempts keep their scores; their per-question review covers the questions that still match
    for i, v in enumerate(rows): s.add(Question(quiz_id=qid, pos=i, **v))
    s.commit(); return {"ok": True, "count": len(rows)}
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
    if have + len(ids) > max_questions(q): raise HTTPException(400, f"A quiz can have up to {max_questions(q)} questions")
    if b.topic_id is not None and not topic_fits(q, b.topic_id, s): raise HTTPException(400, f"Pick a topic from this {'unit' if q.unit_id else 'course'}")
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
        check_course_access(u, cid, s); quiz_unit_open(q, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    mine = s.query(Attempt).filter_by(quiz_id=qid, user_id=u.id).order_by(Attempt.id).all()
    co = s.get(Course, cid) if cid else None
    return {"id": q.id, "title": q.title, "pass_percent": q.pass_percent, "published": bool(q.published), "reveal": bool(q.reveal), "unit_id": q.unit_id, "course_id": cid,
            "course": co.name if co else "", "kind": "unit" if q.unit_id else "course", "can_edit": staff_view,
            "questions": [{**question_view(x), **({"correct": x.correct, "explanation": x.explanation, "topic_id": x.topic_id, "area": x.area or ""} if staff_view else {})} for x in qs],
            **({"topics": quiz_topics(q, s)} if staff_view else {}),
            "attempts": len(mine), "best": max([a.percent for a in mine], default=None), "latest": mine[-1].percent if mine else None, "latest_id": mine[-1].id if mine else None}
def question_view(x):  # what anyone taking the quiz may see of a question
    return {"id": x.id, "text": x.text, "options": json.loads(x.options), "image": x.image or "", "option_images": [v or "" for v in json.loads(x.option_images)] if x.option_images else []}
def quiz_topics(q, s):  # the topics a question of this quiz may be tied to
    if q.unit_id: return [{"id": t.id, "title": t.title} for t in s.query(Topic).filter_by(unit_id=q.unit_id).order_by(*ORDER[Topic])]
    return course_topics(q.course_id, s)
@app.get("/api/courses/{cid}/topics")
def course_topic_list(cid: int, u: User = Depends(staff), s: Session = Depends(db)):  # for tying a new course test's questions to topics
    if not s.get(Course, cid): raise HTTPException(404, "Course not found")
    need_edit(u, cid, s); return course_topics(cid, s)
def course_topics(cid, s):
    units = s.query(Unit).filter_by(course_id=cid).order_by(*ORDER[Unit]).all(); by = defaultdict(list)
    for t in s.query(Topic).filter(Topic.unit_id.in_([x.id for x in units] or [0])).order_by(*ORDER[Topic]): by[t.unit_id].append(t)
    return [{"id": t.id, "title": t.title, "unit": un.name} for un in units for t in by[un.id]]
@app.post("/api/quizzes/{qid}/attempt")
def attempt_quiz(qid: int, b: AttemptIn, u: User = Depends(me), s: Session = Depends(db)):
    q = quiz_or_404(qid, s); cid = quiz_course_id(q, s)
    if not q.published and not (u.role == "admin" or can_edit(u, cid, s)): raise HTTPException(404, "Quiz not found")
    check_course_access(u, cid, s)
    if not can_edit(u, cid, s): quiz_unit_open(q, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all()
    if not qs: raise HTTPException(400, "This quiz has no questions yet")
    if len(b.answers) != len(qs): raise HTTPException(400, "Answer every question or leave it blank")
    if any(a is not None and not 0 <= a < len(json.loads(x.options)) for a, x in zip(b.answers, qs)): raise HTTPException(400, "One of the answers is not a choice of its question")
    key = u.role == "admin" or can_edit(u, cid, s) or bool(q.reveal)  # the answer key goes back only to people who can edit the quiz, or to everyone when the quiz reveals it
    results = [{"chosen": a, "ok": a == x.correct, **({"correct": x.correct, "explanation": x.explanation} if key else {})} for a, x in zip(b.answers, qs)]
    score = sum(r["ok"] for r in results); pct = round(100 * score / len(qs))
    detail = [[x.id, int(r["ok"]), a] for x, r, a in zip(qs, results, b.answers)]
    at = Attempt(quiz_id=qid, user_id=u.id, score=score, total=len(qs), percent=pct, detail=json.dumps(detail)); s.add(at); s.commit()
    areas = areas_for([(u.id, q, {x.id: x for x in qs}, detail)], s, is_staff(u), u.id)
    return {"attempt_id": at.id, "score": score, "total": len(qs), "percent": pct, "passed": pct >= q.pass_percent, "pass_percent": q.pass_percent, "reveal": key, "results": results, "areas": areas,
            "summary": area_summary(areas)}

# ---- MCQ tests from a CSV: parse and preview, then the questions are saved with PUT /api/quizzes/{id}/questions ----
class QuizCsvIn(BaseModel): csv: str; unit_id: int = 0; course_id: int = 0
LETTERS = "abcdef"
CSV_ALIASES = {"question": ("question", "question_text", "q"), "correct": ("correct", "answer", "correct_answer", "key"), "explanation": ("explanation", "solution", "reason"),
               "topic": ("topic",), "area": ("area", "skill", "concept", "tag", "subject_area"), "unit": ("unit",), "image": ("question_image", "image", "q_image")}
for _l in LETTERS:
    CSV_ALIASES["opt_" + _l] = (_l, "option_" + _l, "answer_" + _l, "choice_" + _l, "opt_" + _l)
    CSV_ALIASES["img_" + _l] = (_l + "_image", "option_" + _l + "_image", "image_" + _l, "choice_" + _l + "_image", "answer_" + _l + "_image")
def head_key(h): return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")
def image_ref(v):  # a CSV image cell -> (url, file name): an uploaded url is used as it is, anything else is a file name to upload in the preview
    v = (v or "").strip()
    if not v: return "", ""
    if IMG_URL.fullmatch(v): return v, ""
    return "", re.split(r"[\\/]", v)[-1][:200]
def read_csv_rows(text):
    text = text.lstrip("\ufeff")
    if len(text) > 2_000_000: raise HTTPException(400, "The file is too large. Keep it under 2 MB.")
    try: dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error: dialect = csv.excel
    return [r for r in csv.reader(io.StringIO(text), dialect) if any((c or "").strip() for c in r)]
@app.post("/api/quizzes/parse-csv")
def parse_quiz_csv(b: QuizCsvIn, u: User = Depends(staff), s: Session = Depends(db)):
    """Reads an MCQ CSV and returns the questions for a preview. Nothing is saved. Image cells name files that are uploaded in the preview."""
    if b.unit_id:
        un = s.get(Unit, b.unit_id)
        if not un: raise HTTPException(400, "Choose a unit")
        cid, topics = un.course_id, [(t, un) for t in s.query(Topic).filter_by(unit_id=un.id)]
    else:
        if not b.course_id or not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course")
        cid = b.course_id; units = {x.id: x for x in s.query(Unit).filter_by(course_id=cid)}
        topics = [(t, units[t.unit_id]) for t in s.query(Topic).filter(Topic.unit_id.in_(list(units) or [0]))]
    need_edit(u, cid, s)
    rows = read_csv_rows(b.csv)
    if not rows: raise HTTPException(400, "The file is empty")
    head = [head_key(h) for h in rows[0]]; col = {}
    for name, keys in CSV_ALIASES.items():
        hit = next((i for i, h in enumerate(head) if h in keys), None)
        if hit is not None: col[name] = hit
    opt_cols = [l for l in LETTERS if "opt_" + l in col]
    if "question" not in col or len(opt_cols) < 2 or "correct" not in col:
        raise HTTPException(400, "The first row must name the columns: question, a, b, c, d, correct. Optional: explanation, topic, area, question_image, a_image to f_image. Download the template to see the format.")
    top = 100 if b.unit_id else MAX_QUESTIONS
    if len(rows) - 1 > top: raise HTTPException(400, f"Too many questions. A {'unit quiz' if b.unit_id else 'course test'} can have up to {top}.")
    cell = lambda r, k: (r[col[k]] if k in col and col[k] < len(r) else "").strip()
    by_title = defaultdict(list)
    for t, un in topics: by_title[t.title.strip().lower()].append((t, un))
    out, errors, warnings = [], [], []
    for n, r in enumerate(rows[1:], start=2):
        text, (qimg, qname) = cell(r, "question"), image_ref(cell(r, "image"))
        opts = [(cell(r, "opt_" + l), *image_ref(cell(r, "img_" + l))) for l in opt_cols]
        while opts and not any(opts[-1]): opts.pop()  # answers left blank at the end are not there
        if not text and not (qimg or qname): errors.append({"row": n, "error": "No question text"}); continue
        if len(opts) < 2: errors.append({"row": n, "error": "Needs at least two answers"}); continue
        gap = next((LETTERS[i].upper() for i, o in enumerate(opts) if not any(o)), None)
        if gap: errors.append({"row": n, "error": f"Answer {gap} is empty. Give it text or an image, or move the later answers up"}); continue
        raw = cell(r, "correct"); k = -1
        if re.fullmatch(r"[A-Fa-f]", raw): k = LETTERS.index(raw.lower())
        elif re.fullmatch(r"[1-6]", raw): k = int(raw) - 1
        elif raw: k = next((i for i, o in enumerate(opts) if o[0] and o[0].lower() == raw.lower()), -1)
        if re.fullmatch(r"[A-Fa-f]\s*[,;/&]\s*[A-Fa-f].*", raw): errors.append({"row": n, "error": "Only one correct answer is allowed"}); continue
        if not 0 <= k < len(opts): errors.append({"row": n, "error": f"\"correct\" must be a letter from A to {LETTERS[len(opts) - 1].upper()}, its number, or the exact answer text"}); continue
        tname, uname, area, tid, ttitle = cell(r, "topic"), cell(r, "unit").lower(), cell(r, "area")[:150], None, ""
        if tname:
            hits = [x for x in by_title.get(tname.lower(), []) if not uname or x[1].name.strip().lower() == uname]
            if len(hits) > 1: warnings.append(f"Row {n}: more than one topic is called \"{tname}\". Add a unit column to pick one. The first was used.")
            if hits: tid, ttitle = hits[0][0].id, hits[0][0].title
            else:
                warnings.append(f"Row {n}: no topic called \"{tname}\" in this {'unit' if b.unit_id else 'course'}, so it is grouped as the area \"{tname[:150]}\"")
                area = area or tname[:150]
        out.append({"row": n, "text": text, "options": [o[0] for o in opts], "correct": k, "explanation": cell(r, "explanation"), "topic_id": tid, "topic": ttitle, "area": area,
                    "image": qimg, "image_name": qname, "option_images": [o[1] for o in opts], "option_image_names": [o[2] for o in opts]})
    names = sorted({x["image_name"] for x in out if x["image_name"]} | {m for x in out for m in x["option_image_names"] if m}, key=str.lower)
    return {"questions": out, "count": len(out), "errors": errors[:200], "error_count": len(errors), "warnings": warnings[:200], "images_needed": names}

# ---- results: final scores with a drill-down from the class to one student's answers ----
def quiz_for_staff(qid, u, s):
    q = quiz_or_404(qid, s); cid = quiz_course_id(q, s); need_edit(u, cid, s)
    return q, cid
def students_in(cid, s):  # active students who have the course in their list
    c = s.get(Course, cid) if cid else None
    return [x for x in course_users(c, s) if x.active] if c else []
def attempt_row(a, q): return {"id": a.id, "at": iso(a.at), "score": a.score, "total": a.total, "percent": a.percent, "passed": a.percent >= q.pass_percent}
def iso(t): return t.isoformat() + "Z" if t else None
def stats(vals):
    if not vals: return {"average": None, "median": None, "highest": None, "lowest": None}
    v = sorted(vals); m = len(v) // 2
    return {"average": round(sum(v) / len(v)), "median": v[m] if len(v) % 2 else round((v[m - 1] + v[m]) / 2), "highest": v[-1], "lowest": v[0]}
@app.get("/api/quizzes/{qid}/results")
def quiz_results(qid: int, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    """One test for the class: summary, every student's best and latest score with strengths, each question's answers, and the class's areas.
    The final score is a student's best attempt; strengths and question analysis use each student's latest attempt, so a retake replaces the earlier result."""
    q, cid = quiz_for_staff(qid, u, s)
    qs = s.query(Question).filter_by(quiz_id=qid).order_by(Question.pos, Question.id).all(); qm = {x.id: x for x in qs}
    atts = s.query(Attempt).filter_by(quiz_id=qid).order_by(Attempt.id).all()
    people = {x.id: x for x in s.query(User).filter(User.id.in_({a.user_id for a in atts} or {0}), User.role == "student")}
    by = defaultdict(list)
    for a in atts:
        if a.user_id in people: by[a.user_id].append(a)
    aud = students_in(cid, s); ctx_batches = [(uid, q, qm, json.loads(L[-1].detail)) for uid, L in by.items() if L[-1].detail]
    ctx = area_context(ctx_batches, s); mine = {b[0]: tally([b], ctx, True) for b in ctx_batches}
    students = []
    for uid, L in by.items():
        best = max(L, key=lambda a: (a.percent, a.id)); areas = mine.get(uid, {}).values()
        students.append({"user_id": uid, "name": people[uid].name, "email": people[uid].email, "attempts": len(L), "best": best.percent, "best_id": best.id, "latest": L[-1].percent,
                         "latest_id": L[-1].id, "passed": best.percent >= q.pass_percent, "last_at": iso(L[-1].at),
                         "strong": [a["title"] for a in areas if a["status"] == "strong"], "needs_study": [a["title"] for a in areas if a["status"] == "needs_study"]})
    students.sort(key=lambda r: (-r["best"], r["name"].lower()))
    not_taken = sorted([x for x in aud if x.id not in by], key=lambda x: x.name.lower())
    if format == "csv":
        return csv_response(f"results-{q.title}.csv".replace(" ", "_"), ["Name", "Email", "Attempts", "Final score % (best)", "Latest %", "Passed", "Last attempt", "Strong areas", "Needs another round of study"],
                            [[r["name"], r["email"], r["attempts"], r["best"], r["latest"], "yes" if r["passed"] else "no", r["last_at"] or "", "; ".join(r["strong"]), "; ".join(r["needs_study"])] for r in students] +
                            [[x.name, x.email, 0, "", "", "not taken", "", "", ""] for x in not_taken])
    best = [r["best"] for r in students]; dist = [0] * 10
    for v in best: dist[min(v // 10, 9)] += 1
    qstat = {x.id: {"answered": 0, "blank": 0, "right": 0, "total": 0, "picks": [0] * len(json.loads(x.options)), "picks_known": 0} for x in qs}
    for _, _, _, detail in ctx_batches:
        for d in detail:
            st = qstat.get(d[0])
            if not st: continue
            st["total"] += 1; st["right"] += d[1]
            if len(d) > 2:
                st["picks_known"] += 1
                if d[2] is None: st["blank"] += 1
                elif 0 <= d[2] < len(st["picks"]): st["picks"][d[2]] += 1; st["answered"] += 1
    topics = {t.id: t.title for t in s.query(Topic).filter(Topic.id.in_({x.topic_id for x in qs if x.topic_id} or {0}))}
    questions = [{**question_view(x), "pos": i + 1, "correct": x.correct, "explanation": x.explanation or "", "area": topics.get(x.topic_id) or x.area or "",
                  **qstat[x.id], "percent": round(100 * qstat[x.id]["right"] / qstat[x.id]["total"]) if qstat[x.id]["total"] else None} for i, x in enumerate(qs)]
    n, areas = class_areas(ctx_batches, s)
    return {"id": q.id, "title": q.title, "course_id": cid, "pass_percent": q.pass_percent, "published": bool(q.published), "questions_count": len(qs),
            "summary": {"students": len(set(x.id for x in aud) | set(by)), "took": len(by), "not_taken": len(not_taken), "attempts": sum(len(L) for L in by.values()),
                        "passed": sum(r["passed"] for r in students), "pass_rate": round(100 * sum(r["passed"] for r in students) / len(students)) if students else None,
                        **stats(best), "average_latest": round(sum(r["latest"] for r in students) / len(students)) if students else None,
                        "distribution": [{"label": f"{i * 10}–{i * 10 + 9 if i < 9 else 100}", "count": c} for i, c in enumerate(dist)]},
            "students": students, "not_taken": [{"user_id": x.id, "name": x.name, "email": x.email} for x in not_taken[:200]],
            "questions": questions, "areas": areas, "students_with_results": n}
@app.get("/api/quizzes/{qid}/attempts")
def quiz_attempts(qid: int, user_id: int = 0, u: User = Depends(me), s: Session = Depends(db)):  # one person's attempts, newest first: your own, or a student's for staff who can edit the quiz
    q = quiz_or_404(qid, s); who = user_id or u.id
    if who != u.id: quiz_for_staff(qid, u, s)
    p = s.get(User, who)
    return {"quiz": q.title, "user": p.name if p else "", "pass_percent": q.pass_percent,
            "items": [attempt_row(a, q) for a in s.query(Attempt).filter_by(quiz_id=qid, user_id=who).order_by(Attempt.id.desc()).limit(100)]}
@app.get("/api/attempts/{aid}")
def attempt_detail(aid: int, u: User = Depends(me), s: Session = Depends(db)):
    """Question-by-question review of one attempt. The answer key is shown to staff who can edit the quiz, or to the student when the quiz reveals it."""
    a = s.get(Attempt, aid)
    if not a: raise HTTPException(404, "Attempt not found")
    q = quiz_or_404(a.quiz_id, s); cid = quiz_course_id(q, s); staff_view = u.role == "admin" or can_edit(u, cid, s)
    if a.user_id != u.id and not staff_view: raise HTTPException(403, "You can only see your own attempts")
    key = staff_view or bool(q.reveal)
    qm = {x.id: x for x in s.query(Question).filter_by(quiz_id=q.id)}; detail = json.loads(a.detail) if a.detail else []
    topics = {t.id: t.title for t in s.query(Topic).filter(Topic.id.in_({x.topic_id for x in qm.values() if x.topic_id} or {0}))}
    items, gone = [], 0
    for d in detail:
        x = qm.get(d[0])
        if not x: gone += 1; continue
        items.append({**question_view(x), "ok": bool(d[1]), "chosen": d[2] if len(d) > 2 else None, "chosen_known": len(d) > 2, "area": topics.get(x.topic_id) or x.area or "",
                      **({"correct": x.correct, "explanation": x.explanation or ""} if key else {})})
    areas = areas_for([(a.user_id, q, qm, detail)], s, is_staff(u), a.user_id) if detail else []
    p = s.get(User, a.user_id); co = s.get(Course, cid) if cid else None
    return {**attempt_row(a, q), "quiz_id": q.id, "quiz": q.title, "course": co.name if co else "", "user": p.name if p else "", "user_id": a.user_id, "pass_percent": q.pass_percent,
            "reveal": key, "questions": items, "changed": gone, "no_detail": not detail, "areas": areas, "summary": area_summary(areas)}
def course_tests(cid, s, published_only=True):  # course tests first, then unit quizzes in unit order
    units = s.query(Unit).filter_by(course_id=cid).order_by(*ORDER[Unit]).all(); un = {x.id: x for x in units}; rank = {x.id: i for i, x in enumerate(units)}
    qs = s.query(Quiz).filter(or_(and_(Quiz.unit_id.is_(None), Quiz.course_id == cid), Quiz.unit_id.in_(list(un) or [0])))
    if published_only: qs = qs.filter(Quiz.published == True)  # noqa: E712
    return sorted([(q, un.get(q.unit_id)) for q in qs], key=lambda x: (x[1] is not None, rank.get(x[0].unit_id, 0), x[0].id))
@app.get("/api/courses/{cid}/gradebook")
def gradebook(cid: int, format: str = "json", u: User = Depends(staff), s: Session = Depends(db)):
    """Every student's final (best) score in every published test and quiz of a course. The final course score is the average over the tests a student took."""
    c = s.get(Course, cid)
    if not c: raise HTTPException(404, "Course not found")
    need_edit(u, cid, s)
    tests = course_tests(cid, s); tids = [q.id for q, _ in tests]; aud = students_in(cid, s)
    best = defaultdict(dict)
    for qid, uid, b in s.query(Attempt.quiz_id, Attempt.user_id, func.max(Attempt.percent)).filter(Attempt.quiz_id.in_(tids or [0])).group_by(Attempt.quiz_id, Attempt.user_id): best[uid][qid] = b
    extra = [x for x in s.query(User).filter(User.id.in_(set(best) - {x.id for x in aud} or {0}), User.role == "student")]  # took a test, no longer in the course
    rows = []
    for x in sorted(aud + extra, key=lambda x: x.name.lower()):
        got = best.get(x.id, {}); vals = [got[t] for t in tids if t in got]
        rows.append({"user_id": x.id, "name": x.name, "email": x.email, "scores": [got.get(t) for t in tids], "taken": len(vals), "final": round(sum(vals) / len(vals)) if vals else None,
                     "passed": sum(got[q.id] >= q.pass_percent for q, _ in tests if q.id in got)})
    cols = [{"id": q.id, "title": q.title, "unit": un.name if un else "", "kind": "unit" if un else "course", "pass_percent": q.pass_percent,
             **stats([r["scores"][i] for r in rows if r["scores"][i] is not None]), "took": sum(r["scores"][i] is not None for r in rows)} for i, (q, un) in enumerate(tests)]
    if format == "csv":
        return csv_response(f"gradebook-{c.name}.csv".replace(" ", "_"), ["Name", "Email"] + [t["title"] for t in cols] + ["Tests taken", "Final score % (average of tests taken)"],
                            [[r["name"], r["email"]] + ["" if v is None else v for v in r["scores"]] + [r["taken"], "" if r["final"] is None else r["final"]] for r in rows])
    return {"course": c.name, "tests": cols, "students": rows, "summary": stats([r["final"] for r in rows if r["final"] is not None])}
@app.get("/api/me/scores")
def my_scores(u: User = Depends(me), s: Session = Depends(db)):
    """Your final score in each course you can see, with each test's best and latest result for the drill-down."""
    mine = defaultdict(list)
    for a in s.query(Attempt).filter_by(user_id=u.id).order_by(Attempt.id): mine[a.quiz_id].append(a)
    out, seen = [], set()
    for p in tree(u, s):
        for sm in p["semesters"]:
            for c in sm["courses"]:
                if c["id"] in seen or (c["archived"] and not is_staff(u)): continue
                seen.add(c["id"])
                found = [(q, "") for q in c.get("tests", [])] + [(q, un["name"]) for un in c["units"] for q in un["quizzes"]]
                tests = []
                for q, unit in found:
                    if not q["published"] or not q["questions"]: continue
                    L = mine.get(q["id"], [])
                    tests.append({"id": q["id"], "title": q["title"], "unit": unit, "kind": "unit" if unit else "course", "questions": q["questions"], "pass_percent": q["pass_percent"],
                                  "attempts": len(L), "best": max([a.percent for a in L], default=None), "latest": L[-1].percent if L else None, "latest_id": L[-1].id if L else None,
                                  "passed": bool(L) and max(a.percent for a in L) >= q["pass_percent"], "nav": [p["id"], sm["id"], c["id"]]})
                if not tests: continue
                done = [t["best"] for t in tests if t["best"] is not None]
                out.append({"course_id": c["id"], "course": c["name"], "program": p["name"], "term": sm["name"], "tests": tests, "taken": len(done),
                            "final": round(sum(done) / len(done)) if done else None, "passed": sum(t["passed"] for t in tests)})
    return {"courses": out}

def drop_topics(s, cond):  # topics with their reading progress, bookmarks and saved AI answers (SQLite would not cascade them)
    ids = [i for (i,) in s.query(Topic.id).filter(cond)]
    if ids:
        for m in (Progress, Bookmark, AICache, TopicVersion, TopicNote, PrivateAnswer, DoubtAnswer): s.query(m).filter(m.topic_id.in_(ids)).delete(synchronize_session=False)
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
        drop_quizzes(s, or_(Quiz.unit_id.in_(uids), and_(Quiz.unit_id.is_(None), Quiz.course_id == c.id))); s.query(CourseLink).filter_by(course_id=c.id).delete(); s.query(CourseFaculty).filter_by(course_id=c.id).delete()
        drop_topics(s, or_(Topic.unit_id.in_(uids), and_(Topic.unit_id.is_(None), Topic.course_id == c.id)))
        s.query(CourseMaterial).filter_by(course_id=c.id).delete(); s.query(Unit).filter_by(course_id=c.id).delete(); s.delete(c)
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
            if given and not (given.isdigit() and 1 <= int(given) <= TOP_TERM): errors.append({"row": n, "error": f"semester_no must be a number from 1 to {TOP_TERM}"}); continue
            p = get("program", v["program"].lower(), lambda: Program(name=v["program"], pattern="year" if re.match(r"\s*(year|yr)\b", v["semester"], re.I) else "grade" if re.match(r"\s*(grade|std|class)\b", v["semester"], re.I) else "semester"))
            if (p.id, v["semester"].lower()) not in cache["semester"]:  # a new semester gets semester_no, or else the number in its name, if that is free
                no = int(given) if given else sem_no(v["semester"])
                if given and no in used[p.id]: errors.append({"row": n, "error": f"{v['program']} already has semester {no}"}); continue
                if given and no > term_max(p): errors.append({"row": n, "error": f"{v['program']} goes up to {term_label(p).lower()} {term_max(p)}"}); continue
                if no in used[p.id] or no is None or no > term_max(p):
                    warnings.append(f"{v['program']} › {v['semester']} has no semester number yet. Set it under Programs."); no = None
                if no is not None: used[p.id].add(no)
            sm = get("semester", (p.id, v["semester"].lower()), lambda: Semester(name=v["semester"], program_id=p.id, semester_no=no))
            co = get("course", (sm.id, v["course"].lower()), lambda: Course(name=v["course"], semester_id=sm.id, program_id=p.id))
            un = get("unit", (co.id, v["unit"].lower()), lambda: Unit(name=v["unit"], course_id=co.id, position=next_pos(s, Unit, course_id=co.id)))
            vals = {k: v[k] for k in TEXT_COLS if v.get(k)}
            if "content" in vals: vals["content_format"] = "markdown"  # CSV content is always Markdown
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
            "content": shown_content(t), "content_format": fmt_of(t), "sample_content": t.sample_content, "question_pattern": t.question_pattern, "guideline": t.guideline, "published": t.published is not False}
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
    old = {k: getattr(v, k) or "" for k in VFIELDS}; old["content_format"] = fmt_of(v); old["content"] = shown_content(v)
    return {"id": v.id, "topic_id": t.id, "saved_at": (v.saved_at.isoformat() + "Z") if v.saved_at else None, "note": v.note or "", **old, "now": {**topic_state(t), "content": shown_content(t)}}
@app.post("/api/topic-versions/{vid}/restore")
def restore_topic_version(vid: int, u: User = Depends(staff), s: Session = Depends(db)):  # puts an old text back as the newest version; nothing is lost, the text it replaces stays in the history
    v, t = version_or_404(vid, u, s); before = topic_state(t)
    for k in VFIELDS: setattr(t, k, getattr(v, k) or "")
    if not t.title.strip(): raise HTTPException(400, "That version has no title")
    record_version(s, t, before, u.id, f"Restored the version of {v.saved_at.strftime('%d %b %Y %H:%M') if v.saved_at else 'earlier'} UTC"); s.commit()
    return {"ok": True}
# ---- a topic from files: an HTML file for the content and a config .md file for the rest; the editor fills in from it, nothing is saved here ----
class TopicFilesIn(BaseModel): unit_id: int; html: str = ""; config: str = ""; images: dict[str, str] = {}; scripts: bool = False  # scripts: keep the page whole as HTML + JavaScript. images: file name -> url from POST /api/uploads
CONFIG_SECTIONS = {"title": ("topic title", "title"), "content": ("topic content", "content", "notes"), "question_pattern": ("question pattern", "question patterns"),
                   "sample_content": ("sample content", "sample answer", "sample question and answer", "sample"),
                   "guideline": ("how an answer should be", "answer guideline", "guideline", "how to answer")}
CONFIG_KEYS = {"title": ("title", "topic title", "name"), "published": ("published", "publish", "status"), "deadline": ("deadline", "learning deadline", "due", "learn by")}
def section_of(heading):
    h = re.sub(r"[^a-z ]", "", heading.lower()).strip()
    return next((k for k, names in CONFIG_SECTIONS.items() if h in names), None)
def parse_topic_config(text):
    """The config .md: optional front matter (title, published, deadline) between --- lines, then '## Question pattern', '## Sample content' and
    '## How an answer should be' sections (and '## Topic title' / '## Topic content' if wanted). Other headings stay inside the section they are in."""
    out, warnings, lines = {}, [], (text or "").replace("\r\n", "\n").lstrip("\ufeff").split("\n")
    if lines and lines[0].strip() == "---" and "---" in [x.strip() for x in lines[1:]]:
        end = 1 + [x.strip() for x in lines[1:]].index("---")
        for ln in lines[1:end]:
            if not ln.strip() or ln.strip().startswith("#"): continue
            k, sep, v = ln.partition(":")
            key = next((n for n, names in CONFIG_KEYS.items() if k.strip().lower() in names), None)
            if not sep or not key: warnings.append(f"Config: \"{ln.strip()[:60]}\" is not a known setting (title, published, deadline)"); continue
            out[key] = v.strip().strip("\"'")
        lines = lines[end + 1:]
    cur, buf, fence, loose = None, defaultdict(list), False, []
    for ln in lines:
        if ln.lstrip().startswith(("```", "~~~")): fence = not fence
        m = None if fence else re.match(r"^(#{1,2})\s+(.+?)\s*#*\s*$", ln)
        sec = section_of(m.group(2)) if m else None
        if sec: cur = sec; continue
        if m and m.group(1) == "#" and cur is None and "title" not in out: out["title"] = m.group(2).strip(); continue
        (buf[cur] if cur else loose).append(ln)
    for k, L in buf.items(): out[k] = "\n".join(L).strip()
    if not buf and any(x.strip() for x in loose): out["content"] = "\n".join(loose).strip()  # a plain Markdown file, with none of the config sections, is the content itself
    elif any(x.strip() for x in loose): warnings.append("Config: text before the first section heading was left out")
    if "published" in out:
        v = out["published"].lower()
        if v in ("yes", "true", "published", "1", "y"): out["published"] = True
        elif v in ("no", "false", "draft", "0", "n"): out["published"] = False
        else: warnings.append("Config: published must be yes or no"); out.pop("published")
    if "deadline" in out:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}:\d{2}))?", out["deadline"])
        if m: out["deadline"] = f"{m.group(1)}T{(m.group(2) or '23:59').zfill(5)}"
        else: warnings.append("Config: deadline must look like 2026-10-20 or 2026-10-20 17:00"); out.pop("deadline")
    return out, warnings
DATA_IMG = re.compile(r"""(src\s*=\s*["'])data:image/[a-z+]+;base64,([A-Za-z0-9+/=\s]+)(["'])""", re.I)
def html_images(raw, given):
    """Embedded (data:) images become uploads; images named by file name use the matching uploaded file; anything else is dropped and named."""
    saved, missing = 0, []
    def keep_data(m):
        nonlocal saved
        try: b = base64.b64decode(re.sub(r"\s", "", m.group(2)), validate=True)
        except Exception: b = b""
        ext = sniff(b)
        if not ext or len(b) > MAX_IMG: missing.append("an embedded image " + ("over 3 MB" if ext else "that could not be read")); return m.group(1) + m.group(3)
        os.makedirs(UPLOADS, exist_ok=True); name = f"{os.urandom(16).hex()}.{ext}"
        with open(os.path.join(UPLOADS, name), "wb") as f: f.write(b)
        saved += 1; return f"{m.group(1)}/api/uploads/{name}{m.group(3)}"
    raw = DATA_IMG.sub(keep_data, raw)
    names = {k.strip().lower(): v for k, v in given.items() if IMG_URL.fullmatch(v or "")}
    def link(m):
        src = htmllib.unescape(m.group(2)).strip()
        if IMG_URL.fullmatch(src) or re.match(r"https?://", src, re.I): return m.group(0)
        hit = names.get(re.split(r"[\\/]", src.split("?")[0])[-1].lower())
        if hit: return f'{m.group(1)}{hit}{m.group(3)}'
        if src: missing.append(re.split(r"[\\/]", src)[-1][:80])
        return m.group(1) + m.group(3)
    raw = re.sub(r"""(<img\b[^>]*?\bsrc\s*=\s*["'])([^"']*)(["'])""", link, raw, flags=re.I)
    raw = re.sub(r"""<img\b(?![^>]*\bsrc\s*=\s*["'][^"']+["'])[^>]*>""", "", raw, flags=re.I)  # an image with nothing to show is removed
    return raw, saved, missing
class HtmlIn(BaseModel): html: str
@app.post("/api/topics/clean-html")
def clean_html_preview(b: HtmlIn, _: User = Depends(staff)):  # the editor previews HTML only after this cleaning, so a pasted file can't run code in the browser
    if len(b.html) > 5_000_000: raise HTTPException(413, "The HTML is too large to preview")
    return {"html": clean_html(b.html)}
@app.post("/api/topics/from-files")
def topic_from_files(b: TopicFilesIn, u: User = Depends(staff), s: Session = Depends(db)):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this topic")
    need_edit(u, un.course_id, s)
    if not b.html.strip() and not b.config.strip(): raise HTTPException(400, "Choose an HTML file, a config file, or both")
    if len(b.html) > 25_000_000 or len(b.config) > 1_000_000: raise HTTPException(413, "The file is too large")
    cfg, warnings = parse_topic_config(b.config) if b.config.strip() else ({}, [])
    out = {k: cfg[k] for k in ("title", "question_pattern", "sample_content", "guideline", "published") if k in cfg}
    if "deadline" in cfg: out["learning_due_at"] = cfg["deadline"]
    images = 0
    if b.html.strip():
        raw, images, missing = html_images(b.html, b.images)
        if b.scripts:  # HTML + JavaScript: the page is kept whole and runs only in a sandboxed frame
            if len(raw) > INTERACTIVE_MAX: raise HTTPException(413, "The HTML file is over 2 MB. Split it into smaller topics.")
            out.update(content=raw, content_format="interactive")
        else:
            if re.search(r"<script\b", raw, re.I): warnings.append("The page's JavaScript was removed. To keep it, choose HTML + JavaScript as the content format, then choose the file again.")
            body = clean_html(raw)
            if len(body) > 2_000_000: raise HTTPException(413, "The HTML content is over 2 MB after cleaning. Split it into smaller topics.")
            if not html_text(body) and "<img" not in body: warnings.append("The HTML file has no text to show")
            out.update(content=body, content_format="html")
        if missing: warnings.append("Images not found, so they were left out: " + ", ".join(dict.fromkeys(missing)) + ". Choose the image files together with the HTML file.")
        if "content" in cfg and cfg["content"]: warnings.append("The config's Topic content section was ignored because the HTML file is the content")
        if "title" not in out:
            m = re.search(r"<title[^>]*>(.*?)</title>", b.html, re.S | re.I) or re.search(r"<h1[^>]*>(.*?)</h1>", b.html, re.S | re.I)
            if m and html_text(m.group(1)): out["title"] = html_text(m.group(1))[:200]
    elif cfg.get("content"): out.update(content=cfg["content"], content_format="markdown")
    if out.get("title"): out["title"] = out["title"][:200]
    return {**out, "images_saved": images, "warnings": warnings}
class BulkFile(BaseModel): name: str; text: str
class BulkTopicsIn(BaseModel): files: list[BulkFile]; images: dict[str, str] = {}; scripts: bool = False; published: bool = False; dry_run: bool = True
def natural(name): return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", re.split(r"[\\/]", name)[-1])]  # "2 Intro" before "10 Summary"
@app.post("/api/units/{uid}/topics/bulk")
def bulk_topics(uid: int, b: BulkTopicsIn, u: User = Depends(staff), s: Session = Depends(db)):
    """Many topic files at once: one topic per .html/.htm or .md file, added to the unit in file-name order. A dry run shows what would be
    made. HTML is cleaned unless scripts is set (then each page is kept whole as HTML + JavaScript); a .md file is the content, or a config
    file with sections (title, question pattern, sample, guideline, published, deadline). Images are matched by file name, as for one topic."""
    un = s.get(Unit, uid)
    if not un: raise HTTPException(404, "Unit not found")
    need_edit(u, un.course_id, s)
    if not b.files: raise HTTPException(400, "Choose some .html or .md files")
    if len(b.files) > 200: raise HTTPException(400, "Choose up to 200 files at a time")
    rows, made = [], 0
    for f in sorted(b.files, key=lambda f: natural(f.name)):
        base = re.split(r"[\\/]", f.name)[-1]; ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""; stem = base.rsplit(".", 1)[0] if "." in base else base
        row = {"file": f.name[:200], "warnings": [], "ok": True}; fields = {}
        if ext in ("html", "htm"):
            m = re.search(r"<title[^>]*>(.*?)</title>", f.text, re.S | re.I) or re.search(r"<h1[^>]*>(.*?)</h1>", f.text, re.S | re.I)
            fields["title"] = html_text(m.group(1)) if m and html_text(m.group(1)) else stem
            raw = f.text
            if not b.dry_run: raw, _, missing = html_images(raw, b.images)
            else: missing = [x for x in re.findall(r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", raw, re.I)
                             if not re.match(r"(https?:|data:|/api/uploads/)", x, re.I) and re.split(r"[\\/]", x.split("?")[0])[-1].strip().lower() not in {k.strip().lower() for k in b.images}]
            if missing: row["warnings"].append("Images not found, so they are left out: " + ", ".join(dict.fromkeys(re.split(r"[\\/]", x)[-1][:60] for x in missing)))
            if b.scripts: fields.update(content=raw, content_format="interactive"); limit = INTERACTIVE_MAX
            else:
                fields.update(content=clean_html(raw), content_format="html"); limit = 2_000_000
                if re.search(r"<script\b", raw, re.I): row["warnings"].append("Its JavaScript is removed (tick Keep JavaScript to keep it)")
            if len(fields["content"]) > limit: row.update(ok=False); row["warnings"].append("Over 2 MB. Split it into smaller files.")
        elif ext in ("md", "markdown", "txt"):
            cfg, warns = parse_topic_config(f.text); row["warnings"] += warns
            fields = {k: cfg[k] for k in ("question_pattern", "sample_content", "guideline") if cfg.get(k)}
            fields.update(title=cfg.get("title") or stem, content=cfg.get("content", ""), content_format="markdown")
            if "published" in cfg: fields["published"] = cfg["published"]
            if cfg.get("deadline"):
                try: fields["learning_due_at"] = dt.datetime.fromisoformat(cfg["deadline"]) - dt.timedelta(minutes=DAY_OFFSET)  # the deadline is local time
                except ValueError: row["warnings"].append("The deadline was not understood, so none is set")
        else:
            row.update(ok=False, title=stem, format=""); row["warnings"].append("Not an .html or .md file, so it is skipped"); rows.append(row); continue
        fields["title"] = (fields["title"] or stem).strip()[:200] or "Untitled"
        if not (fields.get("content") or "").strip(): row["warnings"].append("No content in this file")
        row.update(title=fields["title"], format=fields["content_format"], published=fields.get("published", b.published))
        if row["ok"] and not b.dry_run:
            t = Topic(unit_id=un.id, course_id=un.course_id, position=next_pos(s, Topic, unit_id=un.id), **{**fields, "published": fields.get("published", b.published)})
            t.created_by = u.id; s.add(t); s.flush(); record_version(s, t, None, u.id, "Created from " + base[:80]); made += 1
        rows.append(row)
    if not b.dry_run: s.commit()
    return {"dry_run": b.dry_run, "topics": rows, "ready": sum(r["ok"] for r in rows), "created": made}
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
    frame = {"frame_url": f"/api/topics/{tid}/frame?t={frame_pass(u, tid)}"} if fmt_of(t) == "interactive" else {}
    return {**full(t, s), **frame, **learning_state(t.learning_due_at, p, dt.datetime.utcnow()), "my_notes": my_notes(s, u.id, tid), "can_edit": edit, "nav": topic_neighbours(t, edit, s), "bookmarked": s.query(Bookmark).filter_by(user_id=u.id, topic_id=tid).first() is not None}
# ---- interactive topics run in a sandboxed frame; highlights are saved per person ----
# The page gets an opaque origin (CSP sandbox without allow-same-origin), so its scripts can't read the app's sign-in, call the API as the reader or
# touch the app's page. It talks to the app only through postMessage, and the app accepts just the highlight messages below.
FRAME_CSP = ("sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox allow-modals allow-forms allow-downloads; "
             "default-src * data: blob: 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self'")
def frame_pass(u, tid): return jwt.encode({"uid": u.id, "tid": tid, "use": "frame", "k": fp(u), "exp": dt.datetime.utcnow() + dt.timedelta(hours=8)}, SECRET)
@functools.lru_cache(maxsize=1)
def highlighter_js():  # the same highlighter the app bundles (frontend/src/highlighter.js), run inside the frame
    try: return open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "src", "highlighter.js"), encoding="utf-8").read()
    except OSError: return ""
FRAME_BOOT = """(function(){var P=parent,n=0,wait={},h=null;function ask(m){return new Promise(function(ok,no){var k=++n;wait[k]=[ok,no];P.postMessage(Object.assign({zg:1,k:k},m),'*')})}
addEventListener('message',function(e){if(e.source!==P)return;var d=e.data||{};if(!d.zg)return
if(d.k&&wait[d.k]){wait[d.k][d.error?1:0](d);delete wait[d.k];return}
if(d.type==='init'&&!h&&window.zgHighlighter)h=zgHighlighter.attach(document.body,{list:d.list||[],save:function(x){return ask({type:'save',text:x.text,prefix:x.prefix,color:x.color})},remove:function(id){return ask({type:'remove',id:id})},update:function(id,c){return ask({type:'update',id:id,color:c.color})},note:function(id){P.postMessage({zg:1,type:'note',id:id},'*')},explain:function(id){P.postMessage({zg:1,type:'explain',id:id},'*')},changed:function(l){P.postMessage({zg:1,type:'changed',list:l},'*')}})
if(d.type==='scroll'&&h)h.scrollTo(d.id);if(d.type==='unpaint'&&h)h.remove(d.id)});P.postMessage({zg:1,type:'ready'},'*')})()"""
# localStorage and sessionStorage for the page: the sandbox has none (reading them throws), so these stand in. localStorage starts with what this
# person saved last time and sends each change to the app (which saves it); sessionStorage lives as long as the page is open.
STORE_SHIM = """(function(){var P=parent,t=null;function mk(m,keep){var o={getItem:function(k){k=String(k);return Object.prototype.hasOwnProperty.call(m,k)?m[k]:null},
setItem:function(k,v){m[String(k)]=String(v);sync()},removeItem:function(k){delete m[String(k)];sync()},clear:function(){Object.keys(m).forEach(function(k){delete m[k]});sync()},
key:function(i){return Object.keys(m)[i]||null}};Object.defineProperty(o,'length',{get:function(){return Object.keys(m).length}})
function sync(){if(!keep)return;clearTimeout(t);t=setTimeout(function(){P.postMessage({zg:1,type:'store',data:m},'*')},400)}return o}
var ls=mk(__DATA__,__KEEP__),ss=mk({},false);try{Object.defineProperty(window,'localStorage',{value:ls,configurable:true})}catch(e){}
try{Object.defineProperty(window,'sessionStorage',{value:ss,configurable:true})}catch(e){}window.zigora={storage:ls}})()"""
STORE_MAX = 100_000
def frame_page(raw, store=None, keep=False):
    shim = "<script>" + STORE_SHIM.replace("__DATA__", json.dumps(store or {}).replace("<", "\\u003c")).replace("__KEEP__", "true" if keep else "false") + "</script>"
    tail = f"<script>{highlighter_js()}</script><script>{FRAME_BOOT}</script>"
    raw = raw or ""
    m = re.search(r"<head\b[^>]*>", raw, re.I) or re.search(r"<html\b[^>]*>", raw, re.I) or re.match(r"\s*<!doctype[^>]*>", raw, re.I)
    raw = raw[:m.end()] + shim + raw[m.end():] if m else shim + raw  # first, so the page's own scripts find it
    i = raw.lower().rfind("</body>")
    page = raw[:i] + tail + raw[i:] if i >= 0 else raw + tail
    return HTMLResponse(page, headers={"Content-Security-Policy": FRAME_CSP, "X-Frame-Options": "SAMEORIGIN", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
@app.get("/api/topics/{tid}/frame")
def topic_frame(tid: int, t: str = "", s: Session = Depends(db)):
    try: c = jwt.decode(t, SECRET, algorithms=["HS256"])
    except Exception: raise HTTPException(401, "This link has expired. Open the topic again.")
    if c.get("use") != "frame" or c.get("tid") != tid: raise HTTPException(401, "This link has expired. Open the topic again.")
    u, tp = s.get(User, c.get("uid")), s.get(Topic, tid)
    if not u or not u.active or c.get("k") != fp(u): raise HTTPException(401, "Please sign in again")
    if not tp or fmt_of(tp) != "interactive": raise HTTPException(404, "Topic not found")
    check_topic_access(u, tp, s)
    row = s.query(TopicStore).filter_by(user_id=u.id, topic_id=tid).first()
    try: data = json.loads(row.data) if row and row.data else {}
    except ValueError: data = {}
    return frame_page(tp.content, data if isinstance(data, dict) else {}, keep=True)
PREVIEWS = {}  # id -> (expires, html): an unsaved interactive page the editor is previewing, kept a few minutes in memory
class PreviewIn(BaseModel): html: str
@app.post("/api/topics/frame-preview")
def frame_preview(b: PreviewIn, _: User = Depends(staff)):
    if len(b.html) > INTERACTIVE_MAX: raise HTTPException(413, "The page is over 2 MB")
    now = time_now(); [PREVIEWS.pop(k) for k, v in list(PREVIEWS.items()) if v[0] < now]
    while len(PREVIEWS) >= 50: PREVIEWS.pop(next(iter(PREVIEWS)))
    pid = secrets.token_urlsafe(18); PREVIEWS[pid] = (now + 600, b.html); return {"url": f"/api/frame-preview/{pid}"}
@app.get("/api/frame-preview/{pid}")
def frame_preview_page(pid: str):
    v = PREVIEWS.get(pid)
    if not v or v[0] < time_now(): raise HTTPException(404, "This preview has expired. Preview again.")
    return frame_page(v[1])
def time_now(): return dt.datetime.utcnow().timestamp()
class StoreIn(BaseModel): data: dict[str, str]
@app.put("/api/topics/{tid}/store")
def save_store(tid: int, b: StoreIn, u: User = Depends(me), s: Session = Depends(db)):  # an interactive page's localStorage, for this person
    t = s.get(Topic, tid)
    if not t or fmt_of(t) != "interactive": raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    text = json.dumps(b.data)
    if len(text) > STORE_MAX: raise HTTPException(413, "This page is trying to save more than 100 KB")
    row = s.query(TopicStore).filter_by(user_id=u.id, topic_id=tid).first() or TopicStore(user_id=u.id, topic_id=tid)
    row.data, row.updated = text, dt.datetime.utcnow(); s.add(row); s.commit(); return {"ok": True}
HL_COLORS = ("coral", "yellow", "green", "blue")
class HighlightIn(BaseModel): text: str; prefix: str = ""; color: str = "coral"
class HighlightEdit(BaseModel): color: str | None = None; note: str | None = None
def hl_color(c):
    if c not in HL_COLORS: raise HTTPException(400, "Choose coral, yellow, green or blue")
    return c
def hl_row(h, explain=None): return {"id": h.id, "text": h.text, "prefix": h.prefix or "", "color": h.color or "coral", "note": h.note or "", "created": h.created.isoformat() + "Z" if h.created else None,
                                     **({"explain": explain} if explain else {})}
LINE_DAILY = int(os.getenv("AI_LINE_DAILY") or 40)  # new highlight explanations a student can ask the AI for each day (ones already saved are free)
def line_hash(t, prompt, text): return topic_hash(t, "line", prompt + "\n\nPassage: " + " ".join((text or "").split()).lower())
def line_saved(s, t, u, text, prompt=None):  # the saved explanation of this passage in this person's language, if there is one: {"id", "text"}
    hit = s.query(AICache).filter_by(topic_id=t.id, kind="line", chash=line_hash(t, prompt or in_lang(u, prompt_for(s, "line")), text)).first()
    d = step_reply("line", hit.text) if hit else None
    return {"id": hit.id, "text": d["text"]} if d else None
@app.get("/api/topics/{tid}/highlights")
def my_highlights(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    prompt = in_lang(u, prompt_for(s, "line"))
    return {"items": [hl_row(h, line_saved(s, t, u, h.text, prompt)) for h in s.query(Highlight).filter_by(user_id=u.id, topic_id=tid).order_by(Highlight.id)]}
@app.post("/api/topics/{tid}/highlights")
def add_highlight(tid: int, b: HighlightIn, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    text = b.text.strip()
    if not text: raise HTTPException(400, "Select some text to highlight")
    if len(text) > 5000: raise HTTPException(400, "That selection is too long to highlight. Pick a shorter passage.")
    if s.query(Highlight).filter_by(user_id=u.id, topic_id=tid).count() >= 500: raise HTTPException(400, "This topic already has 500 highlights. Remove some first.")
    h = Highlight(user_id=u.id, topic_id=tid, text=text, prefix=(b.prefix or "")[-200:], color=hl_color(b.color)); s.add(h); s.commit(); return hl_row(h)
@app.patch("/api/me/highlights/{hid}")
def edit_highlight(hid: int, b: HighlightEdit, u: User = Depends(me), s: Session = Depends(db)):  # its colour, or the reader's note on it
    h = s.get(Highlight, hid)
    if not h or h.user_id != u.id: raise HTTPException(404, "Highlight not found")
    if b.color is not None: h.color = hl_color(b.color)
    if b.note is not None:
        if len(b.note) > 2000: raise HTTPException(400, "Keep the note under 2000 characters")
        h.note = b.note.strip() or None
    s.commit(); return hl_row(h)
@app.get("/api/me/highlights")
def all_my_highlights(q: str = "", color: str = "", limit: int = 25, offset: int = 0, u: User = Depends(me), s: Session = Depends(db)):
    """Every highlight this person has made, newest first, with the topic it is in: search (passage, note or topic) and a colour filter."""
    qs = s.query(Highlight, Topic, Unit, Course).join(Topic, Topic.id == Highlight.topic_id).outerjoin(Unit, Unit.id == Topic.unit_id) \
        .outerjoin(Course, Course.id == Topic.course_id).filter(Highlight.user_id == u.id)
    if color: qs = qs.filter(func.coalesce(Highlight.color, "coral") == hl_color(color))
    if q.strip():
        like = f"%{q.strip().lower()}%"; qs = qs.filter(or_(*[func.lower(func.coalesce(c, "")).like(like) for c in (Highlight.text, Highlight.note, Topic.title, Course.name)]))
    total = qs.count()
    rows = qs.order_by(Highlight.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    prompt = in_lang(u, prompt_for(s, "line"))
    return {"total": total, "items": [{**hl_row(h, line_saved(s, t, u, h.text, prompt)), "topic_id": t.id, "topic": t.title, "unit": un.name if un else "", "course": co.name if co else ""} for h, t, un, co in rows]}
@app.post("/api/me/highlights/{hid}/explain")
async def explain_highlight(hid: int, u: User = Depends(me), s: Session = Depends(db)):
    """What a highlighted passage means, in a few plain lines. Written when the passage is first highlighted and saved for everyone who highlights the same words."""
    h = s.get(Highlight, hid)
    if not h or h.user_id != u.id: raise HTTPException(404, "Highlight not found")
    t = s.get(Topic, h.topic_id); check_topic_access(u, t, s)
    prompt = in_lang(u, prompt_for(s, "line")); key = key_or_fail(u, s)
    got = line_saved(s, t, u, h.text, prompt)
    if got:
        row = s.get(AICache, got["id"]); note_use(s, u, "line", got["id"], row.author_id if row else None); return {"explain": got}
    if not is_staff(u) and s.query(func.count(StepLog.id)).filter(StepLog.user_id == u.id, StepLog.kind == "line", StepLog.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= LINE_DAILY:
        raise HTTPException(429, f"You have used today's {LINE_DAILY} highlight explanations. Your highlight is saved; ask again tomorrow.")
    f = full(t, s)  # like a doubt: the names and the passage only, never the topic's notes
    msg = f"Program: {f['program']}\nSemester: {f['semester']}\nCourse: {f['course']}\nTopic: {f['title']}\n\nThe passage the student highlighted:\n{h.text[:600]}"
    text, tokens = await ask_ai(u, s, key, prompt, msg, max_tokens=STEPS["line"], kind="line", topic_id=t.id)
    d = step_reply("line", text)
    if not d: raise HTTPException(502, "The AI's answer could not be read. Try again.")
    if not is_staff(u): s.add(StepLog(user_id=u.id, topic_id=t.id, kind="line"))
    row = AICache(topic_id=t.id, kind="line", chash=line_hash(t, prompt, h.text), text=text, tokens=tokens, author_id=author_of(u))
    try: s.add(row); s.commit()
    except Exception: s.rollback(); row = None
    return {"explain": {"id": row.id if row else None, "text": d["text"]}}
@app.delete("/api/me/highlights/{hid}")
def remove_highlight(hid: int, u: User = Depends(me), s: Session = Depends(db)):
    h = s.get(Highlight, hid)
    if not h or h.user_id != u.id: raise HTTPException(404, "Highlight not found")
    s.delete(h); s.commit(); return {"ok": True}
@app.put("/api/topics/{tid}/bookmark")
def add_bookmark(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    if u.role == "admin": raise HTTPException(403, "Bookmarks are for students and faculty")  # admins manage content; they have no study list
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
# ---- the student's day: streak, this week, and what to do next ----
DAY_OFFSET = int(os.getenv("DAY_OFFSET_MINUTES") or 330)  # minutes ahead of UTC that a "day" starts for students (330 = India); streaks count these days
def local_day(t): return (t + dt.timedelta(minutes=DAY_OFFSET)).date()
def note_activity(s, uid):
    day = local_day(dt.datetime.utcnow())
    try:
        if s.query(ActivityDay).filter_by(user_id=uid, day=day).update({"reads": ActivityDay.reads + 1}) == 0: s.add(ActivityDay(user_id=uid, day=day, reads=1))
        s.commit()
    except IntegrityError: s.rollback()  # two requests made today's row at once; the first one counts
def study_days(s, uid, since):  # {local day: activity count}: topics opened, topics completed and quizzes taken
    days = defaultdict(int)
    for d, n in s.query(ActivityDay.day, ActivityDay.reads).filter(ActivityDay.user_id == uid, ActivityDay.day >= since): days[d] += n
    for (t,) in s.query(Progress.completed_at).filter(Progress.user_id == uid, Progress.completed_at.isnot(None)): days[local_day(t)] += 1
    for (t,) in s.query(Progress.last_read).filter(Progress.user_id == uid, Progress.last_read.isnot(None)): days[local_day(t)] += 1  # opens made before day tracking began
    for (t,) in s.query(Attempt.at).filter(Attempt.user_id == uid): days[local_day(t)] += 1
    for (t,) in s.query(StudyAttempt.at).filter(StudyAttempt.user_id == uid): days[local_day(t)] += 1  # courses students build count toward the streak too
    for (t,) in s.query(StudyProgress.opened_at).filter(StudyProgress.user_id == uid, StudyProgress.opened_at.isnot(None)): days[local_day(t)] += 1
    return {d: n for d, n in days.items() if d >= since}
def streak_of(days, today, plan=None):  # plan = a routine's days ("1111110"): then only a missed study day breaks the streak, rest days don't
    d = today if today in days else today - dt.timedelta(days=1)  # no study yet today does not break a streak that is still alive
    n, first = 0, min(days, default=today)
    while d >= first:
        if d in days: n += 1
        elif not plan or plan[d.weekday()] == "1": break
        d -= dt.timedelta(days=1)
    return n
def plan_of(s, uid): r = s.get(Routine, uid); return r.days if r else None
def due_phrase(due, now):  # in the student's own calendar days, so "tomorrow" means tomorrow
    n = (local_day(due) - local_day(now)).days
    if due < now: return f"Overdue by {-n} day{'s' if n != -1 else ''}" if n < 0 else "Overdue since earlier today"
    return "Due today" if n == 0 else "Due tomorrow" if n == 1 else f"Due in {n} days"
@app.get("/api/me/today")
def my_today(u: User = Depends(me), s: Session = Depends(db)):
    now = dt.datetime.utcnow(); today = local_day(now); since = today - dt.timedelta(days=400)
    days = study_days(s, u.id, since); streak = streak_of(days, today, plan_of(s, u.id))
    week = [{"date": (today - dt.timedelta(days=i)).isoformat(), "label": (today - dt.timedelta(days=i)).strftime("%a")[0], "active": (today - dt.timedelta(days=i)) in days, "today": i == 0} for i in range(6, -1, -1)]
    courses, seen = [], set()
    for p in tree(u, s):
        for sm in p["semesters"]:
            for c in sm["courses"]:
                if c["id"] not in seen: seen.add(c["id"]); courses.append((p, sm, c))
    weak = {a["topic_id"]: a for a in my_insights(u, s)["needs_study"] if a.get("topic_id")}
    cand, topics_total, topics_done, bests = {}, 0, 0, []
    def offer(prio, key, item):
        if key not in cand or cand[key][0] < prio: cand[key] = (prio, item)
    for p, sm, c in courses:
        first_new = None
        for q in c.get("tests", []):  # course tests, like unit quizzes
            if not q["published"] or not q["questions"]: continue
            base = {"course": c["name"], "unit": "", "nav": [p["id"], sm["id"], c["id"]]}
            if q["best"] is not None: bests.append(q["best"])
            if q["best"] is None: offer(40, ("q", q["id"]), {**base, "kind": "quiz_new", "title": q["title"], "reason": f"Test not tried yet · {q['questions']} questions", "quiz_id": q["id"]})
            elif q["best"] < q["pass_percent"]: offer(45, ("q", q["id"]), {**base, "kind": "quiz_retake", "title": q["title"], "reason": f"Best so far {q['best']}%, pass mark {q['pass_percent']}%", "quiz_id": q["id"]})
        for un in c["units"]:
            nav = [p["id"], sm["id"], c["id"], un["id"]]; base = {"course": c["name"], "unit": un["name"], "nav": nav}
            for q in un["quizzes"]:
                if not q["published"] or not q["questions"]: continue
                if q["best"] is not None: bests.append(q["best"])
                if q["best"] is None: offer(40, ("q", q["id"]), {**base, "kind": "quiz_new", "title": q["title"], "reason": f"Quiz not tried yet · {q['questions']} questions", "quiz_id": q["id"]})
                elif q["best"] < q["pass_percent"]: offer(45, ("q", q["id"]), {**base, "kind": "quiz_retake", "title": q["title"], "reason": f"Best so far {q['best']}%, pass mark {q['pass_percent']}%", "quiz_id": q["id"]})
            for t in un["topics"]:
                topics_total += 1; topics_done += t["status"] == "completed"
                if t["status"] == "completed": continue
                it = {**base, "title": t["title"], "topic_id": t["id"]}
                if t["learning_due_at"]:
                    due = dt.datetime.fromisoformat(t["learning_due_at"].replace("Z", "")); n = (local_day(due) - local_day(now)).days
                    if t["overdue"]: offer(100 + min(30, max(0, -n)), ("t", t["id"]), {**it, "kind": "overdue", "reason": due_phrase(due, now)})
                    elif n <= 3: offer(80 - n, ("t", t["id"]), {**it, "kind": "due_soon", "reason": due_phrase(due, now)})
                if t["id"] in weak: offer(60 + (60 - weak[t["id"]]["percent"]) / 10, ("t", t["id"]), {**it, "kind": "weak", "reason": f"You scored {weak[t['id']]['percent']}% on questions about this"})
                if t["status"] == "in_progress": offer(50, ("t", t["id"]), {**it, "kind": "resume", "reason": "You started this. Pick up where you left off", "last_read": t["last_read"]})
                elif first_new is None: first_new = (t, it)
        if first_new: offer(30, ("t", first_new[0]["id"]), {**first_new[1], "kind": "next", "reason": "Start the next topic"})
    focus = [i for _, i in sorted(cand.values(), key=lambda x: (-x[0], x[1].get("last_read") or ""))][:4]
    for i in focus: i.pop("last_read", None)
    in7 = [d for d in days if d > today - dt.timedelta(days=7)]
    done7 = s.query(func.count(Progress.id)).filter(Progress.user_id == u.id, Progress.completed_at >= now - dt.timedelta(days=7)).scalar()
    return {"streak": streak, "active_today": today in days, "week": week, "active_days_week": len(in7), "completed_this_week": done7,
            "topics_total": topics_total, "topics_completed": topics_done, "percent": round(100 * topics_done / topics_total) if topics_total else 0,
            "quiz_average": round(sum(bests) / len(bests)) if bests else None, "focus": focus}
@app.post("/api/topics/{tid}/read")
def read(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    p = progress_row(s, u.id, tid)  # opening a topic starts it; it never completes it or undoes a completion
    note_activity(s, u.id)
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

# the short steps on a topic page: each reply is small, ends in something to wonder about, and comes back as JSON the page lays out
STEP_RULES = ("You help a busy engineering student learn one topic in small steps. Use only what fits the topic's notes and stay accurate. "
              "Plain short sentences: no greeting, no filler, no headings. Write formulas in plain text or $...$ math. "
              "Reply with only a JSON object with exactly these keys (the keys stay in English): ")
STEPS = {"gist": 350, "why": 300, "example": 300, "exam": 400, "check": 250, "outline": 400, "simpler": 250, "line": 250}  # the kinds that answer in JSON, and their token limits
EXAM_KINDS = ("answer", "exam", "outline")  # the kinds that also get the question pattern, answer guideline and sample content
PROMPTS = {  # the built-in prompts; an admin can replace any of them under Settings (stored as prompt_<kind>)
 "explain": ("You are a warm, sharp engineering tutor for a busy student with little time. Explain the topic in at most 150 words: one line on why it matters, "
             "the core idea in 2 to 4 short steps, and one tiny example. Use Markdown, plain short sentences, no greeting and no recap. Stay accurate. "
             "Use a small Markdown table only when a comparison is clearer that way: a header row, a separator row, and every row on its own line."),
 "answer": ("You are an engineering exam coach. Write a model answer that follows the given answer guideline and question pattern exactly "
            "(structure, length, marks split, diagrams to sketch, keywords). Use Markdown (tables, when you use them, with every row on its own line). Mirror the style of the sample content."),
 "gist": STEP_RULES + ('{"points": [three strings of at most 18 words each: what it is, the key idea or contrast, why it matters], '
                       '"hook": "one short question (at most 15 words) about the core idea that makes a student curious, answerable from the notes", '
                       '"hook_answer": "the answer to the hook in at most 25 words"}'),
 "why": STEP_RULES + '{"text": "at most 80 words: the reason or mechanism behind the core idea, as cause and effect", "hook": "one short question that goes one step deeper"}',
 "example": STEP_RULES + '{"text": "at most 80 words: one concrete everyday or industrial example of the idea at work, with numbers when natural", "hook": "one short question the example raises"}',
 "exam": STEP_RULES + ('{"question": "one typical short exam question on this topic with its marks in brackets, following the question pattern when one is given", '
                       '"answer": "a model answer in at most 60 words, in points when that is how it is marked, following the answer guideline", "tip": "what examiners look for, at most 15 words"}'),
 "check": STEP_RULES + '{"question": "one question that tests understanding rather than memory of the wording", "answer": "the answer in at most 30 words, with a one-line reason"}',
 "line": STEP_RULES + ('{"text": "at most 60 words: what the highlighted passage means, in plain words, for a student of this course and topic; '
                       'explain any hard term, symbol or step in it"}'),
 "simpler": STEP_RULES + ('{"text": "at most 60 words: the core idea again in the plainest everyday words, with one familiar comparison, for a student who did not get it the first time", '
                          '"hook": "one easy question to check the idea has landed"}'),
 "outline": STEP_RULES + ('{"points": [four to seven short lines: the skeleton of a full-marks answer in order, with the headings, key terms, and the diagram or equation to include], '
                          '"marks": "how the marks usually split, at most 15 words, or an empty string"}'),
 "doubt": ("You are a patient tutor inside a study app. A student marked a phrase they do not understand in one topic. You are told only the program, semester, course and topic names and the phrase itself, never the notes. "
           "Say what the phrase means in that course in at most 90 words: a plain definition first, then one tiny example. If the phrase could mean different things without the notes, say in one short line which meaning you assume. "
           "Use Markdown, plain short sentences, no greeting."),
 "translate": ("Translate these study notes for a student, keeping their meaning exact. Keep the format exactly: the same Markdown (headings, lists, tables, bold) "
               "or, for HTML, every tag and attribute unchanged with only the text between tags translated. Keep formulas, equations, chemical symbols, units, numbers, "
               "code and $...$ maths as they are. The first time a technical term appears, put the English term in brackets after it. Reply with the translation only."),
 "photo": ("A student photographed part of a textbook or question paper and has a question about it. You get the text read from the photo (it may have reading mistakes: "
           "fix obvious ones silently) and, when they ask about a diagram, the photo itself. Answer their question clearly and briefly: at most 150 words, or numbered steps "
           "when they ask you to solve something. Use Markdown and $...$ for maths. If the photo or text is too unclear to answer, say what is unclear and ask them to retake it."),
 "search": ("You are the search helper inside a study app for college students. The student typed a search about something they are studying and the app has no good match in its own notes, "
            "or they asked for a second opinion. Answer it as a clear, accurate tutor: start with a one-line definition, then explain the core idea simply, give one example, and end with 3 recap bullets. "
            "Use Markdown; show comparisons and families of related items as a table with every row on its own line. Fit the answer to the student's program and level when it is given. "
            "If the search is not about their studies, say briefly that you can only help with study topics."),
}
PROMPT_INFO = {"explain": ("Explain tab", "Used when a student opens Explain on a topic. The topic's notes are sent with it."),
               "answer": ("Sample answer tab", "Used for the model answer. The question pattern, answer guideline and sample content are sent with it."),
               "gist": ("Topic gist", "The three points and the curious question at the top of every topic page."),
               "why": ("Topic step: Why?", "A short reason behind the topic's core idea."),
               "example": ("Topic step: Example", "A short real example of the topic."),
               "exam": ("Topic step: Exam angle", "One exam-style question with a short model answer."),
               "check": ("Topic step: Quick check", "One question whose answer the student reveals; nothing is scored."),
               "line": ("Highlight explanation", "Written when a student highlights a passage: what that passage means. Saved per passage, so the same passage costs tokens once."),
               "simpler": ("Topic step: More simply", "Offered after a student says a quick check was not quite right: the idea again in plainer words."),
               "outline": ("Sample answer outline", "The skeleton of a full-marks answer, shown before the full sample answer."),
               "doubt": ("Doubt (a marked phrase)", "Used when a student marks a phrase they do not follow and asks the AI. Only the program, semester, course and topic names and the phrase are sent, never the notes."),
               "translate": ("Notes in my language", "Translates a topic's notes into a student's language (Arabic or Tamil), once per topic and language; everyone shares the translation."),
               "photo": ("Ask from a photo", "Used when a student photographs a question, text or diagram and asks about it. With a diagram, the photo goes to Claude; otherwise only the text read from it goes to DeepSeek."),
               "search": ("Student search", "Used when a search finds nothing in the app's own topics, or the student taps Recheck with AI.")}
MAX_PROMPT = 4000
def prompt_for(s, kind): return setting(s, "prompt_" + kind).strip() or PROMPTS[kind]
def key_or_fail(u, s):  # without a key AI is off, even for saved answers
    key = key_for(u, s)
    if not key and u.self_registered: raise HTTPException(503, NEEDS_OWN_KEY)
    if not key: raise ai_down(u, "no DeepSeek key is saved. Add one under AI config.")
    return key
# ---- plans for self-registered people. Lite: the college's AI key with a small free allowance each local day (searches, and minutes of learning with AI).
# ---- Own key: their own DeepSeek key, no allowance. Pro: an admin lets them use the college's key like a college student until a date.
# ---- Students the college added are not affected. Saved answers never count: they cost nothing.
LITE_SEARCH_KINDS = ("search", "photo", "doubt")  # asking the AI a question; everything else (topic steps, explanations, own courses, translations) is learning time
def pro_active(u): return bool(u.pro_until and u.pro_until > dt.datetime.utcnow())
def ai_plan(u): return "college" if not u.self_registered else "own" if u.ai_key else "pro" if pro_active(u) else "lite"
def lite_limits(s):
    def num(k, d):
        try: return max(0, int(setting(s, k) or d))
        except ValueError: return d
    return num("lite_searches", 10), num("lite_minutes", 20)
def lite_row(s, u):
    day = local_day(dt.datetime.utcnow()); r = s.query(LiteUse).filter_by(user_id=u.id, day=day).first()
    if r: return r
    try:
        with s.begin_nested(): s.add(LiteUse(user_id=u.id, day=day, searches=0, minutes=0, last_min=0))
    except IntegrityError: pass  # another request made today's row first
    return s.query(LiteUse).filter_by(user_id=u.id, day=day).one()
def lite_tick(s, u):  # counts the current minute once, however many requests or heartbeats fall in it
    r = lite_row(s, u); m = int(time.time() // 60)
    if r.last_min != m: r.minutes = (r.minutes or 0) + 1; r.last_min = m
    s.commit(); return r
LITE_MORE = " Saved answers still work. To keep going today, add your own DeepSeek key, or ask your admin for more."
def lite_search_or_fail(u, s):
    if ai_plan(u) != "lite": return
    r = lite_row(s, u); limit = lite_limits(s)[0]
    if (r.searches or 0) >= limit: raise HTTPException(429, f"You have used today's {limit} free AI searches." + LITE_MORE)
    r.searches = (r.searches or 0) + 1; s.commit()
def lite_time_or_fail(u, s):
    if ai_plan(u) != "lite": return
    r = lite_row(s, u); limit = lite_limits(s)[1]
    if (r.minutes or 0) >= limit: raise HTTPException(429, f"You have used today's {limit} free minutes of learning with AI." + LITE_MORE)
    lite_tick(s, u)
def plan_json(u, s):
    p = ai_plan(u); out = {"plan": p, "pro_until": utc_iso(u.pro_until) if p == "pro" else None}
    if p == "lite":
        r = s.query(LiteUse).filter_by(user_id=u.id, day=local_day(dt.datetime.utcnow())).first(); ls, lm = lite_limits(s)
        out.update(searches_used=r.searches if r else 0, searches_limit=ls, minutes_used=r.minutes if r else 0, minutes_limit=lm,
                   asked=s.query(MoreRequest.id).filter_by(user_id=u.id, done_at=None).first() is not None)
    return out
def close_requests(s, uid): s.query(MoreRequest).filter(MoreRequest.user_id == uid, MoreRequest.done_at.is_(None)).update({"done_at": dt.datetime.utcnow()}, synchronize_session=False)
@app.get("/api/me/plan")
def my_plan(u: User = Depends(me), s: Session = Depends(db)): return plan_json(u, s)
@app.post("/api/me/plan/tick")
def plan_tick(u: User = Depends(me), s: Session = Depends(db)):  # sent each minute while a learning screen is open; only lite time is counted
    if ai_plan(u) == "lite": lite_tick(s, u)
    return plan_json(u, s)
class MoreIn(BaseModel): note: str = ""
@app.post("/api/me/plan/request")
def ask_for_more(b: MoreIn, u: User = Depends(me), s: Session = Depends(db)):
    if ai_plan(u) != "lite": raise HTTPException(400, "Your plan already has no daily limit")
    if s.query(MoreRequest.id).filter_by(user_id=u.id, done_at=None).first(): return {"ok": True, "message": "Your request is with your admin."}
    if s.query(func.count(MoreRequest.id)).filter(MoreRequest.user_id == u.id, MoreRequest.at >= dt.datetime.utcnow() - dt.timedelta(days=1)).scalar() >= 3:
        raise HTTPException(429, "You have asked a few times today. Your admin will see it.")
    s.add(MoreRequest(user_id=u.id, note=" ".join((b.note or "").split())[:300] or None)); s.commit()
    return {"ok": True, "message": "Sent. Your admin will see your request."}
class ProIn(BaseModel): days: int | None = None; until: str | None = None; end: bool = False
@app.put("/api/admin/users/{uid}/pro")
def make_pro(uid: int, b: ProIn, bg: BackgroundTasks, a: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if not u.self_registered: raise HTTPException(400, "Only self-registered people have a plan. Students your college added already use the college's AI.")
    if b.end: u.pro_until = None; s.commit(); return urow(u, None)
    if b.days is not None:
        if not 1 <= b.days <= 3660: raise HTTPException(400, "Choose between 1 day and 10 years")
        until = dt.datetime.utcnow() + dt.timedelta(days=b.days)
    else:
        try: d = dt.date.fromisoformat((b.until or "").strip())
        except ValueError: raise HTTPException(400, "Choose the last day of pro, or a number of days")
        if d < local_day(dt.datetime.utcnow()): raise HTTPException(400, "Choose a day from today on")
        until = dt.datetime.combine(d + dt.timedelta(days=1), dt.time()) - dt.timedelta(minutes=DAY_OFFSET)  # the end of that day, in the students' local time
    u.pro_until = until; close_requests(s, u.id); s.commit()
    if mail_on(s) and u.email: bg.add_task(deliver_pro, u.email, u.name, local_day(until - dt.timedelta(seconds=1)))
    return urow(u, None)
def deliver_pro(email, name, last_day):
    try: send_mail(email, f"More AI on {APP_NAME}", f"Hi {name},\n\nYour admin has given you more AI help on {APP_NAME}: no daily limit until {last_day.strftime('%d %B %Y')}.\n\nEnjoy your studies.\n", kind="pro")
    except MailError: pass
# ---- rewards for sharing: nothing to do by hand. When others are shown an answer a student's own search, doubt or highlight first brought,
# ---- each person counts once a day per answer; every SHARE_USES uses earn SHARE_POINTS points. Others never see who asked first.
SHARE_USES, SHARE_POINTS = 1000, 100
def author_of(u): return u.id if u.role == "student" else None  # staff answers are shared too, but only students earn points
def note_use(s, u, source, ref, author_id):  # it must never break the request that showed the answer
    if not author_id or author_id == u.id or not ref: return
    try:
        with s.begin_nested(): s.add(ShareUse(author_id=author_id, viewer_id=u.id, source=source, ref=ref, day=dt.date.today()))
        s.commit()
    except Exception: s.rollback()  # already counted today, most likely
def rewards(s, uid):
    uses = s.query(func.count(ShareUse.id)).filter(ShareUse.author_id == uid).scalar() or 0
    top = s.query(ShareUse.source, ShareUse.ref, func.count(ShareUse.id)).filter(ShareUse.author_id == uid).group_by(ShareUse.source, ShareUse.ref).order_by(func.count(ShareUse.id).desc()).limit(5).all()
    def label(src, ref):
        if src == "search": x = s.get(SearchAnswer, ref); return x.query if x else ""
        if src == "doubt": x = s.get(DoubtAnswer, ref); return x.phrase if x else ""
        x = s.get(AICache, ref); t = s.get(Topic, x.topic_id) if x else None; return t.title if t else ""
    return {"uses": uses, "points": uses // SHARE_USES * SHARE_POINTS, "toward_next": uses % SHARE_USES, "per": SHARE_USES, "points_per": SHARE_POINTS,
            "top": [{"source": src, "label": label(src, ref)[:120], "uses": n} for src, ref, n in top]}
@app.get("/api/me/profile")
def my_profile(u: User = Depends(me), s: Session = Depends(db)):
    pr = s.get(Program, u.program_id) if u.program_id else None
    return {"name": u.name, "email": u.email, "role": u.role, "lang": u.lang or "en", "program": pr.name if pr else "", "semester": u.semester, "term": term_label(pr) if pr else "",
            "self_registered": bool(u.self_registered), "ai": plan_json(u, s), **({"rewards": rewards(s, u.id)} if u.role == "student" else {})}
def own_key(u): return bool(u.self_registered and u.ai_key)  # paying with their own DeepSeek key: outside the college's allowance
def egress(s, u, kind, topic_id, chars, ok, tokens=0):  # the ledger of what leaves for the AI provider (sizes and kinds only, never the text); it must never break a request
    try: s.add(AIEgress(user_id=u.id, kind=kind[:20], topic_id=topic_id, chars=chars, ok=ok, tokens=tokens or 0, own=own_key(u) and kind != "vision")); s.commit()
    except Exception: s.rollback()
# ---- the college's monthly AI allowance: tokens per provider, set by an admin. When one is used up, new AI requests on the college's key stop until
# ---- the 1st; saved answers keep working, and people paying with their own key are not affected. Admins are warned at BUDGET_WARN of it.
BUDGET_WARN = 0.8
def month_start(): now = dt.datetime.utcnow(); return dt.datetime(now.year, now.month, 1)
def budget(s, provider):  # {"limit": tokens or 0 for none, "used": tokens this month on the college's key}
    q = s.query(func.coalesce(func.sum(AIEgress.tokens), 0)).filter(AIEgress.at >= month_start(), AIEgress.own == False)  # noqa: E712
    q = q.filter(AIEgress.kind == "vision") if provider == "claude" else q.filter(AIEgress.kind != "vision")
    try: limit = max(0, int(setting(s, "budget_" + provider) or 0))
    except ValueError: limit = 0
    return {"limit": limit, "used": int(q.scalar() or 0)}
def budget_or_fail(u, s, provider):
    b = budget(s, provider)
    if b["limit"] and b["used"] >= b["limit"]:
        raise HTTPException(503, "This month's AI allowance is used up. Saved answers still work, and new ones can be asked again from the 1st."
                            + (f" (Admin: the {'Claude' if provider == 'claude' else 'DeepSeek'} allowance is set under Settings.)" if u.role == "admin" else ""))
async def ask_ai(u, s, key, system, msg, max_tokens=None, timeout=60, kind="other", topic_id=None):
    size = len(system) + len(msg)
    if not own_key(u): budget_or_fail(u, s, "deepseek")
    if kind not in LITE_SEARCH_KINDS: lite_time_or_fail(u, s)  # searches were counted when asked
    try:
        out = await deepseek(key, setting(s, "model", "deepseek-chat"), [{"role": "system", "content": system}, {"role": "user", "content": msg}], max_tokens=max_tokens, timeout=timeout)
        egress(s, u, kind, topic_id, size, True, out[1]); return out
    except httpx.HTTPStatusError as e:
        egress(s, u, kind, topic_id, size, False)
        log.warning("DeepSeek answered %s", e.response.status_code)
        if own_key(u): raise HTTPException(503, f"DeepSeek refused your key ({e.response.status_code}). Check it, or your DeepSeek balance, under AI key in the menu.")
        raise ai_down(u, "DeepSeek refused the request (" + str(e.response.status_code) + "). Check the key, model name and balance under AI config.")
    except Exception as e:
        egress(s, u, kind, topic_id, size, False)
        log.warning("DeepSeek call failed: %s", type(e).__name__)
        if own_key(u): raise HTTPException(503, "DeepSeek did not answer. Try again in a moment.")
        raise ai_down(u, "DeepSeek did not answer.")
def topic_msg(f, kind, mine=None):  # what the AI is told about a topic
    body = words_of(f["content"], f["content_format"])  # the AI gets the words of an HTML topic, not its tags or scripts
    return (f"Program: {f['program']}\nSemester: {f['semester']}\nCourse: {f['course']}\nUnit: {f['unit']}\nTopic: {f['title']}\n\nTopic content:\n{body}\n\n"
            + (f"The student's own notes on this topic:\n{mine}\n\n" if mine else "")
            + (f"Question pattern:\n{f['question_pattern']}\n\nAnswer guideline:\n{f['guideline']}\n\nSample content:\n{f['sample_content']}\n" if kind in EXAM_KINDS else ""))
def topic_hash(t, kind, prompt): return hashlib.sha256("|".join([kind, t.title, t.content or "", t.sample_content or "", t.question_pattern or "", t.guideline or "", prompt]).encode()).hexdigest()
STEP_NEEDS = {"line": ("text",), "gist": ("points",), "why": ("text",), "example": ("text",), "simpler": ("text",), "exam": ("question", "answer"), "check": ("question", "answer"), "outline": ("points",)}
def step_reply(kind, text):  # a step's JSON, or None when the AI did not keep to it (not JSON, or a part the page shows is missing)
    try: d = ai_json(text)
    except HTTPException: return None
    if not isinstance(d, dict) or not all(d.get(k) for k in STEP_NEEDS.get(kind, ())): return None
    return d
# ---- adapting the steps to each student, from what they do with them (private: teachers never see it) ----
PICKS = ("why", "example", "exam", "check")  # the steps a student chooses, in their default order
CHECK_LEVEL = {"easy": "\n\nThis student has found these questions hard lately: ask about the single most important fact, plainly, and you may put a small hint in the question.",
               "hard": "\n\nThis student answers these easily: ask them to apply the idea to a new situation or to connect two ideas from the topic."}
QUESTION_FIRST_AFTER = 3  # topics opened in a unit before its other topics lead with the question and keep the gist one tap away
def learner(u, s):  # how the steps are arranged for this student
    rows = s.query(StepLog.kind, StepLog.outcome).filter(StepLog.user_id == u.id).order_by(StepLog.id.desc()).limit(200).all()
    taps = defaultdict(int)
    for k, o in rows:
        if not o and k in PICKS: taps[k] += 1
    res = [o for k, o in rows if o][:8]; knew = sum(o == "knew" for o in res)
    level = "normal" if len(res) < 3 else "easy" if knew / len(res) < 0.4 else "hard" if knew / len(res) >= 0.8 else "normal"
    order = sorted(PICKS, key=lambda k: (-taps[k], PICKS.index(k))) if sum(taps.values()) >= 3 else list(PICKS)
    return {"order": order, "level": level, "taps": dict(taps), "checks": len(res), "knew": knew}
def question_first(u, t, s):
    if u.role != "student" or not t.unit_id: return False
    return s.query(Progress.id).join(Topic, Topic.id == Progress.topic_id).filter(Progress.user_id == u.id, Topic.unit_id == t.unit_id, Topic.id != t.id).count() >= QUESTION_FIRST_AFTER
@app.get("/api/topics/{tid}/ai/{kind}")
async def ai(tid: int, kind: str, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t or kind not in PROMPTS or kind in ("search", "line", "doubt"): raise HTTPException(404, "Not found")
    check_topic_access(u, t, s)
    you = learner(u, s) if u.role == "student" else None
    f = full(t, s); prompt = in_lang(u, prompt_for(s, kind) + (CHECK_LEVEL.get(you["level"], "") if you and kind == "check" else ""))
    if you and kind in PICKS + ("simpler",): s.add(StepLog(user_id=u.id, topic_id=tid, kind=kind)); s.commit()  # a step the student chose to open
    extra = {"you": {**you, "question_first": question_first(u, t, s)}} if you and kind == "gist" else {"level": you["level"]} if you and kind == "check" else {}
    mine = my_notes(s, u.id, tid) if u.role == "student" and kind in ("explain", "answer") else None
    if mine:  # the student's own notes are private: the answer is written for them alone and never shared. It goes to the AI once; after that the kept copy is shown and nothing is sent.
        key_or_fail(u, s); ch = hashlib.sha256("|".join(["own", topic_hash(t, kind, prompt), mine]).encode()).hexdigest()
        hit = s.query(PrivateAnswer).filter_by(user_id=u.id, topic_id=tid, kind=kind, chash=ch).first()
        if hit: return {"text": hit.text, "cached": True, "own_notes": True}
        text = await study_ask(u, s, "t_" + kind, prompt, topic_msg(f, kind, mine), max_tokens=None, topic_id=tid)  # kinds fit the 10-character column
        try:
            s.query(PrivateAnswer).filter_by(user_id=u.id, topic_id=tid, kind=kind).delete()  # an answer for older notes is no use now
            s.add(PrivateAnswer(user_id=u.id, topic_id=tid, kind=kind, chash=ch, text=text)); s.commit()
        except Exception: s.rollback()
        return {"text": text, "cached": False, "own_notes": True}
    ch = topic_hash(t, kind, prompt)
    key = key_or_fail(u, s)
    hit = s.query(AICache).filter_by(topic_id=tid, kind=kind, chash=ch).first()
    if hit:
        hit.hits += 1; s.commit()
        return {"text": hit.text, "cached": True, "id": hit.id, **({"data": step_reply(kind, hit.text)} if kind in STEPS else {}), **extra}
    text, tokens = await ask_ai(u, s, key, prompt, topic_msg(f, kind), max_tokens=STEPS.get(kind, 700 if kind == "explain" else None), kind="topic_" + kind, topic_id=tid)
    data = step_reply(kind, text) if kind in STEPS else None
    if kind in STEPS and data is None: raise HTTPException(502, "The AI's answer could not be read. Try again.")  # not saved, so the next try asks again
    row = AICache(topic_id=tid, kind=kind, chash=ch, text=text, tokens=tokens)
    try: s.add(row); s.commit()
    except Exception: s.rollback(); row = None
    return {"text": text, "cached": False, "id": row.id if row else None, **({"data": data} if kind in STEPS else {}), **extra}
class CheckResult(BaseModel): outcome: str
@app.post("/api/topics/{tid}/check-result")
def check_result(tid: int, b: CheckResult, u: User = Depends(me), s: Session = Depends(db)):  # "I had it" or "Not quite" after a quick check: private, never a score
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    if b.outcome not in ("knew", "not_yet"): raise HTTPException(400, "Choose knew or not_yet")
    check_topic_access(u, t, s); s.add(StepLog(user_id=u.id, topic_id=tid, kind="check", outcome=b.outcome)); s.commit()
    return {"ok": True, "level": learner(u, s)["level"]}
@app.get("/api/me/learning")
def my_learning(u: User = Depends(me), s: Session = Depends(db)): return learner(u, s)  # what the app has picked up, shown to the student with a way to start fresh
@app.delete("/api/me/learning/steps")
def forget_learning(u: User = Depends(me), s: Session = Depends(db)):
    n = s.query(StepLog).filter_by(user_id=u.id).delete(); s.commit(); return {"ok": True, "cleared": n}
# ---- "this looks wrong": a student flags an AI reply; the topic's teachers see it (never who sent it) and write it again or let it stand ----
class FlagIn(BaseModel): source: str; id: int | None = None; topic_id: int | None = None; kind: str = ""; excerpt: str = ""; reason: str = ""
FLAG_DAILY = 20
@app.post("/api/ai/flag")
def flag_ai(b: FlagIn, u: User = Depends(me), s: Session = Depends(db)):
    if b.source not in ("topic", "search", "photo"): raise HTTPException(400, "Unknown source")
    if s.query(func.count(AIFlag.id)).filter(AIFlag.user_id == u.id, AIFlag.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= FLAG_DAILY:
        raise HTTPException(429, "Thanks, that's plenty of reports for today.")
    excerpt, kind, tid = (b.excerpt or "")[:600], (b.kind or "")[:10], None
    if b.source == "topic":
        t = s.get(Topic, b.topic_id or 0)
        if not t: raise HTTPException(404, "Topic not found")
        check_topic_access(u, t, s); tid = t.id
        row = s.get(AICache, b.id) if b.id else None
        if row and row.topic_id == t.id: excerpt, kind = readable(row.kind, row.text)[:600], row.kind
        elif b.id: raise HTTPException(404, "That answer is no longer saved")
    elif b.source == "photo": kind, b.id = "photo", None
    else:
        row = s.get(SearchAnswer, b.id) if b.id else None
        if row: excerpt, kind = row.text[:600], "search"
        kind = "search"
    if b.id and s.query(AIFlag).filter_by(user_id=u.id, source=b.source, ref=b.id, status="open").first(): return {"ok": True}  # already reported
    s.add(AIFlag(user_id=u.id, topic_id=tid, source=b.source, kind=kind, ref=b.id, excerpt=excerpt, reason=(b.reason or "").strip()[:300] or None)); s.commit()
    return {"ok": True}
def readable(kind, text):  # a saved step reply (JSON) as plain lines, for a teacher reading a flag
    d = step_reply(kind, text) if kind in STEPS else None
    if not d: return text
    parts = [*(f"- {x}" for x in d.get("points") or []), d.get("text"), d.get("question"), d.get("answer") and "Answer: " + d["answer"], d.get("hook") and "*" + d["hook"] + "*", d.get("tip") and "Examiners look for: " + d["tip"]]
    return "\n".join(str(x) for x in parts if x)
def flags_for(u, s):  # the open flags this person can act on: a faculty member's own courses, everything for admins
    q = s.query(AIFlag).filter(AIFlag.status == "open")
    if u.role == "faculty": q = q.join(Topic, Topic.id == AIFlag.topic_id).join(Course, Course.id == Topic.course_id).filter(Course.faculty_owner_id == u.id)
    return q
@app.get("/api/flags")
def list_flags(limit: int = 10, offset: int = 0, u: User = Depends(staff), s: Session = Depends(db)):
    """Open flags, one row per reply flagged (with how many students flagged it and what they said), newest first."""
    groups = {}
    for f in flags_for(u, s).order_by(AIFlag.id.desc()).all():
        g = groups.setdefault((f.source, f.ref or -f.id), {"id": f.id, "source": f.source, "kind": f.kind, "topic_id": f.topic_id, "excerpt": f.excerpt, "reasons": [], "count": 0, "at": f.at.isoformat() + "Z"})
        g["count"] += 1
        if f.reason and len(g["reasons"]) < 5: g["reasons"].append(f.reason)
    items = list(groups.values()); page = items[max(offset, 0):max(offset, 0) + min(max(limit, 1), 50)]
    names = {t.id: (t.title, c.name) for t, c in s.query(Topic, Course).join(Course, Course.id == Topic.course_id).filter(Topic.id.in_([g["topic_id"] for g in page if g["topic_id"]] or [0]))}
    for g in page: g["topic"], g["course"] = names.get(g["topic_id"], ("", ""))
    return {"total": len(items), "items": page}
class FlagDo(BaseModel): action: str
@app.post("/api/flags/{fid}/resolve")
def resolve_flag(fid: int, b: FlagDo, u: User = Depends(staff), s: Session = Depends(db)):
    """'rewrite' drops the saved reply so the next request writes it again; 'keep' lets it stand. Either closes every flag on that reply."""
    f = flags_for(u, s).filter(AIFlag.id == fid).first()
    if not f: raise HTTPException(404, "Flag not found")
    if b.action not in ("rewrite", "keep"): raise HTTPException(400, "Choose rewrite or keep")
    same = s.query(AIFlag).filter(AIFlag.source == f.source, AIFlag.ref == f.ref, AIFlag.status == "open") if f.ref else s.query(AIFlag).filter(AIFlag.id == f.id)
    if b.action == "rewrite" and f.ref:
        if f.source == "topic": s.query(AICache).filter(AICache.id == f.ref).delete(synchronize_session=False)
        else: s.query(SearchAnswer).filter(SearchAnswer.id == f.ref).delete(synchronize_session=False)
    n = same.update({"status": "fixed" if b.action == "rewrite" else "kept"}, synchronize_session=False); s.commit()
    return {"ok": True, "closed": n}
# ---- a unit's revision sheet: every topic's gist (saved ones only; the page asks for the rest one by one) and the student's own highlights ----
@app.get("/api/units/{uid}/revision")
def revision(uid: int, u: User = Depends(me), s: Session = Depends(db)):
    un = s.get(Unit, uid)
    if not un: raise HTTPException(404, "Unit not found")
    check_course_access(u, un.course_id, s); c = s.get(Course, un.course_id)
    live = {x for x, in live_topic_ids(s, [un.course_id])}; prompt = in_lang(u, prompt_for(s, "gist")); out = []
    hls = defaultdict(list)
    for h in s.query(Highlight).filter(Highlight.user_id == u.id, Highlight.topic_id.in_(live or {0})).order_by(Highlight.id): hls[h.topic_id].append(h.text[:220])
    for t in s.query(Topic).filter(Topic.unit_id == uid).order_by(*ORDER.get(Topic, (Topic.id,))):
        if t.id not in live: continue
        hit = s.query(AICache).filter_by(topic_id=t.id, kind="gist", chash=topic_hash(t, "gist", prompt)).first()
        out.append({"id": t.id, "title": t.title, "gist": step_reply("gist", hit.text) if hit else None, "highlights": hls.get(t.id, [])[:5]})
    return {"unit": un.name, "course": c.name if c else "", "topics": out}
# ---- a doubt: the student marks a phrase they do not follow. The app's own copy answers first; only if that is not enough does the phrase go to the AI, with the names of
# ---- the program, semester, course and topic and nothing else (never the notes). The AI's answer is kept, so the same doubt is never sent twice.
DOUBT_DAILY = int(os.getenv("AI_DOUBT_DAILY") or 30)  # doubts a student can send to the AI per day (kept answers don't count)
MAX_PHRASE = 300
class DoubtIn(BaseModel): phrase: str
def doubt_phrase(b):
    p = " ".join((b.phrase or "").split())
    if not 2 <= len(p) <= MAX_PHRASE: raise HTTPException(400, f"Select a short phrase (2 to {MAX_PHRASE} characters)")
    return p
def passage_around(text, phrase):  # the sentence or two around the phrase, taken from the app's own copy
    body, want = plain(text), plain(phrase).lower()
    i = body.lower().find(want) if want else -1
    if i < 0: return ""
    a = body.rfind(". ", 0, i); a = 0 if a < 0 else a + 2
    z = body.find(". ", i + len(want)); z = len(body) if z < 0 else z + 1
    return body[a:z][:600].strip()
def doubt_key(u, t, phrase, s):
    prompt = in_lang(u, prompt_for(s, "doubt"))
    return prompt, hashlib.sha256("|".join(["doubt", GUARD_VERSION, str(t.id), phrase.lower(), prompt]).encode()).hexdigest()
def doubt_topic(tid, u, s):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s); return t
@app.post("/api/topics/{tid}/doubt")
def doubt_local(tid: int, b: DoubtIn, u: User = Depends(me), s: Session = Depends(db)):
    """Step one, nothing leaves the server: where the phrase sits in the topic (and in the student's own notes), and a kept AI answer if this doubt was asked before."""
    t = doubt_topic(tid, u, s); phrase = doubt_phrase(b); f = full(t, s)
    mine = my_notes(s, u.id, tid) if u.role == "student" else None
    _, qh = doubt_key(u, t, phrase, s); hit = s.query(DoubtAnswer).filter_by(qhash=qh).first() if key_for(u, s) else None
    if hit: hit.hits += 1; s.commit(); note_use(s, u, "doubt", hit.id, hit.author_id)
    return {"phrase": phrase, "where": {"program": f["program"], "semester": f["semester"], "course": f["course"], "topic": f["title"]},
            "passage": passage_around(words_of(t.content, fmt_of(t)), phrase), "my_passage": passage_around(mine, phrase) if mine else "", "saved": hit.text if hit else None,
            "ai_left": max(0, DOUBT_DAILY - s.query(func.count(AIEgress.id)).filter(AIEgress.user_id == u.id, AIEgress.kind == "doubt", AIEgress.ok == True, AIEgress.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar()) if u.role == "student" else None}  # noqa: E712
@app.post("/api/topics/{tid}/doubt/ask")
async def doubt_ask(tid: int, b: DoubtIn, u: User = Depends(me), s: Session = Depends(db)):
    """Step two, only when the app's own copy did not clear it up: the AI gets the program, semester, course and topic names and the phrase. Not the topic's text, not the student's notes."""
    t = doubt_topic(tid, u, s); phrase = doubt_phrase(b)
    if crisis(phrase): return {"text": SUPPORT.get(u.lang or "en", SUPPORT["en"]), "cached": False, "support": True}
    key = key_or_fail(u, s); lite_search_or_fail(u, s); prompt, qh = doubt_key(u, t, phrase, s)
    hit = s.query(DoubtAnswer).filter_by(qhash=qh).first()
    if hit: hit.hits += 1; s.commit(); note_use(s, u, "doubt", hit.id, hit.author_id); return {"text": hit.text, "cached": True}
    if not is_staff(u) and s.query(func.count(AIEgress.id)).filter(AIEgress.user_id == u.id, AIEgress.kind == "doubt", AIEgress.ok == True, AIEgress.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= DOUBT_DAILY:  # noqa: E712
        raise HTTPException(429, f"You have used today's {DOUBT_DAILY} AI doubts. Try again tomorrow, or reread the passage above.")
    f = full(t, s)
    msg = f"Program: {f['program']}\nSemester: {f['semester']}\nCourse: {f['course']}\nTopic: {f['title']}\n\nThe student does not understand this phrase:\n{phrase}"
    text, tokens = await ask_ai(u, s, key, prompt, msg, max_tokens=500, kind="doubt", topic_id=tid)
    try: s.add(DoubtAnswer(qhash=qh, topic_id=tid, phrase=phrase[:300], text=text, tokens=tokens, author_id=author_of(u))); s.commit()
    except Exception: s.rollback()
    return {"text": text, "cached": False}
@app.get("/api/admin/egress")
def egress_report(days: int = 30, _: User = Depends(admin), s: Session = Depends(db)):
    """What has left for the AI provider, by kind: requests, characters sent and failures. Sizes only, never the text."""
    since = dt.datetime.utcnow() - dt.timedelta(days=min(max(days, 1), 400))
    rows = s.query(AIEgress.kind, func.count(AIEgress.id), func.coalesce(func.sum(AIEgress.chars), 0)).filter(AIEgress.at >= since).group_by(AIEgress.kind).all()
    failed = dict(s.query(AIEgress.kind, func.count(AIEgress.id)).filter(AIEgress.at >= since, AIEgress.ok == False).group_by(AIEgress.kind).all())  # noqa: E712
    return {"days": days, "by_kind": [{"kind": k, "requests": n, "chars": int(c), "failed": failed.get(k, 0)} for k, n, c in sorted(rows, key=lambda r: -r[1])], "total": sum(r[1] for r in rows)}
# ---- ask from a photo: the student snaps a question, a paragraph or a diagram in their book. The server reads the text (Tesseract, on this server);
# ---- the student checks it and asks. Only that text goes to DeepSeek; a photo goes out only when they ask about a diagram, and then only to Claude. Photos are never stored.
PHOTO_DAILY = int(os.getenv("AI_PHOTO_DAILY") or 20)  # photo questions a student can send to the AI per day
MAX_PHOTO = 6 * 1024 * 1024
def photo_jpeg(b64):  # the photo as a clean JPEG: decoded, checked to be an image, shrunk to at most 1568 px, metadata (like GPS) dropped
    from PIL import Image, ImageOps
    try:
        raw = base64.b64decode((b64 or "").split(",", 1)[-1], validate=False)
        if not raw or len(raw) > MAX_PHOTO: raise ValueError
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB"); im.thumbnail((1568, 1568))
        out = io.BytesIO(); im.save(out, "JPEG", quality=85); return out.getvalue(), im
    except Exception: raise HTTPException(400, "That photo could not be read. Take it again, or choose a JPEG or PNG under 6 MB.")
class PhotoIn(BaseModel): image: str
@app.post("/api/photo/read")
def photo_read(b: PhotoIn, u: User = Depends(me)):
    """Step one, all on this server: the text in the photo, for the student to check before asking."""
    _, im = photo_jpeg(b.image)
    if not ocr_ready(): return {"text": "", "ocr": False}
    import pytesseract
    try: text = pytesseract.image_to_string(im.convert("L"), lang=OCR_LANGS, timeout=60)
    except Exception: text = ""
    return {"text": re.sub(r"\n{3,}", "\n\n", text).strip()[:4000], "ocr": True}
class PhotoAsk(BaseModel): question: str; text: str = ""; image: str | None = None; diagram: bool = False
@app.post("/api/photo/ask")
async def photo_ask(b: PhotoAsk, u: User = Depends(me), s: Session = Depends(db)):
    q, text = " ".join((b.question or "").split())[:500], (b.text or "").strip()[:4000]
    if not q: raise HTTPException(400, "Type your question about the photo")
    if crisis(q) or crisis(text): return {"text": SUPPORT.get(u.lang or "en", SUPPORT["en"]), "support": True}
    see = b.diagram and b.image and vision_on(u, s)
    if not see and not text: raise HTTPException(400, "No text was read from the photo. Type what it says, or retake it closer and in good light.")
    if not is_staff(u) and s.query(func.count(AIEgress.id)).filter(AIEgress.user_id == u.id, AIEgress.kind.in_(("photo", "vision")), AIEgress.ok == True,  # noqa: E712
                                                                    AIEgress.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= PHOTO_DAILY:
        raise HTTPException(429, f"You have used today's {PHOTO_DAILY} photo questions. Try again tomorrow.")
    if not see: key_or_fail(u, s)  # before counting a lite search, so a missing key doesn't use one up
    lite_search_or_fail(u, s)
    who = ""
    if u.role == "student" and u.program_id:
        pr = s.get(Program, u.program_id); who = f"Student's program: {pr.name if pr else ''}" + (f", {term_label(pr)} {u.semester}" if u.semester else "") + "\n"
    msg = who + f"Text read from the photo:\n{text or '(none)'}\n\nThe student's question: {q}"
    prompt = in_lang(u, prompt_for(s, "photo"))
    if see:
        budget_or_fail(u, s, "claude"); jpeg, _ = photo_jpeg(b.image); size = len(prompt) + len(msg) + len(jpeg)
        try: out, _t = await vision(vision_key(s), setting(s, "vision_model", VISION_MODEL), prompt, jpeg, msg)
        except Exception as e:
            egress(s, u, "vision", None, size, False); log.warning("Claude call failed: %s", type(e).__name__)
            raise ai_down(u, "Claude did not answer. Check the Claude key and model under Settings." if isinstance(e, anthropic.APIStatusError) else "Claude did not answer.")
        egress(s, u, "vision", None, size, True, _t); return {"text": out, "via": "claude"}
    out, _t = await ask_ai(u, s, key_or_fail(u, s), prompt, msg, max_tokens=900, kind="photo")
    return {"text": out, "via": "deepseek"}
@app.get("/api/admin/budget")
def budget_status(_: User = Depends(admin), s: Session = Depends(db)):
    out = {p: budget(s, p) for p in ("deepseek", "claude")}
    for b in out.values(): b["share"] = round(b["used"] / b["limit"], 3) if b["limit"] else 0
    return {**out, "warn_at": BUDGET_WARN}
# ---- a topic's notes in the reader's language (Arabic or Tamil): translated once per topic and language, in parts, then kept and shared
TRANSLATABLE = ("markdown", "html")
def note_parts(text, fmt, size=3000):  # the notes cut at paragraph or block ends into parts of about `size` characters
    pieces = re.findall(r".*?</(?:p|h[1-6]|li|ul|ol|table|div|blockquote|pre|section)>|.+$", text, re.S | re.I) if fmt == "html" else re.split(r"(\n\s*\n)", text)
    parts, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > size: parts.append(cur); cur = ""
        cur += p
    return [x for x in parts + [cur] if x.strip()]
@app.get("/api/topics/{tid}/translation")
async def translation(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    if (u.lang or "en") not in ("ar", "ta"): raise HTTPException(400, "Choose Arabic or Tamil as your language to see notes translated")
    fmt = fmt_of(t)
    if fmt not in TRANSLATABLE or not (t.content or "").strip(): raise HTTPException(400, "This topic's notes can't be translated")
    prompt = in_lang(u, prompt_for(s, "translate")); ch = topic_hash(t, "translate", prompt); key = key_or_fail(u, s)
    hit = s.query(AICache).filter_by(topic_id=tid, kind="translate", chash=ch).first()
    if hit: hit.hits += 1; s.commit(); return {"content": hit.text, "format": fmt, "cached": True, "id": hit.id}
    gate = asyncio.Semaphore(3)
    async def one(part):
        async with gate:
            return (await ask_ai(u, s, key, prompt, f"Format: {'HTML' if fmt == 'html' else 'Markdown'}\n\n{part}", max_tokens=6000, timeout=120, kind="translate", topic_id=tid))
    done = await asyncio.gather(*[one(p) for p in note_parts(t.content, fmt)])
    text = ("" if fmt == "html" else "\n\n").join(x[0].strip() for x in done); tokens = sum(x[1] for x in done)
    if fmt == "html": text = clean_html(text)  # the translation is cleaned like any uploaded HTML: no scripts, no styles
    row = AICache(topic_id=tid, kind="translate", chash=ch, text=text, tokens=tokens)
    try: s.add(row); s.commit()
    except Exception: s.rollback(); row = None
    return {"content": text, "format": fmt, "cached": False, "id": row.id if row else None}
@app.get("/api/me/recall")
def recall(u: User = Depends(me), s: Session = Depends(db)):
    """'Remember this?': one curious question from a topic the student opened a few days ago, from its saved gist (never a new AI call). Changes daily."""
    now = dt.datetime.utcnow(); prompt = in_lang(u, prompt_for(s, "gist")); found = []
    rows = s.query(Topic, Progress.last_read).join(Progress, Progress.topic_id == Topic.id).filter(Progress.user_id == u.id, Progress.last_read <= now - dt.timedelta(days=2),
                                                                                                Progress.last_read >= now - dt.timedelta(days=60)).order_by(Progress.last_read).limit(40).all()
    for t, _ in rows:
        hit = s.query(AICache).filter_by(topic_id=t.id, kind="gist", chash=topic_hash(t, "gist", prompt)).first()
        d = step_reply("gist", hit.text) if hit else None
        if not d or not d.get("hook") or not d.get("hook_answer"): continue
        try: check_topic_access(u, t, s)
        except HTTPException: continue
        found.append({"topic_id": t.id, "title": t.title, "question": d["hook"], "answer": d["hook_answer"]})
    if not found: return {"item": None}
    last = {tid: (o, at) for tid, o, at in s.query(StepLog.topic_id, StepLog.outcome, StepLog.at).filter(StepLog.user_id == u.id, StepLog.outcome.isnot(None)).order_by(StepLog.id)}
    shaky = {tid for tid, (o, at) in last.items() if o == "not_yet" and at <= now - dt.timedelta(days=1)}  # their latest quick check here was "not quite", a day or more ago
    pool = [x for x in found if x["topic_id"] in shaky] or found  # a topic they said was "not quite" comes back first, until they have it
    return {"item": pool[(now.date().toordinal() + u.id) % len(pool)]}

# ---- search: the app's own topics first, then the AI ----
STOP = set("a an the of in on at to for and or is are was were be been what whats how why when which who does do did define explain meaning about between difference differences vs versus with from by as it its this that these those me my tell give short note notes write full form please can you i we".split())
SEARCH_DAILY = int(os.getenv("AI_SEARCH_DAILY") or 30)  # AI searches per student per day (answers already saved don't count)
def search_terms(q):
    out = []
    for w in re.findall(r"[a-z0-9][a-z0-9+./-]*", q.lower()):
        w = w.strip("-./+") or w
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"): w = w[:-1]  # ions -> ion, bases -> base
        if len(w) >= 2 and w not in STOP and w not in out: out.append(w)
    return out[:6]
def plain(t): return re.sub(r"\s+", " ", re.sub(r"[#*_`>|$\\\[\]()~]", " ", re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t or ""))).strip()
def snippet(text, terms, n=170):
    low = text.lower(); at = min([i for i in (low.find(t) for t in terms) if i >= 0] or [0]); a = max(0, at - 60)
    return ("…" if a else "") + text[a:a + n].strip() + ("…" if a + n < len(text) else "")
@app.get("/api/search")
def search(q: str = "", limit: int = 10, u: User = Depends(me), s: Session = Depends(db)):
    q = " ".join(q.split())[:200]; terms = search_terms(q)
    if len(q) < 2 or not terms: return {"q": q, "results": [], "confident": False}
    like = lambda col, t: func.lower(col).like(f"%{t}%")
    conds = [c for t in terms for c in (like(Topic.title, t), like(Topic.content, t), like(Unit.name, t), like(Course.name, t))]
    rows = s.query(Topic, Unit, Course).join(Unit, Unit.id == Topic.unit_id).join(Course, Course.id == Unit.course_id).filter(or_(*conds)).limit(500).all()
    ok = {}
    def allowed(c):
        if c.id not in ok:
            try: check_course_access(u, c.id, s); ok[c.id] = True
            except HTTPException: ok[c.id] = False
        return ok[c.id]
    need = max(1, (len(terms) + 1) // 2); scored = []
    for t, un, co in rows:
        if not allowed(co) or (t.published is False and not can_edit(u, co.id, s)) or (topic_off(s, t) and not can_edit(u, co.id, s)): continue  # archived topics and units are not searchable by students
        title, unit, course, body = (t.title or "").lower(), (un.name or "").lower(), (co.name or "").lower(), plain(words_of(t.content, fmt_of(t)))
        hit = [tm for tm in terms if tm in title or tm in unit or tm in course or tm in body.lower()]
        if len(hit) < need: continue
        score = sum(5 if tm in title else 2 if (tm in unit or tm in course) else 1 for tm in hit) + (5 if len(terms) > 1 and " ".join(terms) in title else 0)
        near = any(tm in title or tm in unit or tm in course for tm in hit)
        scored.append((score, near, len(hit) == len(terms), t, un, co, body))
    scored.sort(key=lambda x: (-x[0], x[3].title)); top = scored[:max(1, min(limit, 25))]
    sems = {x.id: x for x in s.query(Semester).filter(Semester.id.in_({x[5].semester_id for x in top if x[5].semester_id} or {0}))}
    progs = {x.id: x.name for x in s.query(Program).filter(Program.id.in_({x[5].program_id for x in top} or {0}))}
    return {"q": q, "terms": terms, "confident": any(near or (full_ and len(terms) > 1) for _, near, full_, *_ in scored),  # a lone word found only inside some notes is not a confident match
            "results": [{"id": t.id, "title": t.title, "unit": un.name, "course": co.name, "program": progs.get(co.program_id, ""), "semester": sems[co.semester_id].name if co.semester_id in sems else "",
                         "snippet": snippet(body, terms), "score": sc, "in_title": near} for sc, near, _, t, un, co, body in top]}
class SearchAIIn(BaseModel): q: str; refresh: bool = False
@app.post("/api/search/ai")
async def search_ai(b: SearchAIIn, u: User = Depends(me), s: Session = Depends(db)):
    q = " ".join(b.q.split())
    if not 2 <= len(q) <= 200: raise HTTPException(400, "Type what you want to look up (2 to 200 characters)")
    if crisis(q): return {"text": SUPPORT.get(u.lang or "en", SUPPORT["en"]), "cached": False, "support": True}  # answered with care at once: no AI, nothing saved or logged
    key = key_or_fail(u, s); lite_search_or_fail(u, s); prompt = in_lang(u, prompt_for(s, "search")); qh = hashlib.sha256("|".join(["search", GUARD_VERSION, q.lower(), prompt]).encode()).hexdigest()
    if not b.refresh:
        hit = s.query(SearchAnswer).filter_by(qhash=qh).first()
        if hit: hit.hits += 1; s.commit(); note_use(s, u, "search", hit.id, hit.author_id); return {"text": hit.text, "cached": True, "id": hit.id}
    if not is_staff(u) and s.query(func.count(SearchLog.id)).filter(SearchLog.user_id == u.id, SearchLog.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= SEARCH_DAILY:
        raise HTTPException(429, f"You have used today's {SEARCH_DAILY} AI searches. Try again tomorrow, or browse your courses.")
    who = ""
    if u.role == "student" and u.program_id:
        pr = s.get(Program, u.program_id); who = f"Student's program: {pr.name if pr else ''}" + (f", {term_label(pr)} {u.semester}" if u.semester else "") + "\n"
    msg = who + f"Search: {q}" + ("\n\nThe student was not satisfied with the first answer or the topics the app found. Give a fresh, clearer and more complete explanation from a different angle." if b.refresh else "")
    text, tokens = await ask_ai(u, s, key, prompt, msg, kind="search")
    s.add(SearchLog(user_id=u.id, refresh=b.refresh, query=q[:200], tokens=tokens))
    saved = None
    if not b.refresh:  # a recheck is the student asking for something different, so it is not saved for others
        try: saved = SearchAnswer(qhash=qh, query=q[:200], text=text, tokens=tokens, author_id=author_of(u)); s.add(saved); s.flush()
        except Exception: s.rollback(); saved = None; s.add(SearchLog(user_id=u.id, refresh=b.refresh, query=q[:200], tokens=tokens))
    s.commit(); return {"text": text, "cached": False, "id": saved.id if saved else None}
# ---- admin: edit the AI prompts ----
def saved_count(s, kind): return s.query(func.count(SearchAnswer.id)).scalar() if kind == "search" else s.query(func.count(DoubtAnswer.id)).scalar() if kind == "doubt" else s.query(func.count(AICache.id)).filter(AICache.kind == kind).scalar()
def clear_saved(s, kind): return (s.query(SearchAnswer).delete() if kind == "search" else s.query(DoubtAnswer).delete() if kind == "doubt" else s.query(AICache).filter(AICache.kind == kind).delete(synchronize_session=False))
@app.get("/api/admin/guardrails")
def get_guardrails(_: User = Depends(admin)): return {"text": GUARDRAILS, "version": GUARD_VERSION}  # read-only: the rules live in guardrails.py
@app.get("/api/admin/prompts")
def get_prompts(_: User = Depends(admin), s: Session = Depends(db)):
    return {"items": [{"kind": k, "label": PROMPT_INFO[k][0], "help": PROMPT_INFO[k][1], "text": prompt_for(s, k), "default": PROMPTS[k], "custom": bool(setting(s, "prompt_" + k).strip()), "saved_answers": saved_count(s, k)} for k in PROMPTS]}
class PromptIn(BaseModel): text: str
@app.put("/api/admin/prompts/{kind}")
def put_prompt(kind: str, b: PromptIn, _: User = Depends(admin), s: Session = Depends(db)):
    if kind not in PROMPTS: raise HTTPException(404, "No such prompt")
    t = b.text.strip()
    if len(t) < 20: raise HTTPException(400, "The prompt is too short to guide the AI. Write at least a sentence or two.")
    if len(t) > MAX_PROMPT: raise HTTPException(400, f"The prompt is too long (up to {MAX_PROMPT} characters).")
    if t == PROMPTS[kind]: s.query(Setting).filter_by(k="prompt_" + kind).delete()
    else: s.merge(Setting(k="prompt_" + kind, v=t))
    cleared = clear_saved(s, kind); s.commit(); return {"ok": True, "cleared": cleared}  # saved answers were written by the old prompt, so students get fresh ones
@app.delete("/api/admin/prompts/{kind}")
def reset_prompt(kind: str, _: User = Depends(admin), s: Session = Depends(db)):
    if kind not in PROMPTS: raise HTTPException(404, "No such prompt")
    s.query(Setting).filter_by(k="prompt_" + kind).delete(); cleared = clear_saved(s, kind); s.commit(); return {"ok": True, "cleared": cleared}

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
# ---- student-built courses: a student uploads their own material, the AI slices it into units and topics, they preview and adjust it, then study it ----
# The AI never rewrites the material: it only says where each topic starts and ends (paragraph numbers) and what it is called, so topics keep the student's own words.
from sqlalchemy.dialects import mysql as _mysql
BIG = Text().with_variant(_mysql.LONGTEXT(), "mysql")
class StudyCourse(Base):
    __tablename__ = "study_courses"
    id = Column(Integer, primary_key=True); owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title = Column(String(200)); subject = Column(String(150), default="")
    status = Column(String(10), default="draft")  # draft while it is being set up; ready once the student finishes the wizard
    share = Column(String(10), default="private")  # private, or program: classmates in the owner's program can study it too
    notes = Column(Text, default="")  # the student's instructions for slicing
    sources = Column(Text, default="[]")  # JSON [{name, kind, paras, words}] in the order they were added
    paras = Column(BIG, default="[]")  # JSON list of the material's paragraphs (Markdown), numbered from 1 in the plan
    plan = Column(BIG, nullable=True)  # JSON {"units": [{"title", "topics": [{"title", "summary", "from", "to"}]}]} shown in the preview
    sliced_by = Column(String(10), default="")  # ai or headings
    created_at = Column(DateTime, default=dt.datetime.utcnow); updated_at = Column(DateTime, default=dt.datetime.utcnow)
class StudyUnit(Base):
    __tablename__ = "study_units"
    id = Column(Integer, primary_key=True); course_id = Column(Integer, ForeignKey("study_courses.id", ondelete="CASCADE"), index=True)
    title = Column(String(200)); position = Column(Integer, default=0)
class StudyTopic(Base):
    __tablename__ = "study_topics"
    id = Column(Integer, primary_key=True); unit_id = Column(Integer, ForeignKey("study_units.id", ondelete="CASCADE"), index=True); course_id = Column(Integer, index=True)
    title = Column(String(200)); summary = Column(String(300), default=""); content = Column(BIG); position = Column(Integer, default=0)
    explain = Column(BIG, nullable=True); explain_hash = Column(String(64), nullable=True)  # the AI explanation, shared by everyone who studies the course
class StudyProgress(Base):
    __tablename__ = "study_progress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("study_topics.id", ondelete="CASCADE"), index=True)
    opened_at = Column(DateTime, default=dt.datetime.utcnow); completed_at = Column(DateTime, nullable=True)
    review_due = Column(DateTime, nullable=True); review_step = Column(Integer, default=0)  # spaced review: when this topic should come back, and how far apart reviews have grown
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_study_progress"),)
class StudyQuiz(Base):  # a set of questions the AI wrote for one person on one topic: mcq (practice, instant feedback) or quiz (scored at the end)
    __tablename__ = "study_quizzes"
    id = Column(Integer, primary_key=True); topic_id = Column(Integer, ForeignKey("study_topics.id", ondelete="CASCADE"), index=True, nullable=True)  # null for a review set
    course_id = Column(Integer, index=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True); kind = Column(String(10))  # mcq, quiz or review
    src_topic_id = Column(Integer, nullable=True, index=True)  # set instead of topic_id for a quick check or quiz on a topic of a staff-made course
    questions = Column(BIG)  # JSON [{text, options, correct, explanation, concept, topic_id}]
    created_at = Column(DateTime, default=dt.datetime.utcnow)
class StudyAttempt(Base):
    __tablename__ = "study_attempts"
    id = Column(Integer, primary_key=True); quiz_id = Column(Integer, ForeignKey("study_quizzes.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    answers = Column(Text); score = Column(Integer); total = Column(Integer); percent = Column(Integer); at = Column(DateTime, default=dt.datetime.utcnow)
class StudyAICall(Base):  # one row per AI call for a student-built course on the shared key; used for the daily limit
    __tablename__ = "study_ai_calls"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind = Column(String(10)); at = Column(DateTime, default=dt.datetime.utcnow, index=True)
class CourseMaterial(Base):  # one student's own material for an official course, cut into sections and filed under the course's syllabus topics
    __tablename__ = "course_materials"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    sources = Column(Text, default="[]"); paras = Column(BIG, default="[]")  # as in study_courses: the files in order, and their paragraphs
    sections = Column(BIG, nullable=True)  # JSON [{"from", "to", "topic_id" (null = not in the syllabus)}] covering the paragraphs in order
    matched_by = Column(String(10), default=""); saved_at = Column(DateTime, nullable=True); updated_at = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_course_material"),)
class TopicNote(Base):  # a student's own notes for one syllabus topic, taken from their material; private to them
    __tablename__ = "topic_notes"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True); content = Column(BIG); updated_at = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_note"),)

STUDY_AI_DAILY = int(os.getenv("STUDY_AI_DAILY") or 40)  # AI calls per person per day on the shared key (people with their own key are not limited)
MAX_SOURCE_BYTES, MAX_PARAS_CHARS = 20 * 1024 * 1024, 1_500_000
SLICE_BUDGET = 110_000  # characters of material sent to the AI in one slicing call; longer material is sent as the start of each paragraph
QUIZ_SIZE = {"mcq": 5, "quiz": 10}; QUIZ_PASS = 60
STUDY_PROMPTS = {
 "match": ("You file a student's own study material under their university syllabus. The syllabus is a list of topics like T12: title (unit). "
           "The material is a numbered list of paragraphs like [12] text. Cut the material into consecutive sections in the material's own order, "
           "each about one syllabus topic, and say which topic each section belongs to. Several sections may belong to the same topic, and a topic may get none. "
           "A section that fits no syllabus topic (a preface, an index, exercises on other subjects) gets topic null. "
           "Sections must cover the paragraphs in order without gaps or overlaps: give each the number of its first and last paragraph. "
           "Judge by meaning, not only by matching words; headings in the material may be worded differently from the syllabus. Reply with JSON only, exactly in this shape: "
           '{"sections":[{"from":1,"to":4,"topic":"T3"},{"from":5,"to":5,"topic":null}]}'),
 "slice": ("You turn a student's study material into a course. The material is a numbered list of paragraphs like [12] text. "
           "Group it into units, and split each unit into topics. Each topic must be the smallest logical component that can be learnt on its own: "
           "one concept, rule, definition group, worked example or story, usually 1 to 6 paragraphs. Keep the material's own order. "
           "Topics must cover the paragraphs in order without gaps or overlaps: give each topic the number of its first and last paragraph. "
           "Give every unit and topic a short, clear title in the material's language, and every topic a one-line summary. "
           "Follow the student's instructions when they give any. Reply with JSON only, exactly in this shape: "
           '{"units":[{"title":"...","topics":[{"title":"...","summary":"...","from":1,"to":3}]}]}'),
 "explain": ("You are a warm, clear tutor helping a student who is learning on their own from their own notes. Explain the topic so it clicks: "
             "start with the big idea in one or two sentences, then explain it step by step in simple words, give one example or comparison from everyday life, "
             "and end with 3 short recap bullets. Stay faithful to the material and do not add facts that contradict it. Write in the same language as the material. "
             "Use Markdown; show comparisons as a table with every row on its own line."),
 "questions": ("You write multiple-choice questions to check that a student has understood one topic of their own study material. "
               "Use only facts that are in the material; never invent facts. Each question has 4 options (2 for true/false), exactly one correct, "
               "plausible wrong options, a one or two sentence explanation of the right answer that quotes or points to the material, "
               "and a 'concept': the 2-5 word name of the idea it tests. Write in the material's language. Reply with JSON only, exactly in this shape: "
               '{"questions":[{"text":"...","options":["...","...","...","..."],"correct":0,"explanation":"...","concept":"..."}]}'),
}

def study_ai_left(u, s):  # AI requests left today for own-course help; None when not limited
    if is_staff(u) or (u.self_registered and u.ai_key): return None
    return max(0, STUDY_AI_DAILY - s.query(func.count(StudyAICall.id)).filter(StudyAICall.user_id == u.id, StudyAICall.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar())
def study_ai_status(u, s): return {"ai_available": bool(key_for(u, s)), "ai_left": study_ai_left(u, s), "ai_own_key": bool(u.self_registered)}
def study_ai_key(u, s):
    key = key_or_fail(u, s)
    if not (u.self_registered and u.ai_key) and not is_staff(u):
        if s.query(func.count(StudyAICall.id)).filter(StudyAICall.user_id == u.id, StudyAICall.at >= dt.datetime.utcnow() - dt.timedelta(hours=24)).scalar() >= STUDY_AI_DAILY:
            raise HTTPException(429, f"You have used today's {STUDY_AI_DAILY} AI requests for your own courses. Try again tomorrow.")
    return key
def ai_json(text):  # the first JSON object in an AI reply, even when it is wrapped in a code fence or prose
    t = re.sub(r"^\s*```(?:json)?|```\s*$", "", (text or "").strip(), flags=re.I | re.M).strip()
    try: return json.loads(t)
    except ValueError: pass
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        try: return json.loads(t[a:b + 1])
        except ValueError: pass
    raise HTTPException(502, "The AI's answer could not be read. Try again.")
async def study_ask(u, s, kind, system, msg, max_tokens=8000, topic_id=None):
    key = study_ai_key(u, s)
    call = StudyAICall(user_id=u.id, kind=kind)
    s.add(call); s.commit()
    call_id = call.id  # kept so the request can be given back if the AI call fails
    try:
        text, _ = await ask_ai(u, s, key, system, msg, max_tokens=max_tokens, timeout=120, kind=kind, topic_id=topic_id)
    except BaseException:
        # a failed or timed-out AI call must not use up one of the student's daily requests
        try:
            s.rollback()
            s.query(StudyAICall).filter(StudyAICall.id == call_id).delete(synchronize_session=False)
            s.commit()
        except Exception:
            s.rollback()
        raise
    return text

# -- reading uploaded material into paragraphs --
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def docx_paras(b):
    import zipfile, xml.etree.ElementTree as ET
    try: root = ET.fromstring(zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml"))
    except Exception: raise HTTPException(400, "That Word file could not be read. Save it as .docx and try again.")
    out = []
    def ptext(p): return "".join((t.text or "") if t.tag == W + "t" else "\t" if t.tag == W + "tab" else "\n" if t.tag in (W + "br", W + "cr") else "" for t in p.iter()).strip()
    body = root.find(W + "body")
    for el in (list(body) if body is not None else []):
        if el.tag == W + "p":
            tx = ptext(el)
            if not tx: continue
            st = el.find(f"{W}pPr/{W}pStyle"); style = (st.get(W + "val") if st is not None else "") or ""
            m = re.match(r"(?i)heading\s*([1-6])$", style) or re.match(r"(?i)^title$", style)
            if m: out.append("#" * (int(m.group(1)) if m.groups() else 1) + " " + tx.replace("\n", " "))
            elif el.find(f"{W}pPr/{W}numPr") is not None or re.match(r"(?i)list", style): out.append("- " + tx)
            else: out.append(tx)
        elif el.tag == W + "tbl":
            rows = [[ptext(c).replace("|", "\\|").replace("\n", " ") for c in r.findall(W + "tc")] for r in el.findall(W + "tr")]
            rows = [r for r in rows if any(r)]
            if rows:
                n = max(len(r) for r in rows); rows = [r + [""] * (n - len(r)) for r in rows]
                out.append("\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * n] + ["| " + " | ".join(r) + " |" for r in rows[1:]]))
    return merge_lists(out)
def merge_lists(paras):  # consecutive list items become one paragraph
    out = []
    for p in paras:
        if p.startswith("- ") and out and out[-1].startswith("- "): out[-1] += "\n" + p
        else: out.append(p)
    return out
def pdf_texts(b):  # the text of each page; scanned pages have none
    from pypdf import PdfReader
    try: return [pg.extract_text() or "" for pg in PdfReader(io.BytesIO(b)).pages]
    except Exception: raise HTTPException(400, "That PDF could not be read. If it is password-protected, remove the password and try again.")
def needs_ocr(pages):  # mostly scanned: no text at all, or at least 30% of the pages without text (a few blank or picture pages don't count)
    bare = sum(len(x.strip()) < 20 for x in pages)
    return len("".join(pages).strip()) < 40 or (bare and bare >= max(1, 0.3 * len(pages)))
def pdf_paras(b):
    pages = pdf_texts(b)
    if len("".join(pages).strip()) < 40: raise HTTPException(400, "This PDF has no text to read: it is probably scanned pages. Upload a PDF with selectable text, or a Word file.")
    return lines_paras("\n".join(pages))
def lines_paras(text):  # a PDF's (or text recognition's) lines -> paragraphs, with likely headings marked
    out, cur = [], ""
    for line in text.split("\n"):
        ln = line.strip()
        if not ln:
            if cur: out.append(cur); cur = ""
            continue
        heading = len(ln) < 70 and not re.search(r"[.,;:]$", ln) and (ln.isupper() or re.match(r"^(\d+(\.\d+)*\.?|chapter|unit|lesson|section)\s", ln, re.I))
        if heading:
            if cur: out.append(cur)
            out.append("## " + ln); cur = ""
        elif cur and (re.search(r"[.!?:]$", cur) and (ln[:1].isupper() or ln[:1].isdigit() or ln[:1] in "-•*")): out.append(cur); cur = ln
        else: cur = (cur + " " + ln).strip() if cur else ln
    if cur: out.append(cur)
    return [re.sub(r"^[•*]\s*", "- ", p) for p in out]
def text_paras(t): return [p.strip() for p in re.split(r"\n\s*\n", (t or "").replace("\r\n", "\n").lstrip("\ufeff")) if p.strip()]
# -- scanned PDFs: text recognition (Tesseract) in the background --
OCR_LANGS = (os.getenv("OCR_LANGS") or "eng").strip()  # Tesseract languages, e.g. eng+tam+hin (their packs must be installed)
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES") or 300)
OCR_GATE = threading.BoundedSemaphore(max(1, int(os.getenv("OCR_WORKERS") or 1)))  # pages are read one file at a time by default: it is heavy on the CPU
OCR_JOBS = set()  # ids of files being read (or waiting) in this process; one that is "reading" but not here was cut off by a restart
@functools.lru_cache(maxsize=1)
def ocr_ready():  # Tesseract with the languages asked for, and the page renderer, are installed
    try:
        import pypdfium2, pytesseract  # noqa: F401
        have = set(pytesseract.get_languages(config=""))
        return all(x in have for x in OCR_LANGS.split("+"))
    except Exception: return False
def ocr_page(page): import pytesseract; return pytesseract.image_to_string(page.render(scale=300 / 72).to_pil().convert("L"), lang=OCR_LANGS, timeout=180)
def spawn(fn, *args): threading.Thread(target=fn, args=args, daemon=True).start()
def read_material(name, b):  # (kind, paragraphs, None), or for a scanned PDF ("scan", None, page texts) to be read in the background
    if b[:4] == b"%PDF" or name.lower().endswith(".pdf"):
        pages = pdf_texts(b)
        if needs_ocr(pages) and not pdf_has_images(b): raise HTTPException(400, "This PDF has no text to read and no scanned pages either. Upload a PDF with selectable text, or a Word file.")
        if needs_ocr(pages):
            if not ocr_ready(): raise HTTPException(400, "This PDF is scanned pages, and text recognition isn't set up on this server yet. Ask your admin, or upload a PDF with selectable text or a Word file.")
            if not pages: raise HTTPException(400, "This PDF has no pages")
            return "scan", None, pages
        return "pdf", lines_paras("\n".join(pages)), None
    kind, paras = material_paras(name, b); return kind, paras, None
def pdf_has_images(b):  # scanned pages are pictures; a PDF with no text and no pictures has nothing to read
    from pypdf import PdfReader
    try: return any(len(pg.images) for pg in PdfReader(io.BytesIO(b)).pages)
    except Exception: return True  # unusual image encodings: let text recognition try
def add_scan(row, name, pages):  # the file is listed at once, without text, while its pages are read
    sources = json.loads(row.sources or "[]"); sid = secrets.token_hex(8)
    sources.append({"name": name[:200], "kind": "scan", "paras": 0, "words": 0, "status": "reading", "pages": len(pages), "done": 0, "sid": sid})
    row.sources = json.dumps(sources, ensure_ascii=False); clear_split(row); OCR_JOBS.add(sid)
    return sources[-1]
def clear_split(row):  # new material means the outline (student courses) or the filing (course material) is made again
    if isinstance(row, StudyCourse): row.plan = None; touch(row)
    else: row.sections = None; row.updated_at = dt.datetime.utcnow()
def on_source(model, rid, sid, fn):  # change one listed file under a row lock; False when the row or the file is gone
    with Session_() as s:
        row = s.query(model).filter_by(id=rid).with_for_update().first()
        srcs = json.loads(row.sources or "[]") if row else []
        k = next((i for i, x in enumerate(srcs) if x.get("sid") == sid), None)
        if k is None: return False
        fn(row, srcs, k); row.sources = json.dumps(srcs, ensure_ascii=False); s.commit(); return True
def run_ocr(model, rid, sid, data, pages):
    try:
        with OCR_GATE:
            import pypdfium2
            doc, n, got = pypdfium2.PdfDocument(data), min(len(pages), OCR_MAX_PAGES), []
            for i in range(n):  # pages that have real text keep it; only the others are read from the image
                got.append(pages[i] if len(pages[i].strip()) >= 20 else ocr_page(doc[i]))
                if not on_source(model, rid, sid, lambda row, srcs, k: srcs[k].update(done=i + 1)): return  # removed while reading: stop
        paras = [p for p in lines_paras("\n".join(got)) if p.strip()]
        def finish(row, srcs, k):
            have = json.loads(row.paras or "[]")
            if not paras: srcs[k].update(status="failed", error="No text could be read from these pages."); return
            if sum(len(x) for x in have) + sum(len(x) for x in paras) > MAX_PARAS_CHARS: srcs[k].update(status="failed", error="That is more material than one course can hold."); return
            at = sum(x.get("paras", 0) for x in srcs[:k])  # its text goes where the file sits in the list
            row.paras = json.dumps(have[:at] + paras + have[at:], ensure_ascii=False)
            srcs[k].update(status="done", paras=len(paras), words=sum(len(x.split()) for x in paras), **({"note": f"Only the first {n} of {len(pages)} pages were read."} if n < len(pages) else {}))
            clear_split(row)
        on_source(model, rid, sid, finish)
    except Exception as e:
        log.warning("text recognition failed: %s", type(e).__name__)
        on_source(model, rid, sid, lambda row, srcs, k: srcs[k].update(status="failed", error="The pages could not be read. Try a clearer scan."))
    finally: OCR_JOBS.discard(sid)
def scan_state(row, s):  # mark files cut off by a restart; True while any file is still being read
    srcs = json.loads(row.sources or "[]") if row else []; busy, changed = False, False
    for x in srcs:
        if x.get("status") == "reading":
            if x.get("sid") in OCR_JOBS: busy = True
            else: x.update(status="failed", error="Reading stopped when the server restarted. Remove this file and add it again."); changed = True
    if changed: row.sources = json.dumps(srcs, ensure_ascii=False); s.commit()
    return busy
def not_while_reading(row, s):
    if scan_state(row, s): raise HTTPException(409, "Wait until your scanned pages have been read")
def material_paras(name, b):
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if b[:4] == b"%PDF" or ext == "pdf": return "pdf", pdf_paras(b)
    if b[:2] == b"PK" or ext == "docx":
        if ext == "doc": raise HTTPException(400, "Old .doc files can't be read. Save it as .docx and try again.")
        return "docx", docx_paras(b)
    if ext in ("txt", "md", "markdown", "text", ""):
        try: return ext or "txt", text_paras(b.decode("utf-8"))
        except UnicodeDecodeError: return ext or "txt", text_paras(b.decode("latin-1"))
    raise HTTPException(400, "Upload a PDF, a Word (.docx) file, or a .txt or .md file")

# -- slicing --
def slice_view(paras, budget=SLICE_BUDGET):
    total = sum(len(p) for p in paras)
    cap = None if total <= budget else max(80, budget // max(1, len(paras)))
    return "\n".join(f"[{i}] " + (p if cap is None or len(p) <= cap else p[:cap] + " …") for i, p in enumerate(paras, 1))
def normalise_plan(raw, n):
    """Any plan -> units of topics that cover paragraphs 1..n in order with no gaps or overlaps (a topic runs until the next one starts)."""
    flat = []
    for ui, un in enumerate((raw or {}).get("units") or []):
        for t in (un.get("topics") or []) if isinstance(un, dict) else []:
            try: f = int(t.get("from"))
            except (TypeError, ValueError, AttributeError): continue
            if 1 <= f <= n: flat.append((f, ui, str(un.get("title") or f"Part {ui + 1}").strip()[:200], str(t.get("title") or "").strip()[:200], str(t.get("summary") or "").strip()[:300]))
    flat.sort(key=lambda x: (x[0], x[1]))
    seen, uniq = set(), []
    for x in flat:
        if x[0] not in seen: seen.add(x[0]); uniq.append(x)
    if not uniq: return None
    if uniq[0][0] != 1: uniq[0] = (1,) + uniq[0][1:]
    units = []
    for k, (f, ui, ut, tt, sm) in enumerate(uniq):
        to = uniq[k + 1][0] - 1 if k + 1 < len(uniq) else n
        if not units or units[-1]["_ui"] != ui: units.append({"_ui": ui, "title": ut, "topics": []})
        units[-1]["topics"].append({"title": tt or f"Topic {k + 1}", "summary": sm, "from": f, "to": to})
    for u_ in units: u_.pop("_ui")
    return {"units": units[:60]}
def headings_plan(paras):  # without AI: every heading starts a topic, top-level headings start units; with no headings, about 350 words per topic
    lvl = [len(m.group(1)) if (m := re.match(r"^(#{1,6})\s", p)) else 0 for p in paras]
    if not any(lvl):
        units, cur, words = [{"title": "Part 1", "topics": []}], None, 0
        for i, p in enumerate(paras, 1):
            if cur is None or words >= 350: cur = {"title": p[:60].split("\n")[0] + ("…" if len(p) > 60 else ""), "summary": "", "from": i, "to": i}; units[0]["topics"].append(cur); words = 0
            cur["to"] = i; words += len(p.split())
        return {"units": units}
    used = sorted({l for l in lvl if l}); top = next((l for l in used if lvl.count(l) > 1), used[0])  # a lone document title is not a unit level
    raw, ui, unit_title = {"units": []}, -1, "Introduction"
    for i, (p, l) in enumerate(zip(paras, lvl), 1):
        if (l and l <= top) or ui < 0:
            unit_title = p.lstrip("#").strip()[:200] if l else unit_title; raw["units"].append({"title": unit_title, "topics": []}); ui += 1
        if l or i == 1: raw["units"][ui]["topics"].append({"title": p.lstrip("#").strip()[:200] if l else "Introduction", "from": i})
    return normalise_plan(raw, len(paras))
def plain_excerpt(ps): return re.sub(r"\s+", " ", re.sub(r"^#{1,6}\s+|\|?\s*:?-{3,}:?\s*\|?|[|*_`>]", " ", "\n".join(ps), flags=re.M)).strip()[:280]
def plan_view(c):  # the preview: each topic with its size and the start of its text
    paras = json.loads(c.paras or "[]"); plan = json.loads(c.plan) if c.plan else None
    if not plan: return None
    out = {"units": []}
    for un in plan["units"]:
        out["units"].append({"title": un["title"], "topics": [{**t, "words": sum(len(p.split()) for p in paras[t["from"] - 1:t["to"]]),
                                                               "excerpt": plain_excerpt(paras[t["from"] - 1:t["to"]])} for t in un["topics"]]})
    return out

# -- access --
def study_course_or_404(cid, u, s, edit=False):  # the owner (and admins) edit; classmates in the owner's program see a shared, finished course
    c = s.get(StudyCourse, cid)
    if not c: raise HTTPException(404, "Course not found")
    if c.owner_id == u.id or u.role == "admin": return c
    owner = s.get(User, c.owner_id)
    sees = c.status == "ready" and c.share == "program" and bool(u.program_id) and owner is not None and owner.program_id == u.program_id
    if sees and not edit: return c
    if sees: raise HTTPException(403, "Only the student who built this course can change it")
    raise HTTPException(404, "Course not found")
def study_topic_or_404(tid, u, s):
    t = s.get(StudyTopic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    study_course_or_404(t.course_id, u, s); return t
def touch(c): c.updated_at = dt.datetime.utcnow()

class StudyCourseIn(BaseModel): title: str = ""; subject: str = ""; share: str | None = None; notes: str | None = None
@app.post("/api/study/courses")
def study_new(b: StudyCourseIn, u: User = Depends(me), s: Session = Depends(db)):
    title = b.title.strip()
    if not title or len(title) > 200: raise HTTPException(400, "Give your course a name (up to 200 characters)")
    if s.query(StudyCourse).filter_by(owner_id=u.id).count() >= 50: raise HTTPException(400, "You can have up to 50 courses of your own. Delete one you no longer need.")
    c = StudyCourse(owner_id=u.id, title=title, subject=b.subject.strip()[:150]); s.add(c); s.commit(); return {"id": c.id}
def study_row(c, s, u, owners=None):
    owner = (owners or {}).get(c.owner_id) or s.get(User, c.owner_id)
    topics = s.query(func.count(StudyTopic.id)).filter_by(course_id=c.id).scalar() if c.status == "ready" else 0
    done = s.query(func.count(StudyProgress.id)).join(StudyTopic, StudyTopic.id == StudyProgress.topic_id).filter(StudyTopic.course_id == c.id, StudyProgress.user_id == u.id, StudyProgress.completed_at.isnot(None)).scalar() if topics else 0
    return {"id": c.id, "title": c.title, "subject": c.subject or "", "status": c.status, "share": c.share, "mine": c.owner_id == u.id, "owner": owner.name if owner else "",
            "topics": topics, "completed": done, "updated_at": iso(c.updated_at)}
@app.get("/api/study/courses")
def study_list(u: User = Depends(me), s: Session = Depends(db)):
    mine = s.query(StudyCourse).filter_by(owner_id=u.id).order_by(StudyCourse.updated_at.desc()).all()
    shared = []
    if u.program_id:
        mates = [i for (i,) in s.query(User.id).filter(User.program_id == u.program_id, User.id != u.id)]
        shared = s.query(StudyCourse).filter(StudyCourse.owner_id.in_(mates or [0]), StudyCourse.share == "program", StudyCourse.status == "ready").order_by(StudyCourse.updated_at.desc()).limit(100).all()
    owners = {x.id: x for x in s.query(User).filter(User.id.in_({c.owner_id for c in shared} or {0}))}
    return {"mine": [study_row(c, s, u) for c in mine], "shared": [study_row(c, s, u, owners) for c in shared], "ai_daily": STUDY_AI_DAILY}
@app.get("/api/study/courses/{cid}")
def study_get(cid: int, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s); mine = c.owner_id == u.id or u.role == "admin"
    out = {**study_row(c, s, u), "can_edit": mine, "notes": (c.notes or "") if mine else "", "sliced_by": c.sliced_by or "", **study_ai_status(u, s)}
    if mine: out.update(reading=scan_state(c, s), ocr_available=ocr_ready(), sources=json.loads(c.sources or "[]"), paragraphs=len(json.loads(c.paras or "[]")), plan=plan_view(c))
    if c.status == "ready":
        prog = {p.topic_id: p for p in s.query(StudyProgress).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_(s.query(StudyTopic.id).filter_by(course_id=c.id)))}
        best = study_best(s, u.id, c.id); now = dt.datetime.utcnow()
        units = s.query(StudyUnit).filter_by(course_id=c.id).order_by(StudyUnit.position, StudyUnit.id).all(); by = defaultdict(list)
        for t in s.query(StudyTopic).filter_by(course_id=c.id).order_by(StudyTopic.position, StudyTopic.id): by[t.unit_id].append(t)
        stars = study_stars(s, u.id, [t.id for L in by.values() for t in L])
        out["units"] = [{"id": un.id, "title": un.title, "topics": [{"id": t.id, "title": t.title, "summary": t.summary or "", "status": "completed" if prog.get(t.id) and prog[t.id].completed_at else "in_progress" if t.id in prog else "not_started",
                                                                   "best": best.get(t.id), "stars": stars.get(t.id, 0), "due": bool(prog.get(t.id) and prog[t.id].review_due and prog[t.id].review_due <= now)} for t in by[un.id]]} for un in units]
        out["mastery"] = round(100 * sum(stars.values()) / (3 * len(stars))) if stars else 0; out["reviews_due"] = sum(t["due"] for un in out["units"] for t in un["topics"])
    return out
@app.put("/api/study/courses/{cid}")
def study_edit(cid: int, b: StudyCourseIn, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    if b.title.strip():
        if len(b.title.strip()) > 200: raise HTTPException(400, "The name is too long")
        c.title = b.title.strip()
    if b.subject is not None: c.subject = b.subject.strip()[:150]
    if b.share is not None:
        if b.share not in ("private", "program"): raise HTTPException(400, "Share must be private or program")
        if b.share == "program" and not s.get(User, c.owner_id).program_id: raise HTTPException(400, "You are not in a program yet, so there are no classmates to share with")
        c.share = b.share
    if b.notes is not None: c.notes = b.notes.strip()[:4000]
    touch(c); s.commit(); return {"ok": True}
@app.delete("/api/study/courses/{cid}")
def study_delete(cid: int, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True); drop_study_content(s, c.id); s.delete(c); s.commit(); return {"ok": True}
def drop_study_content(s, cid):  # units, topics and everything hanging off them (SQLite does not cascade)
    tids = [i for (i,) in s.query(StudyTopic.id).filter_by(course_id=cid)] or [0]
    qids = [i for (i,) in s.query(StudyQuiz.id).filter(or_(StudyQuiz.topic_id.in_(tids), StudyQuiz.course_id == cid))] or [0]
    s.query(StudyAttempt).filter(StudyAttempt.quiz_id.in_(qids)).delete(synchronize_session=False)
    s.query(StudyQuiz).filter(StudyQuiz.id.in_(qids)).delete(synchronize_session=False); s.query(StudyProgress).filter(StudyProgress.topic_id.in_(tids)).delete(synchronize_session=False)
    s.query(StudyTopic).filter_by(course_id=cid).delete(); s.query(StudyUnit).filter_by(course_id=cid).delete()

# -- wizard step 2: material --
def add_material(c, name, kind, new):
    paras, sources = json.loads(c.paras or "[]"), json.loads(c.sources or "[]")
    new = [p for p in new if p.strip()]
    if not new: raise HTTPException(400, f"No text was found in {name}")
    if sum(len(p) for p in paras) + sum(len(p) for p in new) > MAX_PARAS_CHARS: raise HTTPException(413, "That is more material than one course can hold. Split it into two courses.")
    sources.append({"name": name[:200], "kind": kind, "paras": len(new), "words": sum(len(p.split()) for p in new)})
    c.paras, c.sources, c.plan = json.dumps(paras + new, ensure_ascii=False), json.dumps(sources, ensure_ascii=False), None  # new material means a new slice
    touch(c)
    return sources[-1]
@app.post("/api/study/courses/{cid}/files")
async def study_file(cid: int, request: Request, name: str = "", u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    if c.status == "ready": raise HTTPException(400, "Start a new setup of this course to add material")
    if int(request.headers.get("content-length") or 0) > MAX_SOURCE_BYTES: raise HTTPException(413, "The file is too large. Keep it under 20 MB.")
    b = await request.body()
    if len(b) > MAX_SOURCE_BYTES: raise HTTPException(413, "The file is too large. Keep it under 20 MB.")
    kind, paras, pages = await run_in_threadpool(read_material, name or "file", b)
    if kind == "scan": src = add_scan(c, name or "file", pages); s.commit(); spawn(run_ocr, StudyCourse, c.id, src["sid"], b, pages); return src
    src = add_material(c, name or "file", kind, paras); s.commit(); return src
class StudyTextIn(BaseModel): text: str; name: str = ""
@app.post("/api/study/courses/{cid}/text")
def study_text(cid: int, b: StudyTextIn, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    if c.status == "ready": raise HTTPException(400, "Start a new setup of this course to add material")
    src = add_material(c, b.name.strip() or "Pasted text", "text", text_paras(b.text)); s.commit(); return src
@app.delete("/api/study/courses/{cid}/sources/{i}")
def study_drop_source(cid: int, i: int, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    if c.status == "ready": raise HTTPException(400, "Start a new setup of this course to change its material")
    paras, sources = json.loads(c.paras or "[]"), json.loads(c.sources or "[]")
    if not 0 <= i < len(sources): raise HTTPException(404, "No such file")
    start = sum(x["paras"] for x in sources[:i])
    del paras[start:start + sources[i]["paras"]]; del sources[i]
    c.paras, c.sources, c.plan = json.dumps(paras, ensure_ascii=False), json.dumps(sources, ensure_ascii=False), None; touch(c); s.commit(); return {"ok": True}

# -- wizard steps 3-5: slice, preview, adjust, finish --
class SliceIn(BaseModel): notes: str = ""; method: str = "ai"
@app.post("/api/study/courses/{cid}/slice")
async def study_slice(cid: int, b: SliceIn, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    not_while_reading(c, s); paras = json.loads(c.paras or "[]")
    if not paras: raise HTTPException(400, "Add your material first")
    c.notes = b.notes.strip()[:4000]
    if b.method == "headings": plan, by = headings_plan(paras), "headings"
    elif b.method == "ai":
        msg = (f"Course: {c.title}" + (f" ({c.subject})" if c.subject else "") + (f"\n\nThe student's instructions:\n{c.notes}" if c.notes else "") +
               f"\n\nThe material has {len(paras)} paragraphs:\n\n" + slice_view(paras))
        plan, by = normalise_plan(ai_json(await study_ask(u, s, "slice", STUDY_PROMPTS["slice"], msg)), len(paras)), "ai"
        if not plan: raise HTTPException(502, "The AI did not return a usable outline. Try again, or slice by headings.")
    else: raise HTTPException(400, "method must be ai or headings")
    c.plan, c.sliced_by = json.dumps(plan, ensure_ascii=False), by; touch(c); s.commit()
    return {"plan": plan_view(c), "sliced_by": by}
class PlanIn(BaseModel): units: list[dict]
@app.put("/api/study/courses/{cid}/plan")
def study_plan(cid: int, b: PlanIn, u: User = Depends(me), s: Session = Depends(db)):
    """The preview after the student renamed, merged or removed topics. Topics stay in order and never overlap; removed topics leave their paragraphs out."""
    c = study_course_or_404(cid, u, s, edit=True); n = len(json.loads(c.paras or "[]")); last, units = 0, []
    for un in b.units:
        topics = []
        for t in un.get("topics") or []:
            try: f, to = int(t["from"]), int(t["to"])
            except (KeyError, TypeError, ValueError): raise HTTPException(400, "Each topic needs its first and last paragraph")
            if not (last < f <= to <= n): raise HTTPException(400, "Topics must stay in order without overlapping")
            last = to; topics.append({"title": (str(t.get("title") or "").strip() or "Untitled topic")[:200], "summary": str(t.get("summary") or "")[:300], "from": f, "to": to})
        if topics: units.append({"title": (str(un.get("title") or "").strip() or "Untitled unit")[:200], "topics": topics})
    if not units: raise HTTPException(400, "Keep at least one topic")
    c.plan = json.dumps({"units": units}, ensure_ascii=False); touch(c); s.commit(); return {"plan": plan_view(c)}
@app.get("/api/study/courses/{cid}/preview")
def study_preview(cid: int, start: int, end: int, u: User = Depends(me), s: Session = Depends(db)):  # the full text of a planned topic
    c = study_course_or_404(cid, u, s, edit=True); paras = json.loads(c.paras or "[]")
    if not 1 <= start <= end <= len(paras): raise HTTPException(400, "Out of range")
    return {"content": "\n\n".join(paras[start - 1:end])}
class FinishIn(BaseModel): replace: bool = False
@app.post("/api/study/courses/{cid}/finish")
def study_finish(cid: int, b: FinishIn, u: User = Depends(me), s: Session = Depends(db)):
    c = study_course_or_404(cid, u, s, edit=True)
    if not c.plan: raise HTTPException(400, "Slice your material and check the preview first")
    if s.query(StudyTopic.id).filter_by(course_id=c.id).first():
        if not b.replace: raise HTTPException(409, "This course already has topics. Finishing again replaces them, with their progress and quizzes.")
        drop_study_content(s, c.id)
    paras = json.loads(c.paras or "[]"); n = 0
    for ui, un in enumerate(json.loads(c.plan)["units"]):
        su = StudyUnit(course_id=c.id, title=un["title"], position=ui); s.add(su); s.flush()
        for ti, t in enumerate(un["topics"]):
            s.add(StudyTopic(unit_id=su.id, course_id=c.id, title=t["title"], summary=t.get("summary", ""), position=ti, content="\n\n".join(paras[t["from"] - 1:t["to"]]))); n += 1
    c.status = "ready"; touch(c); s.commit(); return {"ok": True, "topics": n}
@app.post("/api/study/courses/{cid}/reopen")
def study_reopen(cid: int, u: User = Depends(me), s: Session = Depends(db)):  # back to the wizard; the topics stay until the student finishes again
    c = study_course_or_404(cid, u, s, edit=True); c.status = "draft"; touch(c); s.commit(); return {"ok": True}

# -- studying: topics, progress, explanations, MCQs and quizzes --
def study_best(s, uid, cid):  # best quiz score per topic (quizzes only; practice MCQs don't count toward it)
    rows = s.query(StudyQuiz.topic_id, func.max(StudyAttempt.percent)).join(StudyAttempt, StudyAttempt.quiz_id == StudyQuiz.id).join(StudyTopic, StudyTopic.id == StudyQuiz.topic_id)\
            .filter(StudyTopic.course_id == cid, StudyAttempt.user_id == uid, StudyQuiz.kind == "quiz").group_by(StudyQuiz.topic_id)
    return {tid: p for tid, p in rows}
@app.get("/api/study/topics/{tid}")
def study_topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = study_topic_or_404(tid, u, s); c = s.get(StudyCourse, t.course_id); un = s.get(StudyUnit, t.unit_id)
    p = s.query(StudyProgress).filter_by(user_id=u.id, topic_id=tid).first()
    if not p: s.add(StudyProgress(user_id=u.id, topic_id=tid)); s.commit()
    order = [x.id for x in s.query(StudyTopic).join(StudyUnit, StudyUnit.id == StudyTopic.unit_id).filter(StudyTopic.course_id == c.id).order_by(StudyUnit.position, StudyUnit.id, StudyTopic.position, StudyTopic.id)]
    i = order.index(tid); pick = lambda j: {"id": order[j], "title": s.get(StudyTopic, order[j]).title} if 0 <= j < len(order) else None
    atts = s.query(StudyAttempt, StudyQuiz).join(StudyQuiz, StudyQuiz.id == StudyAttempt.quiz_id).filter(StudyQuiz.topic_id == tid, StudyAttempt.user_id == u.id).order_by(StudyAttempt.id.desc()).limit(200).all()
    return {"id": t.id, "title": t.title, "summary": t.summary or "", "content": t.content or "", "course_id": c.id, "course": c.title, "unit": un.title if un else "",
            "completed": bool(p and p.completed_at), "has_explain": bool(t.explain), "stars": study_stars(s, u.id, [tid]).get(tid, 0), "can_edit": c.owner_id == u.id or u.role == "admin", **study_ai_status(u, s), "prev": pick(i - 1), "next": pick(i + 1), "position": i + 1, "total": len(order),
            "attempts": [{"id": a.id, "quiz_id": q.id, "kind": q.kind, "score": a.score, "total": a.total, "percent": a.percent, "at": iso(a.at)} for a, q in atts]}
class DoneIn(BaseModel): completed: bool
@app.put("/api/study/topics/{tid}/progress")
def study_done(tid: int, b: DoneIn, u: User = Depends(me), s: Session = Depends(db)):
    study_topic_or_404(tid, u, s)
    p = s.query(StudyProgress).filter_by(user_id=u.id, topic_id=tid).first() or StudyProgress(user_id=u.id, topic_id=tid)
    p.completed_at = dt.datetime.utcnow() if b.completed else None; s.add(p); s.commit(); return {"ok": True}
@app.get("/api/study/topics/{tid}/explain")
async def study_explain(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = study_topic_or_404(tid, u, s); c = s.get(StudyCourse, t.course_id); prompt = in_lang(u, STUDY_PROMPTS["explain"])
    h = hashlib.sha256("|".join([t.title, t.content or "", prompt]).encode()).hexdigest()
    if t.explain and t.explain_hash == h: return {"text": t.explain, "cached": True}
    text = await study_ask(u, s, "explain", prompt, f"Course: {c.title}\nUnit: {s.get(StudyUnit, t.unit_id).title}\nTopic: {t.title}\n\nTopic content:\n{t.content}", max_tokens=4000)
    t.explain, t.explain_hash = text, h; s.commit(); return {"text": text, "cached": False}
def clean_questions(raw, want):
    out = []
    for q in (raw or {}).get("questions") or []:
        if not isinstance(q, dict): continue
        opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        try: k = int(q.get("correct"))
        except (TypeError, ValueError): continue
        text = str(q.get("text") or "").strip()
        if text and 2 <= len(opts) <= 6 and 0 <= k < len(opts) and len(set(o.lower() for o in opts)) == len(opts):
            out.append({"text": text[:1000], "options": [o[:400] for o in opts], "correct": k, "explanation": str(q.get("explanation") or "").strip()[:1000], "concept": str(q.get("concept") or "").strip()[:80]})
    return out[:want]
class NewQuizIn(BaseModel): kind: str = "mcq"
async def write_questions(u, s, kind, title, material, earlier):
    if kind not in QUIZ_SIZE: raise HTTPException(400, "kind must be mcq or quiz")
    if not (material or "").strip(): raise HTTPException(400, "This topic has no notes to ask about yet")
    n = QUIZ_SIZE[kind]; seen = [q for (raw,) in earlier for q in json.loads(raw)]
    msg = (f"Topic: {title}\n\nMaterial:\n{material}\n\nWrite {n} questions" + (", a mix of 4-option questions and a few true/false ones" if kind == "quiz" else "") + "." +
           (("\nAsk about different points than these earlier questions:\n" + "\n".join("- " + q["text"] for q in seen[:15])) if seen else ""))
    lang = u.lang or "en"; system = STUDY_PROMPTS["questions"] + ("" if lang == "en" else f"\n\nWrite the questions, options and explanations in {LANGS[lang]}, but keep the JSON keys and structure exactly as asked.")
    qs = clean_questions(ai_json(await study_ask(u, s, kind, system, msg, max_tokens=6000)), n)
    if len(qs) < max(2, n // 2): raise HTTPException(502, "The AI did not write enough usable questions. Try again.")
    return qs
@app.post("/api/study/topics/{tid}/quizzes")
async def study_new_quiz(tid: int, b: NewQuizIn, u: User = Depends(me), s: Session = Depends(db)):
    t = study_topic_or_404(tid, u, s)
    qs = await write_questions(u, s, b.kind, t.title, t.content, s.query(StudyQuiz.questions).filter_by(topic_id=tid, user_id=u.id).order_by(StudyQuiz.id.desc()).limit(3).all())
    for x in qs: x["topic_id"] = tid
    q = StudyQuiz(topic_id=tid, course_id=t.course_id, user_id=u.id, kind=b.kind, questions=json.dumps(qs, ensure_ascii=False)); s.add(q); s.commit()
    return study_quiz_view(q, u, s)
@app.post("/api/topics/{tid}/practice")
async def staff_topic_practice(tid: int, b: NewQuizIn, u: User = Depends(me), s: Session = Depends(db)):
    """A quick check or quiz the AI writes on demand from a topic of a staff-made course, just like on the courses students build."""
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    check_topic_access(u, t, s)
    body = words_of(t.content, fmt_of(t))
    mine = my_notes(s, u.id, tid)
    if mine: body = (body + "\n\nThe student's own notes:\n" + mine).strip()
    qs = await write_questions(u, s, b.kind, t.title, body, s.query(StudyQuiz.questions).filter_by(src_topic_id=tid, user_id=u.id).order_by(StudyQuiz.id.desc()).limit(3).all())
    q = StudyQuiz(topic_id=None, src_topic_id=tid, course_id=None, user_id=u.id, kind=b.kind, questions=json.dumps(qs, ensure_ascii=False)); s.add(q); s.commit()
    return study_quiz_view(q, u, s)
class FlagIn(BaseModel): index: int
@app.post("/api/study/quizzes/{qid}/flag")
def study_flag(qid: int, b: FlagIn, u: User = Depends(me), s: Session = Depends(db)):  # "this question is wrong": it never comes back in a review
    q = study_quiz_or_404(qid, u, s); qs = json.loads(q.questions)
    if not 0 <= b.index < len(qs): raise HTTPException(400, "Out of range")
    qs[b.index]["flagged"] = True; q.questions = json.dumps(qs, ensure_ascii=False); s.commit(); return {"ok": True}
class StudyTopicIn(BaseModel): title: str | None = None; content: str | None = None
@app.put("/api/study/topics/{tid}")
def study_topic_edit(tid: int, b: StudyTopicIn, u: User = Depends(me), s: Session = Depends(db)):  # the owner fixes a topic without redoing the setup
    t = s.get(StudyTopic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    study_course_or_404(t.course_id, u, s, edit=True)
    if b.title is not None:
        if not b.title.strip() or len(b.title.strip()) > 200: raise HTTPException(400, "Give the topic a title (up to 200 characters)")
        t.title = b.title.strip()
    if b.content is not None:
        if not b.content.strip(): raise HTTPException(400, "A topic needs some text")
        t.content = b.content.strip()
    s.commit(); return {"ok": True}
@app.delete("/api/study/topics/{tid}")
def study_topic_delete(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(StudyTopic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    c = study_course_or_404(t.course_id, u, s, edit=True)
    if s.query(StudyTopic).filter_by(course_id=c.id).count() <= 1: raise HTTPException(400, "A course needs at least one topic. Delete the course instead.")
    qids = [i for (i,) in s.query(StudyQuiz.id).filter_by(topic_id=tid)] or [0]
    s.query(StudyAttempt).filter(StudyAttempt.quiz_id.in_(qids)).delete(synchronize_session=False)
    for m in (StudyQuiz, StudyProgress): s.query(m).filter(m.topic_id == tid).delete(synchronize_session=False)
    uid = t.unit_id; s.delete(t); s.flush()
    if not s.query(StudyTopic.id).filter_by(unit_id=uid).first(): s.query(StudyUnit).filter_by(id=uid).delete()
    s.commit(); return {"ok": True}
def study_quiz_or_404(qid, u, s):
    q = s.get(StudyQuiz, qid)
    if not q or q.user_id != u.id: raise HTTPException(404, "Quiz not found")  # a set belongs to the person who asked for it
    if q.src_topic_id:
        t = s.get(Topic, q.src_topic_id)
        if not t: raise HTTPException(404, "Quiz not found")
        check_topic_access(u, t, s)
    elif q.topic_id: study_topic_or_404(q.topic_id, u, s)
    else: study_course_or_404(q.course_id, u, s)
    return q
def study_quiz_view(q, u, s):
    t = s.get(StudyTopic, q.topic_id) if q.topic_id else s.get(Topic, q.src_topic_id) if q.src_topic_id else None; c = s.get(StudyCourse, q.course_id) if q.course_id else None
    names = {x.id: x.title for x in s.query(StudyTopic).filter(StudyTopic.id.in_({x.get("topic_id") for x in json.loads(q.questions)} - {None} or {0}))}
    return {"id": q.id, "kind": q.kind, "topic_id": t.id if t else None, "topic": t.title if t else ("Review · " + (c.title if c else "")), "pass_percent": QUIZ_PASS,
            "questions": [{"text": x["text"], "options": x["options"], **({"topic": names.get(x.get("topic_id"), "")} if not t else {})} for x in json.loads(q.questions)]}
@app.get("/api/study/quizzes/{qid}")
def study_quiz(qid: int, u: User = Depends(me), s: Session = Depends(db)): return study_quiz_view(study_quiz_or_404(qid, u, s), u, s)
class CheckIn(BaseModel): index: int; answer: int
@app.post("/api/study/quizzes/{qid}/check")
def study_check(qid: int, b: CheckIn, u: User = Depends(me), s: Session = Depends(db)):  # practice MCQs: right or wrong at once, with the explanation
    q = study_quiz_or_404(qid, u, s)
    if q.kind not in ("mcq", "review"): raise HTTPException(400, "A quiz shows its answers after you submit it")
    qs = json.loads(q.questions)
    if not 0 <= b.index < len(qs) or not 0 <= b.answer < len(qs[b.index]["options"]): raise HTTPException(400, "Out of range")
    x = qs[b.index]; return {"ok": b.answer == x["correct"], "correct": x["correct"], "explanation": x["explanation"]}
class StudyAnswersIn(BaseModel): answers: list[int | None]
@app.post("/api/study/quizzes/{qid}/attempt")
def study_attempt(qid: int, b: StudyAnswersIn, u: User = Depends(me), s: Session = Depends(db)):
    q = study_quiz_or_404(qid, u, s); qs = json.loads(q.questions)
    if len(b.answers) != len(qs): raise HTTPException(400, "Answer every question or leave it blank")
    if any(a is not None and not 0 <= a < len(x["options"]) for a, x in zip(b.answers, qs)): raise HTTPException(400, "One of the answers is not a choice of its question")
    results = [{"chosen": a, "ok": a == x["correct"], "correct": x["correct"], "explanation": x["explanation"], "concept": x.get("concept", "")} for a, x in zip(b.answers, qs)]
    score = sum(r["ok"] for r in results); pct = round(100 * score / len(qs))
    xp0, stars0 = study_xp(s, u.id), study_stars(s, u.id, [q.topic_id]).get(q.topic_id, 0) if q.topic_id else 0
    a = StudyAttempt(quiz_id=q.id, user_id=u.id, answers=json.dumps(b.answers), score=score, total=len(qs), percent=pct); s.add(a)
    per = defaultdict(lambda: [0, 0])  # topic -> [right, asked]: each topic in the set moves on its own review schedule
    for x, r_ in zip(qs, results):
        k = x.get("topic_id") or q.topic_id
        if k: per[k][0] += r_["ok"]; per[k][1] += 1  # checks on staff-made topics have no review schedule of their own
    now, completed_now = dt.datetime.utcnow(), False
    for tid, (ok, n) in per.items():
        p = s.query(StudyProgress).filter_by(user_id=u.id, topic_id=tid).first() or StudyProgress(user_id=u.id, topic_id=tid); s.add(p)
        schedule_review(p, ok / n, now)
        if q.kind != "review" and not p.completed_at and pct >= (QUIZ_PASS if q.kind == "quiz" else 80): p.completed_at = now; completed_now = True  # a good check marks the topic learnt
    s.commit()
    xp1 = study_xp(s, u.id); stars1 = study_stars(s, u.id, [q.topic_id]).get(q.topic_id, 0) if q.topic_id else 0
    acc = {}
    for r in results:
        k = r["concept"] or "General"; g = acc.setdefault(k.lower(), {"title": k, "correct": 0, "total": 0}); g["correct"] += r["ok"]; g["total"] += 1
    areas = sorted([{**g, "percent": round(100 * g["correct"] / g["total"]), "status": area_status(round(100 * g["correct"] / g["total"]))} for g in acc.values()], key=lambda g: (g["percent"], g["title"]))
    return {"attempt_id": a.id, "score": score, "total": len(qs), "percent": pct, "passed": pct >= QUIZ_PASS, "pass_percent": QUIZ_PASS, "results": results, "areas": areas, "summary": area_summary(areas),
            "completed_now": completed_now, "stars": {"before": stars0, "after": stars1}, "xp": {"gained": xp1 - xp0, **level_of(xp1), "level_up": level_of(xp1)["level"] > level_of(xp0)["level"]},
            "next_review": next_review_phrase(per, u, s)}
@app.get("/api/study/courses/{cid}/progress")
def study_progress(cid: int, u: User = Depends(me), s: Session = Depends(db)):
    """Your progress in a course: topics completed, and each topic's best quiz score sorted into strong, getting there and needs another round."""
    c = study_course_or_404(cid, u, s); best = study_best(s, u.id, c.id)
    topics = s.query(StudyTopic).filter_by(course_id=c.id).all(); names = {t.id: t.title for t in topics}
    done = s.query(func.count(StudyProgress.id)).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_(list(names) or [0]), StudyProgress.completed_at.isnot(None)).scalar()
    areas = sorted([{"topic_id": tid, "title": names[tid], "percent": p, "status": area_status(p)} for tid, p in best.items() if tid in names], key=lambda a: (a["percent"], a["title"]))
    return {"course": c.title, "topics": len(topics), "completed": done, "quizzed": len(areas), "average": round(sum(a["percent"] for a in areas) / len(areas)) if areas else None,
            "areas": areas, "summary": area_summary(areas)}
REVIEW_DAYS = [1, 3, 7, 14, 30]  # spaced review: each good review pushes the next one further out; a poor one brings the topic back tomorrow
# -- a student's own material, filed under an official course's syllabus --
def syllabus(s, cid):  # [(unit, [topics])] in order, as students see them: published, not archived
    units = s.query(Unit).filter(Unit.course_id == cid, Unit.archived_at.is_(None)).order_by(*ORDER[Unit]).all()
    tops = defaultdict(list)
    for x in s.query(Topic).filter(Topic.unit_id.in_([un.id for un in units] or [0]), Topic.published.isnot(False), Topic.archived_at.is_(None)).order_by(*ORDER[Topic]):
        tops[x.unit_id].append(x)
    return [(un, tops[un.id]) for un in units]
def my_material(cid, u, s, make=False):  # only students file their own material, only in courses they may open
    co = s.get(Course, cid)
    if not co: raise HTTPException(404, "Course not found")
    if u.role != "student": raise HTTPException(403, "Students add their own material to a course")
    check_course_access(u, cid, s)
    m = s.query(CourseMaterial).filter_by(user_id=u.id, course_id=cid).first()
    if m is None and make:
        s.add(CourseMaterial(user_id=u.id, course_id=cid))
        try: s.commit()
        except IntegrityError: s.rollback()  # two uploads raced; one row either way
        m = s.query(CourseMaterial).filter_by(user_id=u.id, course_id=cid).one()
    return m
def norm_title(x): return re.sub(r"\s+", " ", re.sub(r"^(unit|chapter|lesson|topic|section)?\s*[\divxlc]+[.):-]?\s+|[^\w\s]", " ", (x or "").lower().lstrip("# "))).strip()
def headings_sections(paras, topics):  # without AI: each heading starts a section, filed under the syllabus topic whose title it matches best
    import difflib
    names = [(x.id, norm_title(x.title)) for x in topics]; out, last_level = [], 0
    def titled(p):  # PDFs often lose their headings: a paragraph that is, or opens with, a syllabus topic's title starts that topic
        n = norm_title(p)
        for tid, nm in names:
            if len(nm) >= 4 and (n == nm or (n.startswith(nm + " ") and len(p.split()) > len(nm.split()) and p.split()[len(nm.split())][:1].isupper())): return tid
    for i, p in enumerate(paras, 1):
        m = re.match(r"^(#{1,6})\s+(.*)", p)
        if not m and (tid := titled(p)) is not None: out.append({"from": i, "to": i, "topic_id": tid}); last_level = 6; continue
        if m or not out:
            hit, lvl = None, len(m.group(1)) if m else 0
            if m:
                h = norm_title(m.group(2)); best = max(names, key=lambda n: difflib.SequenceMatcher(None, h, n[1]).ratio(), default=None)
                if best and (h == best[1] or difflib.SequenceMatcher(None, h, best[1]).ratio() >= 0.6 or (len(best[1]) > 4 and best[1] in h)): hit = best[0]
            if hit is None and out and m and out[-1]["topic_id"] and lvl > last_level: out[-1]["to"] = i; continue  # a sub-heading stays with its topic
            if hit is not None: last_level = lvl
            out.append({"from": i, "to": i, "topic_id": hit})
        else: out[-1]["to"] = i
    return out
def normalise_sections(raw, n, refs):  # any AI answer -> sections covering paragraphs 1..n in order; refs maps "T3" to a topic id
    flat = []
    for x in (raw or {}).get("sections") or []:
        try: f = int(x.get("from"))
        except (TypeError, ValueError, AttributeError): continue
        if 1 <= f <= n: flat.append((f, refs.get(str(x.get("topic") or "").strip().upper())))
    flat = sorted(dict(sorted(flat, reverse=True)).items())  # one section per start; keeps the first answer for a start
    if not flat: return None
    if flat[0][0] != 1: flat[0] = (1, flat[0][1])
    out = []
    for k, (f, tid) in enumerate(flat):
        to = flat[k + 1][0] - 1 if k + 1 < len(flat) else n
        if out and out[-1]["topic_id"] == tid: out[-1]["to"] = to  # neighbours about the same topic become one section
        else: out.append({"from": f, "to": to, "topic_id": tid})
    return out
def material_view(m, s, cid, u):
    reading = scan_state(m, s); syl = syllabus(s, cid); paras = json.loads(m.paras or "[]") if m else []; secs = json.loads(m.sections) if m and m.sections else []
    title = {x.id: x.title for _, ts in syl for x in ts}; covered = {x["topic_id"] for x in secs if x["topic_id"] in title}
    secs = [{**x, "topic_id": x["topic_id"] if x["topic_id"] in title else None} for x in secs]  # a topic moved out of this course (or unpublished) shows as not filed yet, so saving the sections again works
    notes = {r.topic_id for r in s.query(TopicNote.topic_id).filter(TopicNote.user_id == m.user_id, TopicNote.topic_id.in_(list(title) or [0]))} if m else set()
    return {"sources": json.loads(m.sources or "[]") if m else [], "matched_by": m.matched_by if m else "", "saved_at": utc_iso(m.saved_at) if m else None,
            "syllabus": [{"id": un.id, "name": un.name, "topics": [{"id": x.id, "title": x.title, "has_notes": x.id in notes} for x in ts]} for un, ts in syl],
            "sections": [{**x, "words": sum(len(p.split()) for p in paras[x["from"] - 1:x["to"]]), "heading": paras[x["from"] - 1].lstrip("#").strip()[:120] if paras[x["from"] - 1].startswith("#") else "",
                          "excerpt": plain_excerpt(paras[x["from"] - 1:x["to"]])} for x in secs],
            "topics": sum(len(ts) for _, ts in syl), "covered": len(covered), "with_notes": len(notes), "reading": reading, "ocr_available": ocr_ready(), **study_ai_status(u, s)}
@app.get("/api/courses/{cid}/my-material")
def material_get(cid: int, u: User = Depends(me), s: Session = Depends(db)): return material_view(my_material(cid, u, s), s, cid, u)
@app.post("/api/courses/{cid}/my-material/files")
async def material_file(cid: int, request: Request, name: str = "", u: User = Depends(me), s: Session = Depends(db)):
    m = my_material(cid, u, s, make=True)
    if int(request.headers.get("content-length") or 0) > MAX_SOURCE_BYTES: raise HTTPException(413, "The file is too large. Keep it under 20 MB.")
    b = await request.body()
    if len(b) > MAX_SOURCE_BYTES: raise HTTPException(413, "The file is too large. Keep it under 20 MB.")
    kind, paras, pages = await run_in_threadpool(read_material, name or "file", b)
    if kind == "scan": src = add_scan(m, name or "file", pages); s.commit(); spawn(run_ocr, CourseMaterial, m.id, src["sid"], b, pages); return src
    src = add_material(m, name or "file", kind, paras); m.sections = None; s.commit(); return src
@app.post("/api/courses/{cid}/my-material/text")
def material_text(cid: int, b: StudyTextIn, u: User = Depends(me), s: Session = Depends(db)):
    m = my_material(cid, u, s, make=True); src = add_material(m, b.name.strip() or "Pasted text", "text", text_paras(b.text)); m.sections = None; s.commit(); return src
@app.delete("/api/courses/{cid}/my-material/sources/{i}")
def material_drop_source(cid: int, i: int, u: User = Depends(me), s: Session = Depends(db)):
    m = my_material(cid, u, s)
    sources = json.loads(m.sources or "[]") if m else []
    if not 0 <= i < len(sources): raise HTTPException(404, "No such file")
    paras = json.loads(m.paras or "[]"); start = sum(x["paras"] for x in sources[:i])
    del paras[start:start + sources[i]["paras"]]; del sources[i]
    m.paras, m.sources, m.sections, m.updated_at = json.dumps(paras, ensure_ascii=False), json.dumps(sources, ensure_ascii=False), None, dt.datetime.utcnow(); s.commit()
    return material_view(m, s, cid, u)
class MatchIn(BaseModel): method: str = "ai"
@app.post("/api/courses/{cid}/my-material/match")
async def material_match(cid: int, b: MatchIn, u: User = Depends(me), s: Session = Depends(db)):
    m = my_material(cid, u, s); paras = json.loads(m.paras or "[]") if m else []
    if m: not_while_reading(m, s)
    if not paras: raise HTTPException(400, "Add your material first")
    syl = syllabus(s, cid); topics = [x for _, ts in syl for x in ts]
    if not topics: raise HTTPException(400, "This course has no syllabus topics yet. Ask your teacher.")
    if b.method == "headings": secs = headings_sections(paras, topics)
    elif b.method == "ai":
        refs = {f"T{k}": x.id for k, x in enumerate(topics, 1)}; ref = {v: k for k, v in refs.items()}
        listing = "\n".join(f"{ref[x.id]}: {x.title} ({un.name})" for un, ts in syl for x in ts)
        co = s.get(Course, cid)
        msg = f"Course: {co.name}\n\nSyllabus topics:\n{listing}\n\nThe material has {len(paras)} paragraphs:\n\n" + slice_view(paras)
        secs = normalise_sections(ai_json(await study_ask(u, s, "match", STUDY_PROMPTS["match"], msg)), len(paras), refs)
        if not secs: raise HTTPException(502, "The AI did not return a usable matching. Try again, or match by headings.")
    else: raise HTTPException(400, "method must be ai or headings")
    m.sections, m.matched_by, m.updated_at = json.dumps(secs), b.method, dt.datetime.utcnow(); s.commit()
    return material_view(m, s, cid, u)
class SectionsIn(BaseModel): sections: list[dict]
@app.put("/api/courses/{cid}/my-material/sections")
def material_sections(cid: int, b: SectionsIn, u: User = Depends(me), s: Session = Depends(db)):
    """The student's corrections: which topic each section belongs to (or none). Sections stay in order and never overlap."""
    m = my_material(cid, u, s); n = len(json.loads(m.paras or "[]")) if m else 0
    ok = {x.id for _, ts in syllabus(s, cid) for x in ts}; last, out = 0, []
    gone = {y.get("topic_id") for y in json.loads(m.sections or "[]")} - ok - {None} if m else set()  # topics the saved filing used that are no longer in this course
    for x in b.sections:
        try: f, to = int(x["from"]), int(x["to"])
        except (KeyError, TypeError, ValueError): raise HTTPException(400, "Each section needs its first and last paragraph")
        if not (last < f <= to <= n): raise HTTPException(400, "Sections must stay in order without overlapping")
        tid = x.get("topic_id")
        if tid in gone: tid = None  # the old filing pointed at a topic that has moved away: leave that part unfiled instead of failing
        if tid is not None and tid not in ok: raise HTTPException(400, "Choose a topic of this course")
        last = to; out.append({"from": f, "to": to, "topic_id": tid})
    m.sections, m.updated_at = json.dumps(out), dt.datetime.utcnow(); s.commit(); return material_view(m, s, cid, u)
@app.get("/api/courses/{cid}/my-material/preview")
def material_preview(cid: int, start: int, end: int, u: User = Depends(me), s: Session = Depends(db)):
    m = my_material(cid, u, s); paras = json.loads(m.paras or "[]") if m else []
    if not 1 <= start <= end <= len(paras): raise HTTPException(400, "Out of range")
    return {"content": "\n\n".join(paras[start - 1:end])}
@app.post("/api/courses/{cid}/my-material/save")
def material_save(cid: int, u: User = Depends(me), s: Session = Depends(db)):
    """Writes the student's notes into each matched topic. Their notes for this course are rebuilt from the material each time; reading, completion and quiz records stay."""
    m = my_material(cid, u, s)
    if not m or not m.sections: raise HTTPException(400, "Match your material to the syllabus first")
    paras, ok = json.loads(m.paras or "[]"), {x.id for _, ts in syllabus(s, cid) for x in ts}; per = defaultdict(list)
    for x in json.loads(m.sections):
        if x["topic_id"] in ok: per[x["topic_id"]].append("\n\n".join(paras[x["from"] - 1:x["to"]]))
    if not per: raise HTTPException(400, "None of the sections is filed under a syllabus topic yet")
    course_topics = [i for (i,) in s.query(Topic.id).join(Unit, Unit.id == Topic.unit_id).filter(Unit.course_id == cid)] or [0]
    s.query(TopicNote).filter(TopicNote.user_id == u.id, TopicNote.topic_id.in_(course_topics)).delete(synchronize_session=False)
    now = dt.datetime.utcnow()
    for tid, parts in per.items(): s.add(TopicNote(user_id=u.id, topic_id=tid, content="\n\n".join(parts), updated_at=now))
    m.saved_at = now; s.commit(); return material_view(m, s, cid, u)
@app.delete("/api/courses/{cid}/my-material")
def material_delete(cid: int, u: User = Depends(me), s: Session = Depends(db)):  # the material and the notes it made; nothing else
    m = my_material(cid, u, s)
    course_topics = [i for (i,) in s.query(Topic.id).join(Unit, Unit.id == Topic.unit_id).filter(Unit.course_id == cid)] or [0]
    s.query(TopicNote).filter(TopicNote.user_id == u.id, TopicNote.topic_id.in_(course_topics)).delete(synchronize_session=False)
    if m: s.delete(m)
    s.commit(); return {"ok": True}
def my_notes(s, uid, tid):
    n = s.query(TopicNote).filter_by(user_id=uid, topic_id=tid).first(); return n.content if n else None
def schedule_review(p, ratio, now):
    step = p.review_step or 0
    if ratio >= 0.8: step = min(step + 1, len(REVIEW_DAYS))
    elif ratio < 0.6: step = 0
    p.review_step = step; p.review_due = now + dt.timedelta(days=REVIEW_DAYS[max(step - 1, 0)])
def next_review_phrase(per, u, s):
    ds = [p.review_due for p in s.query(StudyProgress).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_(list(per) or [0])) if p.review_due]
    if not ds: return ""
    n = (local_day(min(ds)) - local_day(dt.datetime.utcnow())).days
    return "Review it again tomorrow" if n <= 1 else f"Review it again in {n} days"
def study_stars(s, uid, tids):  # 1 star: completed; 2: passed a quiz (60%+); 3: mastered (90%+ in a quiz)
    tids = [t for t in tids if t]
    if not tids: return {}
    done = {t for (t,) in s.query(StudyProgress.topic_id).filter(StudyProgress.user_id == uid, StudyProgress.topic_id.in_(tids), StudyProgress.completed_at.isnot(None))}
    best = dict(s.query(StudyQuiz.topic_id, func.max(StudyAttempt.percent)).join(StudyAttempt, StudyAttempt.quiz_id == StudyQuiz.id)
                .filter(StudyQuiz.topic_id.in_(tids), StudyQuiz.kind == "quiz", StudyAttempt.user_id == uid).group_by(StudyQuiz.topic_id).all())
    return {t: 3 if (best.get(t) or 0) >= 90 else 2 if (best.get(t) or 0) >= QUIZ_PASS else 1 if t in done else 0 for t in tids}
def study_xp(s, uid):
    """Points worked out from what the student did, so they never drift: 10 per topic completed, 1 per right answer, 20 per topic with a passed quiz,
    30 more per mastered topic, 5 per review finished."""
    done = s.query(func.count(StudyProgress.id)).filter(StudyProgress.user_id == uid, StudyProgress.completed_at.isnot(None)).scalar() or 0
    right = s.query(func.coalesce(func.sum(StudyAttempt.score), 0)).filter(StudyAttempt.user_id == uid).scalar() or 0
    best = [p for _, p in s.query(StudyQuiz.topic_id, func.max(StudyAttempt.percent)).join(StudyAttempt, StudyAttempt.quiz_id == StudyQuiz.id)
            .filter(StudyAttempt.user_id == uid, StudyQuiz.kind == "quiz").group_by(StudyQuiz.topic_id)]
    reviews = s.query(func.count(StudyAttempt.id)).join(StudyQuiz, StudyQuiz.id == StudyAttempt.quiz_id).filter(StudyAttempt.user_id == uid, StudyQuiz.kind == "review").scalar() or 0
    return 10 * done + int(right) + 20 * sum(p >= QUIZ_PASS for p in best) + 30 * sum(p >= 90 for p in best) + 5 * reviews
def level_of(xp):  # level n starts at 50·n·(n−1) points: 0, 100, 300, 600, 1000 …
    n = 1
    while 50 * (n + 1) * n <= xp: n += 1
    lo, hi = 50 * n * (n - 1), 50 * (n + 1) * n
    return {"total": xp, "level": n, "into": xp - lo, "span": hi - lo}
def visible_study_courses(u, s):  # ready courses this person studies: their own and those classmates share
    mine = s.query(StudyCourse).filter_by(owner_id=u.id, status="ready").all()
    shared = []
    if u.program_id:
        mates = [i for (i,) in s.query(User.id).filter(User.program_id == u.program_id, User.id != u.id)]
        shared = s.query(StudyCourse).filter(StudyCourse.owner_id.in_(mates or [0]), StudyCourse.share == "program", StudyCourse.status == "ready").all()
    return mine + shared
def due_topics(u, s, cids, now=None):
    now = now or dt.datetime.utcnow()
    return s.query(StudyProgress, StudyTopic).join(StudyTopic, StudyTopic.id == StudyProgress.topic_id).filter(
        StudyProgress.user_id == u.id, StudyProgress.review_due.isnot(None), StudyProgress.review_due <= now, StudyTopic.course_id.in_(list(cids) or [0])).order_by(StudyProgress.review_due).all()
@app.get("/api/study/me")
def study_me(u: User = Depends(me), s: Session = Depends(db)):
    """Home for a self-learner: level and points, streak, this week, reviews due, and the one thing to do next."""
    now = dt.datetime.utcnow(); today = local_day(now); days = study_days(s, u.id, today - dt.timedelta(days=400))
    courses = visible_study_courses(u, s); cmap = {c.id: c for c in courses}
    due = due_topics(u, s, cmap, now); due_by = defaultdict(int)
    for _, t in due: due_by[t.course_id] += 1
    nxt = None
    last = s.query(StudyProgress, StudyTopic).join(StudyTopic, StudyTopic.id == StudyProgress.topic_id).filter(StudyProgress.user_id == u.id, StudyTopic.course_id.in_(list(cmap) or [0])).order_by(StudyProgress.opened_at.desc()).first()
    for c in ([cmap[last[1].course_id]] if last else []) + [c for c in courses if not last or c.id != last[1].course_id]:
        order = s.query(StudyTopic).join(StudyUnit, StudyUnit.id == StudyTopic.unit_id).filter(StudyTopic.course_id == c.id).order_by(StudyUnit.position, StudyUnit.id, StudyTopic.position, StudyTopic.id).all()
        done = {t for (t,) in s.query(StudyProgress.topic_id).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_([t.id for t in order] or [0]), StudyProgress.completed_at.isnot(None))}
        t = next((t for t in order if t.id not in done), None)
        if t: nxt = {"course_id": c.id, "course": c.title, "topic_id": t.id, "topic": t.title, "done": len(done), "topics": len(order)}; break
    week = [{"date": (today - dt.timedelta(days=i)).isoformat(), "label": (today - dt.timedelta(days=i)).strftime("%a")[0], "active": (today - dt.timedelta(days=i)) in days, "today": i == 0} for i in range(6, -1, -1)]
    return {**study_ai_status(u, s), "xp": level_of(study_xp(s, u.id)), "streak": streak_of(days, today, plan_of(s, u.id)), "active_today": today in days, "week": week, "courses": len(courses),
            "reviews_due": len(due), "review_courses": [{"course_id": cid, "course": cmap[cid].title, "due": n} for cid, n in due_by.items()], "next": nxt}
@app.post("/api/study/courses/{cid}/review")
def study_review(cid: int, u: User = Depends(me), s: Session = Depends(db)):
    """A review set from the student's own earlier questions on the topics that are due, at most two per topic and ten in all. No AI request is used."""
    import random
    c = study_course_or_404(cid, u, s); due = due_topics(u, s, [c.id])
    if not due: raise HTTPException(400, "Nothing is due for review in this course right now")
    picked = []
    for _, t in due:
        pool = [x for (raw,) in s.query(StudyQuiz.questions).filter(StudyQuiz.topic_id == t.id, StudyQuiz.user_id == u.id, StudyQuiz.kind.in_(("mcq", "quiz"))) for x in json.loads(raw) if not x.get("flagged")]
        for x in random.sample(pool, min(2, len(pool))): picked.append({**x, "topic_id": t.id})
        if len(picked) >= 10: break
    if not picked: raise HTTPException(400, "Do a quick check on these topics first, then they can be reviewed")
    random.shuffle(picked)
    q = StudyQuiz(topic_id=None, course_id=c.id, user_id=u.id, kind="review", questions=json.dumps(picked[:10], ensure_ascii=False)); s.add(q); s.commit()
    return study_quiz_view(q, u, s)
# -- own-pace routine: one session a day, never a pile of catching up --
SLOTS = {15: 1, 30: 1, 45: 2, 60: 3}  # new topics per session for the minutes a student picks
FAR = dt.datetime(9999, 1, 1)
def study_queues(u, s):
    """Every course the student studies, as a queue of topics not yet completed, in syllabus order: staff courses (with their deadlines) and their own."""
    qs, seen = [], set()
    for p in tree(u, s):
        for sm in p["semesters"]:
            for c in sm["courses"]:
                if c["id"] in seen or c.get("archived"): continue
                seen.add(c["id"]); items = []
                for un in c["units"]:
                    for x in un["topics"]:
                        if x["status"] == "completed": continue
                        due = dt.datetime.fromisoformat(x["learning_due_at"].replace("Z", "")) if x.get("learning_due_at") else None
                        items.append({"kind": "topic", "src": "course", "id": x["id"], "title": x["title"], "course": c["name"], "course_id": c["id"], "nav": [p["id"], sm["id"], c["id"], un["id"]],
                                      "due": due, "started": x["status"] == "in_progress"})
                if items: qs.append(items)
    for c in visible_study_courses(u, s):
        order = s.query(StudyTopic).join(StudyUnit, StudyUnit.id == StudyTopic.unit_id).filter(StudyTopic.course_id == c.id).order_by(StudyUnit.position, StudyUnit.id, StudyTopic.position, StudyTopic.id).all()
        prog = {p.topic_id: p for p in s.query(StudyProgress).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_([x.id for x in order] or [0]))}
        items = [{"kind": "topic", "src": "study", "id": x.id, "title": x.title, "course": c.title, "course_id": c.id, "due": None, "started": x.id in prog}
                 for x in order if not (prog.get(x.id) and prog[x.id].completed_at)]
        if items: qs.append(items)
    return qs
def pick_topics(qs, n):
    """The next n topics: ones already started, then those with deadlines (nearest first), then each course's next topic in turn so no course is left behind."""
    out, heads, used = [], [list(q) for q in qs], [0] * len(qs)
    for q in heads:
        for x in [x for x in q if x["started"]]:
            if len(out) < n: out.append(x); q.remove(x)
    for k, x in sorted(((k, x) for k, q in enumerate(heads) for x in q if x["due"]), key=lambda kx: kx[1]["due"]):
        if len(out) < n: out.append(x); heads[k].remove(x); used[k] += 1
    while len(out) < n and any(heads):
        k = min((k for k, q in enumerate(heads) if q), key=lambda k: (heads[k][0]["due"] or FAR, used[k], k))
        out.append(heads[k].pop(0)); used[k] += 1
    return out
def review_item(u, s, now):  # one review set a session: the student's course with the most topics due
    courses = {c.id: c for c in visible_study_courses(u, s)}; by = defaultdict(list)
    for _, x in due_topics(u, s, courses, now): by[x.course_id].append(x.id)
    if not by: return None
    cid = max(by, key=lambda k: len(by[k]))
    return {"kind": "review", "src": "study", "course_id": cid, "course": courses[cid].title, "title": f"Review {len(by[cid])} topic{'s' if len(by[cid]) > 1 else ''}", "topic_ids": by[cid][:5]}
def nth_study_day(days, start, k):  # the date of the k-th study day from start (0 = start itself when it is a study day)
    d, seen = start, -1
    for _ in range(3660):
        if days[d.weekday()] == "1":
            seen += 1
            if seen == k: return d
        d += dt.timedelta(days=1)
    return d
def projection(days, minutes, qs, today):
    """When everything left would be finished at this pace, and how many topics would miss their deadline. Worked out again every day from what is left."""
    slots = SLOTS.get(minutes, 1); order = pick_topics(qs, 10 ** 6)
    late = sum(1 for k, x in enumerate(order) if x["due"] and nth_study_day(days, today, k // slots) > local_day(x["due"]))
    return {"left": len(order), "finish": nth_study_day(days, today, (len(order) - 1) // slots).isoformat() if order else None, "late": late}
def plan_advice(r, qs, today):
    p = projection(r.days, r.minutes, qs, today)
    if p["late"]:
        tries = []
        if "0" in r.days: tries.append(("Add one more study day a week", r.days.replace("0", "1", 1), r.minutes))
        bigger = [m for m in sorted(SLOTS) if SLOTS[m] > SLOTS.get(r.minutes, 1)]
        if bigger: tries.append((f"Study {bigger[0]} minutes a session", r.days, bigger[0]))
        for text_, d, m in tries:
            if projection(d, m, qs, today)["late"] < p["late"]: p["advice"] = text_ + " to meet more of your deadlines."; break
    return p
def routine_view(r): return {"days": r.days, "minutes": r.minutes, "at": r.at, "new_per_session": SLOTS.get(r.minutes, 1)}
def item_done(it, u, s, now):
    if it["kind"] == "review":
        due = s.query(func.count(StudyProgress.id)).filter(StudyProgress.user_id == u.id, StudyProgress.topic_id.in_(it["topic_ids"] or [0]), StudyProgress.review_due <= now).scalar()
        return due == 0
    if it["src"] == "study":
        p = s.query(StudyProgress).filter_by(user_id=u.id, topic_id=it["id"]).first(); return bool(p and p.completed_at)
    p = s.query(Progress).filter_by(user_id=u.id, topic_id=it["id"]).first(); return bool(p and p.completed_at)
def item_alive(it, s):
    if it["kind"] == "review" or it["src"] == "study": return it["kind"] == "review" or s.get(StudyTopic, it["id"]) is not None
    x = s.get(Topic, it["id"]); return bool(x and x.published is not False and not topic_off(s, x))
def make_session(u, s, r, today, now):
    items = pick_topics(study_queues(u, s), SLOTS.get(r.minutes, 1)); rv = review_item(u, s, now)
    if rv: items.append(rv)
    for x in items: x.pop("due", None); x.pop("started", None)
    s.add(DaySession(user_id=u.id, day=today, items=json.dumps(items, ensure_ascii=False)))
    try: s.commit()
    except IntegrityError: s.rollback()  # made by a request that came at the same moment; one session either way
    return s.query(DaySession).filter_by(user_id=u.id, day=today).one()
def next_study_day(days, today):  # the next study day after today, counted by the students' day (DAY_OFFSET), not the phone's clock
    k = next(k for k in range(1, 8) if days[(today + dt.timedelta(days=k)).weekday()] == "1")  # a routine always has a study day, so within 7
    return {"in": k, "weekday": (today + dt.timedelta(days=k)).weekday()}  # weekday 0 = Monday
def session_view(u, s, r, ds, today, now):
    days = study_days(s, u.id, today - dt.timedelta(days=60)); missed, d = 0, today - dt.timedelta(days=1)
    since = max(today - dt.timedelta(days=14), local_day(r.started_at or r.updated_at or dt.datetime.utcnow()) + dt.timedelta(days=1))  # the day it was set up doesn't count
    while d >= since and d not in days:  # study days missed since they last studied, and only since the routine began
        missed += r.days[d.weekday()] == "1"; d -= dt.timedelta(days=1)
    out = {"routine": routine_view(r), "planned_today": r.days[today.weekday()] == "1", "studied_today": today in days, "missed": missed,
           "streak": streak_of(days, today, r.days), "plan": plan_advice(r, study_queues(u, s), today), "session": None,
           "next_day": next_study_day(r.days, today)}
    if ds:
        items = [x for x in json.loads(ds.items or "[]") if item_alive(x, s)]  # a topic deleted or hidden since the morning just drops out
        for x in items: x["done"] = item_done(x, u, s, now)
        if items and all(x["done"] for x in items) and not ds.done_at: ds.done_at = now; s.commit()
        out["session"] = {"day": ds.day.isoformat(), "items": items, "done": bool(ds.done_at) or not items, "caught_up": not items}
    return out
@app.get("/api/me/session")
def my_session(u: User = Depends(me), s: Session = Depends(db)):
    """Today's session on a study day (made the first time it is asked for), what the routine is, and where the plan stands. No routine: {"routine": null}."""
    r = s.get(Routine, u.id)
    if not r: return {"routine": None}
    now = dt.datetime.utcnow(); today = local_day(now); ds = s.query(DaySession).filter_by(user_id=u.id, day=today).first()
    if ds is None and r.days[today.weekday()] == "1": ds = make_session(u, s, r, today, now)
    return session_view(u, s, r, ds, today, now)
@app.post("/api/me/session")
def extra_session(u: User = Depends(me), s: Session = Depends(db)):  # study on a rest day too
    r = s.get(Routine, u.id)
    if not r: raise HTTPException(400, "Set your study routine first")
    now = dt.datetime.utcnow(); today = local_day(now); ds = s.query(DaySession).filter_by(user_id=u.id, day=today).first() or make_session(u, s, r, today, now)
    return session_view(u, s, r, ds, today, now)
class RoutineIn(BaseModel): days: str; minutes: int = 30; at: str | None = None
@app.put("/api/me/routine")
def set_routine(b: RoutineIn, u: User = Depends(me), s: Session = Depends(db)):
    if u.role != "student": raise HTTPException(403, "The study routine is for students")
    if not re.fullmatch(r"[01]{7}", b.days or "") or "1" not in b.days: raise HTTPException(400, "Pick at least one study day")
    if b.minutes not in SLOTS: raise HTTPException(400, "Pick 15, 30, 45 or 60 minutes")
    at = (b.at or "").strip() or None
    if at and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at): raise HTTPException(400, "Give the time as HH:MM, for example 19:30")
    r = s.get(Routine, u.id) or Routine(user_id=u.id); r.days, r.minutes, r.at, r.updated_at = b.days, b.minutes, at, dt.datetime.utcnow(); s.add(r)
    today = local_day(dt.datetime.utcnow()); ds = s.query(DaySession).filter_by(user_id=u.id, day=today).first()
    if ds and not any(item_done(x, u, s, dt.datetime.utcnow()) for x in json.loads(ds.items or "[]")): s.delete(ds)  # an untouched session today follows the new routine
    s.commit(); return my_session(u, s)
@app.post("/api/me/routine/stop")  # (not DELETE /api/me/routine: the older DELETE /api/{kind}/{id} route would take it)
def stop_routine(u: User = Depends(me), s: Session = Depends(db)):  # back to studying without a routine; progress is untouched
    s.query(DaySession).filter_by(user_id=u.id).delete(); s.query(Routine).filter_by(user_id=u.id).delete(); s.commit(); return {"routine": None}
# ---- notifications: worked out from what needs doing now, with each person's seen ones remembered, and an optional daily email ----
STUDENT_NOTES = ("due_soon", "quiz_new")  # a teacher's date coming up and a new test; no reminders about being late or scoring low
def notes_for(u, s):  # [{key, text, sub}]: staff get what needs attention, students their deadlines and tests. The key changes when the item does
    if u.role == "student":
        return [{"key": f"{i['kind']}:{i.get('quiz_id') or i.get('id')}"[:120], "text": i.get("title") or "", "sub": i.get("reason") or ""}
                for i in my_today(u=u, s=s)["focus"] if i.get("kind") in STUDENT_NOTES]
    return [{"key": f"{a['kind']}:{a['count']}"[:120], "text": a["text"], "sub": ""} for a in overview(u=u, s=s)["attention"]]
@app.get("/api/me/notifications")
def my_notifications(u: User = Depends(me), s: Session = Depends(db)):
    items = notes_for(u, s); seen = {k for (k,) in s.query(NoteSeen.key).filter(NoteSeen.user_id == u.id, NoteSeen.key.in_([i["key"] for i in items] or [""]))}
    return {"items": [{**i, "unread": i["key"] not in seen} for i in items], "digest": bool(u.digest), "mail": mail_on(s)}
class SeenIn(BaseModel): keys: list[str]
@app.post("/api/me/notifications/seen")
def notes_seen(b: SeenIn, u: User = Depends(me), s: Session = Depends(db)):
    have = {k for (k,) in s.query(NoteSeen.key).filter(NoteSeen.user_id == u.id)}
    for k in dict.fromkeys(x[:120] for x in b.keys[:100]):
        if k not in have: s.add(NoteSeen(user_id=u.id, key=k))
    s.query(NoteSeen).filter(NoteSeen.user_id == u.id, NoteSeen.at < dt.datetime.utcnow() - dt.timedelta(days=120)).delete()  # old ones stop mattering
    s.commit(); return {"ok": True}
class DigestIn(BaseModel): digest: bool
@app.put("/api/me/notifications/settings")
def notes_settings(b: DigestIn, u: User = Depends(me), s: Session = Depends(db)):
    if b.digest and not mail_on(s): raise HTTPException(400, "Email is not set up on this server yet")
    u.digest = b.digest; s.commit(); return {"digest": u.digest}
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR") or 7)  # the local hour (see DAY_OFFSET_MINUTES) after which the daily summary goes out
def send_digests(now=None):  # once a local day, after DIGEST_HOUR: everyone who asked gets their unseen notifications by email (nothing if there are none)
    now = now or dt.datetime.utcnow(); sent = 0
    if not mail_on() or (now + dt.timedelta(minutes=DAY_OFFSET)).hour < DIGEST_HOUR: return 0
    with Session_() as s:
        link = site_url(s) + "/app/"
        for u in s.query(User).filter(User.digest == True, User.active == True):  # noqa: E712
            if u.digest_at and local_day(u.digest_at) >= local_day(now): continue
            u.digest_at = now; s.commit()  # marked first, so a failing mail server can't make it send twice
            try:
                items = notes_for(u, s); seen = {k for (k,) in s.query(NoteSeen.key).filter(NoteSeen.user_id == u.id)}; new = [i for i in items if i["key"] not in seen]
                if not new: continue
                lines = "\n".join(f"- {i['text']}" + (f" ({i['sub']})" if i["sub"] else "") for i in new)
                send_mail(u.email, f"{APP_NAME}: {len(new)} new {'notification' if len(new) == 1 else 'notifications'}",
                          f"Hi {u.name},\n\nHere is what is new for you:\n\n{lines}\n\nOpen {APP_NAME}: {link}\n\nTo stop these emails, open the bell in the app and untick the daily summary.\n", kind="digest", link=link)
                sent += 1
            except Exception as e: log.warning("Daily summary to user %s failed: %s", u.id, type(e).__name__)
    return sent
def digest_loop():
    while True:
        try: send_digests()
        except Exception as e: log.warning("Daily summaries failed: %s", type(e).__name__)
        time.sleep(1800)
def read_head():  # the commit this server's code is at (None when it is not a git checkout)
    try: return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception: return None
SERVER_HEAD = read_head()
dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
@app.get("/api/version")  # open it in a browser to check that the screens were rebuilt after the last update: "match" should be true
def version():
    try: screens = open(os.path.join(dist, "build.txt")).read().strip() or None
    except OSError: screens = None
    return {"server": SERVER_HEAD, "screens": screens, "match": bool(SERVER_HEAD and screens and SERVER_HEAD == screens),
            "hint": None if SERVER_HEAD and screens and SERVER_HEAD == screens else "The screens are older than the server code (or were never built). Run ./run.sh, or: cd frontend && npm ci && npm run build, then restart."}
# ---- the Android app: GitHub Actions builds it in mobile/ and publishes each version as a release tagged android-v<version>. The server looks
# ---- once a day for the newest one, so the home page and the app itself can offer it (version, date and the download link) ----
ANDROID_REPO = os.getenv("ANDROID_REPO", "BT-Rajan/iniyavan")  # owner/name of the GitHub repository whose releases carry the APK; empty turns this off
ANDROID_CHECK = 24 * 3600; ANDROID_RETRY = 3600  # seconds between checks, and before trying again after GitHub could not be reached
android_seen = {"at": 0.0, "release": None}
def android_release(now=None):
    """The newest published APK as {version, code, date, url, size}, or None. Asks GitHub at most once a day (once an hour after a failure)."""
    now = now or time.time()
    if not ANDROID_REPO: return None
    if now - android_seen["at"] < (ANDROID_CHECK if android_seen["release"] else ANDROID_RETRY): return android_seen["release"]
    android_seen["at"] = now
    try:
        r = httpx.get(f"https://api.github.com/repos/{ANDROID_REPO}/releases", params={"per_page": 20}, timeout=10,
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "zigora-server"})
        r.raise_for_status()
        for rel in r.json():
            tag = rel.get("tag_name") or ""
            apk = next((x for x in rel.get("assets") or [] if (x.get("name") or "").endswith(".apk")), None)
            if rel.get("draft") or rel.get("prerelease") or not tag.startswith("android-v") or not apk: continue
            ver = tag[len("android-v"):]
            code = ver.rsplit(".", 1)[-1]
            android_seen["release"] = {"version": ver, "code": int(code) if code.isdigit() else None, "date": rel.get("published_at"),
                                       "url": apk.get("browser_download_url"), "size": apk.get("size")}
            break
    except Exception as e: log.warning("Could not check GitHub for the Android app: %s", type(e).__name__)  # the last answer stays
    return android_seen["release"]
@app.post("/api/app/android/refresh")
async def android_refresh(request: Request):
    """Look at GitHub again now. Only the server itself asks (run.sh, once a deploy's new release is out): from this machine, or with the key
    only .env can give (for a server bound to its public address). At most once a minute."""
    key = hashlib.sha256(f"android-refresh:{SECRET}".encode()).hexdigest()
    local = (request.client.host if request.client else "") in ("127.0.0.1", "::1")
    if not local and not hmac.compare_digest(request.headers.get("x-refresh-key", ""), key): raise HTTPException(403, "Only the server itself can ask for this")
    if time.time() - android_seen["at"] >= 60: android_seen["at"] = 0.0
    return JSONResponse(await run_in_threadpool(android_release) or {"version": None})
@app.get("/api/app/android")
async def android_latest():  # public: the home page shows it before anyone signs in
    rel = await run_in_threadpool(android_release)
    return JSONResponse(rel or {"version": None}, headers={"Cache-Control": "public, max-age=3600"})
# the site: the home page (web/) at the root, and the app itself under /app/
web = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(dist): app.mount("/app", StaticFiles(directory=dist, html=True), name="ui")
if os.path.isdir(web): app.mount("/", StaticFiles(directory=web, html=True), name="web")
else:
    @app.get("/", include_in_schema=False)
    def home(): return RedirectResponse("/app/")
