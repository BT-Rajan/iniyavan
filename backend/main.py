from collections import defaultdict
import csv, io, os, re, hashlib, secrets, datetime as dt, httpx, jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, func, or_, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
APP_NAME = (os.getenv("APP_NAME") or "Eng Tutor").strip()
VERSION = "1.1.0"
DB = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/engtutor")
SECRET = os.getenv("JWT_SECRET", "change-me")
engine = create_engine(DB, pool_pre_ping=True)
Session_ = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100)); email = Column(String(190), unique=True)
    pw = Column(String(200)); role = Column(String(10), default="student"); active = Column(Boolean, default=True)
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
class Progress(Base):  # what each student has read
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id")); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    reads = Column(Integer, default=1); last_read = Column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
class AICache(Base):  # shared by all students; key changes when the topic is edited
    __tablename__ = "ai_cache"
    id = Column(Integer, primary_key=True); topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    kind = Column(String(10)); chash = Column(String(64)); text = Column(Text)
    tokens = Column(Integer, default=0); hits = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint("topic_id", "kind", "chash"),)

def hp(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100000).hex()
def vp(p, h): return hp(p, h.split("$")[0]) == h
def db():
    s = Session_()
    try: yield s
    finally: s.close()
def me(authorization: str = Header(""), s: Session = Depends(db)):
    try: uid = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])["uid"]
    except Exception: raise HTTPException(401, "Please sign in again")
    u = s.get(User, uid)
    if not u or not u.active: raise HTTPException(401, "Account disabled. Ask your admin.")
    return u
def admin(u: User = Depends(me)):
    if u.role != "admin": raise HTTPException(403, "Admins only")
    return u
def setting(s, k, d=""):
    r = s.get(Setting, k); return r.v if r else d

