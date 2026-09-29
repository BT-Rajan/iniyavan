import os, hashlib, secrets, datetime as dt, httpx, jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, func, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
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
class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True); name = Column(String(150)); owner_id = Column(Integer, ForeignKey("users.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True); title = Column(String(200)); owner_id = Column(Integer, ForeignKey("users.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"))
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

app = FastAPI(title="Eng Tutor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def boot():
    Base.metadata.create_all(engine)
    if "unit_id" not in [c["name"] for c in inspect(engine).get_columns("topics")]:  # upgrade from the pre-unit schema
        with engine.begin() as c: c.execute(text("ALTER TABLE topics ADD COLUMN unit_id INT NULL"))
    with Session_() as s:  # topics without a unit go into a "General" unit per subject
        for sub in s.query(Subject).all():
            orphans = s.query(Topic).filter(Topic.subject_id == sub.id, Topic.unit_id.is_(None)).all()
            if orphans:
                un = Unit(name="General", subject_id=sub.id, owner_id=sub.owner_id); s.add(un); s.flush()
                for t in orphans: t.unit_id = un.id
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
class NewUser(BaseModel): name: str; email: str; password: str; role: str = "student"
class UserPatch(BaseModel): active: bool | None = None; password: str | None = None
@app.get("/api/admin/users")
def users(_: User = Depends(admin), s: Session = Depends(db)):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active} for u in s.query(User).order_by(User.id)]
@app.post("/api/admin/users")
def add_user(b: NewUser, _: User = Depends(admin), s: Session = Depends(db)):
    if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
    e = b.email.strip().lower()
    if s.query(User).filter_by(email=e).first(): raise HTTPException(400, "That email is already registered")
    s.add(User(name=b.name, email=e, pw=hp(b.password), role="admin" if b.role == "admin" else "student")); s.commit(); return {"ok": True}
@app.patch("/api/admin/users/{uid}")
def patch_user(uid: int, b: UserPatch, a: User = Depends(admin), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "No such user")
    if b.active is not None and u.id != a.id: u.active = b.active
    if b.password:
        if len(b.password) < 8: raise HTTPException(400, "Use at least 8 characters")
        u.pw = hp(b.password)
    s.commit(); return {"ok": True}
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

# ---- content: admin writes, everyone reads ----
class CourseIn(BaseModel): name: str
class SubjectIn(BaseModel): name: str; course_id: int
class UnitIn(BaseModel): name: str; subject_id: int
class TopicIn(BaseModel):
    title: str; unit_id: int; content: str = ""; sample_content: str = ""; question_pattern: str = ""; guideline: str = ""
M = {"courses": Course, "subjects": Subject, "units": Unit, "topics": Topic}
@app.get("/api/tree")
def tree(u: User = Depends(me), s: Session = Depends(db)):
    read = {p.topic_id for p in s.query(Progress).filter_by(user_id=u.id)}
    topics = s.query(Topic).order_by(Topic.id).all(); units = s.query(Unit).order_by(Unit.id).all(); subs = s.query(Subject).order_by(Subject.id).all()
    return [{"id": c.id, "name": c.name, "subjects": [{"id": x.id, "name": x.name, "units": [{"id": n.id, "name": n.name, "topics": [
        {"id": t.id, "title": t.title, "read": t.id in read} for t in topics if t.unit_id == n.id]}
        for n in units if n.subject_id == x.id]} for x in subs if x.course_id == c.id]} for c in s.query(Course).order_by(Course.id)]
def save_row(row, u, s): row.owner_id = u.id; s.add(row); s.commit(); return {"id": row.id}
def topic_fields(b, s):
    un = s.get(Unit, b.unit_id)
    if not un: raise HTTPException(400, "Choose a unit for this topic")
    return {**b.dict(), "subject_id": un.subject_id}
def update(row, vals, s):
    if not row: raise HTTPException(404, "Not found")
    for k, v in vals.items(): setattr(row, k, v)
    s.commit(); return {"ok": True}
@app.post("/api/courses")
def new_course(b: CourseIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Course(name=b.name), u, s)
@app.post("/api/subjects")
def new_subject(b: SubjectIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Subject(**b.dict()), u, s)
@app.post("/api/units")
def new_unit(b: UnitIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Unit(**b.dict()), u, s)
@app.post("/api/topics")
def new_topic(b: TopicIn, u: User = Depends(admin), s: Session = Depends(db)): return save_row(Topic(**topic_fields(b, s)), u, s)
@app.put("/api/courses/{rid}")
def edit_course(rid: int, b: CourseIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Course, rid), b.dict(), s)
@app.put("/api/subjects/{rid}")
def edit_subject(rid: int, b: SubjectIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Subject, rid), b.dict(), s)
@app.put("/api/units/{rid}")
def edit_unit(rid: int, b: UnitIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Unit, rid), b.dict(), s)
@app.put("/api/topics/{rid}")
def edit_topic(rid: int, b: TopicIn, _: User = Depends(admin), s: Session = Depends(db)): return update(s.get(Topic, rid), topic_fields(b, s), s)
@app.delete("/api/{kind}/{rid}")
def remove(kind: str, rid: int, _: User = Depends(admin), s: Session = Depends(db)):
    if kind not in M: raise HTTPException(404, "Unknown item")
    r = s.get(M[kind], rid)
    if not r: raise HTTPException(404, "Not found")
    def clear(sid): s.query(Topic).filter_by(subject_id=sid).delete(); s.query(Unit).filter_by(subject_id=sid).delete()
    if kind == "courses":
        for x in s.query(Subject).filter_by(course_id=rid).all(): clear(x.id); s.delete(x)
    if kind == "subjects": clear(rid)
    if kind == "units": s.query(Topic).filter_by(unit_id=rid).delete()
    s.delete(r); s.commit(); return {"ok": True}

def full(t, s):
    sub = s.get(Subject, t.subject_id); c = s.get(Course, sub.course_id); un = s.get(Unit, t.unit_id) if t.unit_id else None
    return {"id": t.id, "title": t.title, "subject_id": t.subject_id, "unit_id": t.unit_id, "unit": un.name if un else "", "subject": sub.name, "course": c.name,
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
             .filter(Progress.user_id == u.id, Topic.subject_id == t.subject_id, Topic.id != tid).limit(8)]
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
    msg = f"Course: {f['course']}\nSubject: {f['subject']}\nUnit: {f['unit']}\nTopic: {f['title']}\n\nTopic content:\n{f['content']}\n\n" + (
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
