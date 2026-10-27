"""Phase 3: a school student who signed up (or was added by a parent) uses AI only on a linked parent's or teacher's own key; without one, AI is off."""
import main
from main import Session_, User, GuardianLink, Program, Semester, Setting, seal, hp

def setup():
    with Session_() as s:
        s.merge(Setting(k="deepseek_key", v="sk-college-key-0000000000"))
        sch = Program(name="State Board", pattern="grade"); col = Program(name="B.E.", pattern="semester"); s.add_all([sch, col]); s.flush()
        s.add_all([Semester(name="Grade 6", program_id=sch.id, semester_no=6), Semester(name="Semester 1", program_id=col.id, semester_no=1)])
        kid = User(name="Kavin", username="kavin", pw=hp("pw"), role="student", self_registered=True, program_id=sch.id, semester=6)
        mum = User(name="Mum", email="mum@x.com", pw=hp("pw"), role="guardian", relation="parent", self_registered=True, level="school")
        tch = User(name="Teacher", email="t@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="school")
        uni = User(name="Uni", email="uni@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1)
        added = User(name="Added", email="added@x.com", pw=hp("pw"), role="student", program_id=sch.id, semester=6)  # placed by the admin, not self-registered
        s.add_all([kid, mum, tch, uni, added]); s.flush()
        s.add_all([GuardianLink(guardian_id=mum.id, student_id=kid.id), GuardianLink(guardian_id=tch.id, student_id=kid.id)]); s.commit()
        return {x.name: x.id for x in (kid, mum, tch, uni, added)}
def key(uid):
    with Session_() as s: return main.key_for(s.get(User, uid), s)
def set_key(uid, k):
    with Session_() as s: s.get(User, uid).ai_key = seal(k) if k else None; s.commit()
def login(env, who): return {"Authorization": "Bearer " + env.c.post("/api/login", json={"email": who, "password": "pw"}).json()["token"]}

def test_without_a_guardian_key_a_school_student_has_no_ai(env):
    i = setup(); h = login(env, "kavin")
    st = env.c.get("/api/ai/status", headers=h).json(); assert (st["available"], st["off"], st["plan"], st["own_key"]) == (False, True, "off", False)
    assert env.c.get("/api/me", headers=h).json()["ai_off"] is True and key(i["Kavin"]) is None  # never the college's key
    assert env.c.get("/api/me/plan", headers=h).json()["plan"] == "off"  # and no Lite allowance
    r = env.c.put("/api/me/ai-key", headers=h, json={"key": "sk-" + "x" * 30}); assert r.status_code == 403 and "parent or teacher" in r.json()["detail"]
    r = env.c.post("/api/search/ai", headers=h, json={"q": "hard water"}); assert r.status_code == 503 and "parent or teacher" in r.json()["detail"]

def test_a_parents_key_turns_it_on_and_comes_before_a_teachers(env):
    i = setup(); set_key(i["Teacher"], "sk-teacher-key-111111111111"); assert key(i["Kavin"]) == "sk-teacher-key-111111111111"
    set_key(i["Mum"], "sk-parent-key-2222222222222"); assert key(i["Kavin"]) == "sk-parent-key-2222222222222"  # the parent's first
    h = login(env, "kavin"); st = env.c.get("/api/ai/status", headers=h).json()
    assert (st["available"], st["off"], st["plan"]) == (True, False, "family") and env.c.get("/api/me", headers=h).json()["ai_off"] is False
    with Session_() as s: s.get(User, i["Mum"]).active = False; s.commit()
    assert key(i["Kavin"]) == "sk-teacher-key-111111111111"  # a disabled parent's key is not used
    with Session_() as s: s.query(GuardianLink).filter_by(guardian_id=i["Teacher"]).update({"status": "invited"}); s.commit()
    assert key(i["Kavin"]) is None  # an invitation not yet accepted gives nothing

def test_others_keep_the_rules_they_had(env):
    i = setup()
    assert key(i["Uni"]) == "sk-college-key-0000000000" and env.c.get("/api/ai/status", headers=login(env, "uni@x.com")).json()["plan"] == "lite"  # college: Lite
    assert key(i["Added"]) == "sk-college-key-0000000000"  # a school student the admin added uses the school's own key
    assert key(i["Mum"]) is None  # a parent never uses the college's key themselves
    set_key(i["Mum"], "sk-parent-key-2222222222222"); assert key(i["Mum"]) == "sk-parent-key-2222222222222"
    assert env.c.get("/api/ai/status", headers=login(env, "mum@x.com")).json()["off"] is False and env.c.get("/api/ai/status", headers=login(env, "mum@x.com")).json()["plan"] == "own"