app = FastAPI(title=APP_NAME)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/config")
def config(): return {"name": APP_NAME, "version": VERSION}
@app.get("/manifest.json")  # served dynamically so the installed app carries APP_NAME
def manifest():
    icons = [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
             {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
             {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    return JSONResponse({"name": APP_NAME, "short_name": APP_NAME[:12], "start_url": "/", "scope": "/", "display": "standalone", "orientation": "portrait",
                         "background_color": "#0e0a1f", "theme_color": "#0e0a1f", "icons": icons})

@app.on_event("startup")
def boot():
    Base.metadata.create_all(engine)
    cols = lambda t: [c["name"] for c in inspect(engine).get_columns(t)]
    add_unit, add_sem = "unit_id" not in cols("topics"), "semester_id" not in cols("subjects")
    with engine.begin() as c:  # upgrade older schemas in place
        if add_unit: c.execute(text("ALTER TABLE topics ADD COLUMN unit_id INT NULL"))
        if add_sem: c.execute(text("ALTER TABLE subjects ADD COLUMN semester_id INT NULL"))
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
@app.post("/api/login")
def login(b: Login, s: Session = Depends(db)):
    u = s.query(User).filter_by(email=b.email.strip().lower()).first()
    if not u or not vp(b.password, u.pw): raise HTTPException(401, "Wrong email or password")
    if not u.active: raise HTTPException(403, "Account disabled. Ask your admin.")
    return {"token": jwt.encode({"uid": u.id, "exp": dt.datetime.utcnow() + dt.timedelta(days=14)}, SECRET), "user": {"id": u.id, "name": u.name, "role": u.role}}
@app.get("/api/me")
def whoami(u: User = Depends(me)): return {"id": u.id, "name": u.name, "role": u.role}

# ---- admin ----
ROLES = ("student", "admin")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PWCHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
class NewUser(BaseModel): name: str; email: str; password: str; role: str = "student"; active: bool = True
class UserPatch(BaseModel):
    name: str | None = None; email: str | None = None; role: str | None = None; active: bool | None = None; password: str | None = None
@app.get("/api/admin/users")
def users(q: str = "", limit: int = 50, offset: int = 0, _: User = Depends(admin), s: Session = Depends(db)):
    qs = s.query(User)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        qs = qs.filter(or_(func.lower(User.name).like(like), func.lower(User.email).like(like), func.lower(User.role).like(like)))
    rows = qs.order_by(User.role, User.name).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
    return {"total": qs.count(), "items": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active} for u in rows]}
@app.post("/api/admin/users")
def add_user(b: NewUser, _: User = Depends(admin), s: Session = Depends(db)):
    e, name = b.email.strip().lower(), b.name.strip()
    if not name: raise HTTPException(400, "Enter a name")
    if not EMAIL.match(e): raise HTTPException(400, "Enter a valid email")
    if b.role not in ROLES: raise HTTPException(400, "Role must be student or admin")
    if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
    if s.query(User).filter_by(email=e).first(): raise HTTPException(400, "That email is already registered")
    s.add(User(name=name, email=e, pw=hp(b.password), role=b.role, active=b.active)); s.commit(); return {"ok": True}
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
        if b.role not in ROLES: raise HTTPException(400, "Role must be student or admin")
        u.role = b.role
    if b.active is not None: u.active = b.active
    if b.password:
        if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
        u.pw = hp(b.password)
    s.commit(); return {"ok": True}
class UserImportIn(BaseModel): csv: str; dry_run: bool = True
UALIAS = {"full_name": "name", "student": "name", "student_name": "name", "e-mail": "email", "mail": "email", "email_address": "email", "pass": "password", "user_role": "role"}
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
    existing = {u.email: u for u in s.query(User)}
    seen, errors, creds = set(), [], []; created = updated = generated = 0
    for n, row in enumerate(rows, start=2):
        v = {k: (row.get(k) or "").strip() for k in rd.fieldnames if k}
        if not any(v.values()): continue
        e = v.get("email", "").lower(); role = v.get("role", "").lower() or None; pw = v.get("password", "")
        def bad(msg): errors.append({"row": n, "error": msg})
        if not EMAIL.match(e): bad("Invalid email"); continue
        if e in seen: bad("Duplicate email in this file"); continue
        if role and role not in ROLES: bad("Role must be student or admin"); continue
        if pw and len(pw) < 8: bad("Password needs 8+ characters"); continue
        name = v.get("name") or e.split("@")[0]
        if len(name) > 100 or len(e) > 190: bad("Name or email is too long"); continue
        seen.add(e); u = existing.get(e)
        if u:
            if u.id == a.id and role and role != u.role: bad("You can't change your own role"); continue
            if v.get("name"): u.name = name
            if role: u.role = role
            if pw and not b.dry_run: u.pw = hp(pw)
            updated += 1
        else:
            created += 1; generated += not pw
            if not b.dry_run:
                final = pw or "".join(secrets.choice(PWCHARS) for _ in range(10))
                s.add(User(name=name, email=e, pw=hp(final), role=role or "student"))
                if not pw: creds.append({"name": name, "email": e, "password": final})
    s.rollback() if b.dry_run else s.commit()
    return {"dry_run": b.dry_run, "rows": len(rows), "valid_rows": created + updated, "created": created, "updated": updated, "generated": generated,
            "error_count": len(errors), "errors": errors[:20], "credentials": creds}
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

# ---- content: admin writes, everyone reads ----
class ProgramIn(BaseModel): name: str
class SemesterIn(BaseModel): name: str; program_id: int
class CourseIn(BaseModel): name: str; semester_id: int
class UnitIn(BaseModel): name: str; course_id: int
class TopicIn(BaseModel):
    title: str; unit_id: int; content: str = ""; sample_content: str = ""; question_pattern: str = ""; guideline: str = ""
M = {"programs": Program, "semesters": Semester, "courses": Course, "units": Unit, "topics": Topic}
@app.get("/api/tree")
def tree(u: User = Depends(me), s: Session = Depends(db)):
    read = {p.topic_id for p in s.query(Progress).filter_by(user_id=u.id)}
    def g(model, k):
        d = defaultdict(list)
        for r in s.query(model).order_by(model.id): d[getattr(r, k)].append(r)
        return d
    tp, un, co, se = g(Topic, "unit_id"), g(Unit, "course_id"), g(Course, "semester_id"), g(Semester, "program_id")
    return [{"id": p.id, "name": p.name, "semesters": [{"id": sm.id, "name": sm.name, "courses": [{"id": c.id, "name": c.name, "units": [
        {"id": n.id, "name": n.name, "topics": [{"id": t.id, "title": t.title, "read": t.id in read} for t in tp[n.id]]} for n in un[c.id]]}
        for c in co[sm.id]]} for sm in se[p.id]]} for p in s.query(Program).order_by(Program.id)]
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
@app.post("/api/programs")
def new_program(b: ProgramIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Program(name=b.name), u, s)
@app.post("/api/semesters")
def new_semester(b: SemesterIn, u: User = Depends(admin), s: Session = Depends(db)):
    if not s.get(Program, b.program_id): raise HTTPException(400, "Choose a program for this semester")
    return save_row(Semester(**b.dict()), u, s)
@app.post("/api/courses")
def new_course(b: CourseIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Course(**course_fields(b, s)), u, s)
@app.post("/api/units")
def new_unit(b: UnitIn, u: User = Depends(admin), s: Session = Depends(db)):
    if not s.get(Course, b.course_id): raise HTTPException(400, "Choose a course for this unit")
    return save_row(Unit(**b.dict()), u, s)
@app.post("/api/topics")
def new_topic(b: TopicIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Topic(**topic_fields(b, s)), u, s)
@app.put("/api/programs/{rid}")
def edit_program(rid: int, b: ProgramIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Program, rid), b.dict(), s)
@app.put("/api/semesters/{rid}")
def edit_semester(rid: int, b: SemesterIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Semester, rid), b.dict(), s)
@app.put("/api/courses/{rid}")
def edit_course(rid: int, b: CourseIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Course, rid), course_fields(b, s), s)
@app.put("/api/units/{rid}")
def edit_unit(rid: int, b: UnitIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Unit, rid), b.dict(), s)
@app.put("/api/topics/{rid}")
def edit_topic(rid: int, b: TopicIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Topic, rid), topic_fields(b, s), s)
@app.delete("/api/{kind}/{rid}")
def remove(kind: str, rid: int, _: User = Depends(admin), s: Session = Depends(db)):
    if kind not in M: raise HTTPException(404, "Unknown item")
    r = s.get(M[kind], rid)
    if not r: raise HTTPException(404, "Not found")
    def drop_course(c): s.query(Topic).filter_by(course_id=c.id).delete(); s.query(Unit).filter_by(course_id=c.id).delete(); s.delete(c)
    if kind == "programs":
        for c in s.query(Course).filter_by(program_id=rid).all(): drop_course(c)
        s.query(Semester).filter_by(program_id=rid).delete()
    if kind == "semesters":
        for c in s.query(Course).filter_by(semester_id=rid).all(): drop_course(c)
    if kind == "courses": drop_course(r); r = None
    if kind == "units": s.query(Topic).filter_by(unit_id=rid).delete()
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
            "content": t.content, "sample_content": t.sample_content, "question_pattern": t.question_pattern, "guideline": t.guideline}
@app.get("/api/topics/{tid}")
def topic(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
    return full(t, s)
@app.post("/api/topics/{tid}/read")
def read(tid: int, u: User = Depends(me), s: Session = Depends(db)):
    t = s.get(Topic, tid)
    if not t: raise HTTPException(404, "Topic not found")
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

dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(dist): app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
