"""Phase 4: a teacher adds a class, invites students who already have accounts (they accept or decline), and sees their progress, read-only."""
import datetime as dt
import main
from main import Session_, User, GuardianLink, Program, Semester, Course, Unit, Topic, Progress, hp

def setup():
    with Session_() as s:
        sch = Program(name="State Board", pattern="grade"); s.add(sch); s.flush(); g6 = Semester(name="Grade 6", program_id=sch.id, semester_no=6); s.add(g6); s.flush()
        co = Course(name="Science", semester_id=g6.id, program_id=sch.id); s.add(co); s.flush(); un = Unit(name="Water", course_id=co.id, position=1); s.add(un); s.flush()
        ts = [Topic(title=x, content="c", unit_id=un.id, course_id=co.id, position=k, published=True) for k, x in enumerate(("Hard water", "Soft water", "Boiling"), 1)]; s.add_all(ts)
        t = User(name="Ms Rani", email="rani@school.in", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="school")
        mum = User(name="Mum", email="mum@x.com", pw=hp("pw"), role="guardian", relation="parent", self_registered=True, level="school")
        old = User(name="Old Student", email="old@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=sch.id, semester=6)
        s.add_all([t, mum, old]); s.commit()
        return {"sch": sch.id, "topics": [x.id for x in ts], "old": old.id}
def h(env, who): return {"Authorization": "Bearer " + env.c.post("/api/login", json={"email": who, "password": "pw"}).json()["token"]}
STU = lambda n, u, **k: dict(name=n, username=u, password="classpass1", **k)

def test_a_teacher_adds_a_class_that_signs_in_with_usernames(env):
    i = setup(); t = h(env, "rani@school.in")
    r = env.c.post("/api/guardian/students", headers=t, json={"students": [STU("Arun", "arun6", program_id=i["sch"], semester=6), STU("Bala", "bala6")]})
    assert r.status_code == 200 and [(x["username"], x["status"]) for x in r.json()["students"]] == [("arun6", "active"), ("bala6", "active")]
    assert env.c.post("/api/login", json={"email": "arun6", "password": "classpass1"}).status_code == 200
    assert env.c.post("/api/guardian/students", headers=t, json={"students": [STU("Again", "arun6")]}).status_code == 400  # usernames stay unique
    assert env.c.post("/api/guardian/students", headers=env.stu, json={"students": [STU("X", "xx1")]}).status_code == 403  # only parents and teachers

def test_a_parent_adds_another_child_up_to_the_limit(env):
    setup(); m = h(env, "mum@x.com")
    assert env.c.post("/api/guardian/students", headers=m, json={"students": [STU(f"K{n}", f"kid{n}") for n in range(8)]}).status_code == 200
    r = env.c.post("/api/guardian/students", headers=m, json={"students": [STU("Nine", "kid9")]}); assert r.status_code == 400 and "up to 8" in r.json()["detail"]
    assert env.c.post("/api/guardian/invite", headers=m, json={"login": "old@x.com"}).status_code == 403  # parents add children; teachers invite

def test_an_invitation_waits_for_the_student_and_answers_the_same_either_way(env):
    i = setup(); t = h(env, "rani@school.in")
    a = env.c.post("/api/guardian/invite", headers=t, json={"login": "Old@X.com"}).json(); b = env.c.post("/api/guardian/invite", headers=t, json={"login": "nobody@x.com"}).json()
    assert a["message"].replace("old@x.com", "") == b["message"].replace("nobody@x.com", "")  # no way to tell who has an account
    assert [x["status"] for x in env.c.get("/api/guardian/students", headers=t).json()["students"]] == ["invited"]
    assert env.c.get(f"/api/guardian/students/{i['old']}/progress", headers=t).status_code == 403  # not until they accept
    o = h(env, "old@x.com"); inv = env.c.get("/api/me/invitations", headers=o).json()["invitations"]; assert [x["name"] for x in inv] == ["Ms Rani"]
    assert any(n["key"] == f"invite:{inv[0]['id']}" for n in env.c.get("/api/me/notifications", headers=o).json()["items"])  # and the bell says so
    assert env.c.post(f"/api/me/invitations/{inv[0]['id']}/accept", headers=env.stu).status_code == 404  # only the invited student answers
    assert env.c.post(f"/api/me/invitations/{inv[0]['id']}/accept", headers=o).status_code == 200
    assert [x["status"] for x in env.c.get("/api/guardian/students", headers=t).json()["students"]] == ["active"]
    assert env.c.delete(f"/api/guardian/students/{i['old']}", headers=t).status_code == 200  # the teacher can stop following them
    with Session_() as s: assert s.query(GuardianLink).count() == 0 and s.get(User, i["old"]) is not None

def test_declining_removes_the_invitation(env):
    i = setup(); t = h(env, "rani@school.in"); env.c.post("/api/guardian/invite", headers=t, json={"login": "old@x.com"})
    o = h(env, "old@x.com"); lid = env.c.get("/api/me/invitations", headers=o).json()["invitations"][0]["id"]
    assert env.c.post(f"/api/me/invitations/{lid}/decline", headers=o).status_code == 200
    assert env.c.get("/api/guardian/students", headers=t).json()["students"] == [] and env.c.get("/api/me/invitations", headers=o).json()["invitations"] == []

def test_progress_is_per_course_and_read_only(env):
    i = setup(); t = h(env, "rani@school.in")
    env.c.post("/api/guardian/students", headers=t, json={"students": [STU("Arun", "arun6", program_id=i["sch"], semester=6)]})
    with Session_() as s:
        a = s.query(User).filter_by(username="arun6").one().id; now = dt.datetime.utcnow()
        s.add_all([Progress(user_id=a, topic_id=i["topics"][0], completed_at=now, last_read=now), Progress(user_id=a, topic_id=i["topics"][1], last_read=now)]); s.commit()
    p = env.c.get(f"/api/guardian/students/{a}/progress", headers=t).json()
    assert p["place"] == "State Board · Grade 6" and [(c["course"], c["topics"], c["completed"], c["opened"]) for c in p["courses"]] == [("Science", 3, 1, 2)]
    assert env.c.get(f"/api/guardian/students/{a}/progress", headers=h(env, "mum@x.com")).status_code == 404  # not her child

def test_a_parent_or_teacher_sets_a_new_password_for_a_username_account(env):
    i = setup(); t = h(env, "rani@school.in")
    env.c.post("/api/guardian/students", headers=t, json={"students": [STU("Arun", "arun6")]})
    with Session_() as s: a = s.query(User).filter_by(username="arun6").one().id
    kid = {"Authorization": "Bearer " + env.c.post("/api/login", json={"email": "arun6", "password": "classpass1"}).json()["token"]}
    assert env.c.get(f"/api/guardian/students/{a}/progress", headers=t).json()["can_reset"] is True
    assert env.c.put(f"/api/guardian/students/{a}/password", headers=t, json={"password": "short"}).status_code == 400
    assert env.c.put(f"/api/guardian/students/{a}/password", headers=t, json={"password": "arun6"}).status_code == 400
    assert env.c.put(f"/api/guardian/students/{a}/password", headers=t, json={"password": "newpass123"}).status_code == 200
    assert env.c.get("/api/me", headers=kid).status_code == 401  # the old sign-in ends
    assert env.c.post("/api/login", json={"email": "arun6", "password": "newpass123"}).status_code == 200
    assert env.c.put(f"/api/guardian/students/{a}/password", headers=h(env, "mum@x.com"), json={"password": "newpass123"}).status_code == 404  # not her child
    env.c.post("/api/guardian/invite", headers=t, json={"login": "old@x.com"})
    assert env.c.put(f"/api/guardian/students/{i['old']}/password", headers=t, json={"password": "newpass123"}).status_code == 403  # not accepted yet
    o = h(env, "old@x.com"); lid = env.c.get("/api/me/invitations", headers=o).json()["invitations"][0]["id"]; env.c.post(f"/api/me/invitations/{lid}/accept", headers=o)
    r = env.c.put(f"/api/guardian/students/{i['old']}/password", headers=t, json={"password": "newpass123"})
    assert r.status_code == 403 and "own email" in r.json()["detail"] and env.c.get(f"/api/guardian/students/{i['old']}/progress", headers=t).json()["can_reset"] is False
