# Tests a teacher assigns: a course quiz or an MCQ set from the bank, to one student or a group, due by a date and time, with 1, 2, 3 or
# unlimited attempts. The best attempt before the due time counts; later ones are late; with the attempts used up, the quiz waits for the due time.
import datetime as dt, json
import main
from main import Session_, User, GuardianLink, McqItem, Topic, hp
from tests.test_quiz_reports import setup, make_quiz
from tests.test_insights import me_id

def due(days=2): return (dt.datetime.utcnow() + dt.timedelta(minutes=main.DAY_OFFSET) + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
def mine(env, h=None): return {x["title"]: x for x in env.c.get("/api/me/assignments", headers=h or env.stu).json()["items"]}

def test_a_quiz_assigned_with_one_attempt(env):
    i, unit = setup(env); cid = i["course"]["Chem"]; q = make_quiz(env, unit); sid = me_id("stu@x.com")
    assert cid in [c["id"] for c in env.c.get("/api/assign/options", headers=env.admin).json()["courses"]]
    o = env.c.get(f"/api/assign/options?course_id={cid}", headers=env.admin).json()
    assert q in [x["id"] for x in o["quizzes"]] and sid in [x["id"] for x in o["students"]]
    with Session_() as s: s.add(User(name="Elsewhere", email="else@x.com", pw=hp("pw"), role="student", active=True)); s.commit()
    r = env.c.post("/api/assignments", headers=env.admin, json={"course_id": cid, "kind": "quiz", "quiz_id": q, "students": [sid, me_id("else@x.com")], "due": due(), "attempts": 1})
    assert r.status_code == 200 and r.json()["students"] == 1 and r.json()["skipped"] == 1  # not in the course: left out
    a = mine(env)["Water quiz"]; assert (a["status"], a["left"], a["attempts"]) == ("to_do", 1, 1) and a["due"] == due()
    assert any(x["key"] == "assignment" and x["target"]["quiz_id"] == q for x in env.c.get("/api/me/dashboard", headers=env.stu).json()["items"])
    assert env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]}).status_code == 200
    a = mine(env)["Water quiz"]; assert (a["status"], a["used"], a["left"]) == ("done", 1, 0) and a["best"] is not None
    r = env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]}); assert r.status_code == 403 and "all 1 attempts" in r.json()["detail"]
    lst = env.c.get("/api/assignments", headers=env.admin).json()["items"][0]; assert (lst["students"], lst["done"]) == (1, 1)
    d = env.c.get(f"/api/assignments/{lst['id']}", headers=env.admin).json(); assert d["rows"][0]["status"] == "done"
    assert env.c.patch(f"/api/assignments/{lst['id']}", headers=env.admin, json={"attempts": 2}).json()["attempts"] == 2
    assert env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [1, 1]}).status_code == 200  # a second attempt now allowed; the best stays
    assert mine(env)["Water quiz"]["best"] == a["best"]

def test_bad_requests_and_who_may_assign(env):
    i, unit = setup(env); cid = i["course"]["Chem"]; q = make_quiz(env, unit); sid = me_id("stu@x.com")
    body = {"course_id": cid, "kind": "quiz", "quiz_id": q, "students": [sid], "due": due(), "attempts": 1}
    assert env.c.post("/api/assignments", headers=env.admin, json={**body, "due": due(-1)}).status_code == 400
    assert env.c.post("/api/assignments", headers=env.admin, json={**body, "attempts": 5}).status_code == 400
    assert env.c.post("/api/assignments", headers=env.admin, json={**body, "quiz_id": 999999}).status_code == 400
    assert env.c.post("/api/assignments", headers=env.stu, json=body).status_code == 403
    aid = env.c.post("/api/assignments", headers=env.admin, json=body).json()["id"]
    assert env.c.get(f"/api/assignments/{aid}", headers=env.fac).status_code == 404  # only its teacher (or an admin)
    assert env.c.delete(f"/api/assignments/{aid}", headers=env.admin).json() == {"ok": True} and mine(env) == {}

def test_a_school_teacher_assigns_an_mcq_set_and_it_is_late_after_the_due_time(env):
    i, unit = setup(env); cid = i["course"]["Chem"]; sid = me_id("stu@x.com")
    with Session_() as s:
        t = User(name="Ms Rani", email="rani@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="college"); s.add(t); s.flush()
        s.add(GuardianLink(guardian_id=t.id, student_id=sid)); water = s.query(Topic).filter_by(unit_id=unit).first().id
        for k in range(4): s.add(McqItem(topic_id=water, course_id=cid, text=f"Q{k}", options=json.dumps(["a", "b", "c", "d"]), correct=0, explanation="", status="published"))
        s.commit()
    h = env.login("rani@x.com")
    o = env.c.get(f"/api/assign/options?course_id={cid}", headers=h).json(); assert [x["id"] for x in o["students"]] == [sid] and o["topics"][0]["mcqs"] == 4
    r = env.c.post("/api/assignments", headers=h, json={"course_id": cid, "kind": "mcq", "topic_ids": [water], "size": 3, "students": [sid], "due": due(1), "attempts": 0, "title": "Water practice"})
    aid = r.json()["id"]
    st = env.c.post(f"/api/assignments/{aid}/start", headers=env.stu, json={}).json(); assert len(st["questions"]) == 3
    assert env.c.post(f"/api/assignments/{aid}/start", headers=env.stu, json={}).json()["id"] == st["id"]  # the open one comes back
    env.c.post(f"/api/mcq/attempts/{st['id']}/submit", headers=env.stu, json={"answers": {}})  # blank answers: 0%, whatever order the options came in
    a = mine(env)["Water practice"]; assert a["status"] == "done" and a["left"] is None and a["best"] == 0 and a["late_best"] is None
    with Session_() as s:  # the due time passes just after that first set
        s.get(main.Assignment, aid).due_at = s.get(main.McqAttempt, st["id"]).submitted_at + dt.timedelta(seconds=1); s.commit()
    st = env.c.post(f"/api/assignments/{aid}/start", headers=env.stu, json={}).json()
    env.c.post(f"/api/mcq/attempts/{st['id']}/submit", headers=env.stu, json={"answers": {}})
    with Session_() as s:  # handed in a minute after the due time
        x = s.get(main.McqAttempt, st["id"]); x.submitted_at = s.get(main.Assignment, aid).due_at + dt.timedelta(minutes=1); s.commit()
    a = mine(env)["Water practice"]; assert a["used"] == 1 and a["late_best"] == 0 and a["status"] == "done"  # after the due time: late, kept apart
    assert env.c.get("/api/assignments", headers=h).json()["items"][0]["done"] == 1
