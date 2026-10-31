# A student can start a topic, or a whole course, over: it reads "not started" again, their quiz scores stay, and the days they studied still
# count toward their streak.
import datetime as dt
import main
from main import Session_, Progress, ProgressHistory, Topic, Unit, Attempt
from tests.test_quiz_reports import setup, make_quiz
from tests.test_insights import me_id

def status(env, tid): return env.c.get(f"/api/topics/{tid}", headers=env.stu).json().get("status")

def test_redo_a_topic_then_a_course_keeps_scores_and_the_streak(env):
    i, unit = setup(env); sid = me_id("stu@x.com"); cid = i["course"]["Chem"]
    with Session_() as s: tids = [t.id for t in s.query(Topic).filter_by(unit_id=unit)]
    for t in tids: env.c.post(f"/api/topics/{t}/read", headers=env.stu); env.c.put(f"/api/topics/{t}/complete", headers=env.stu, json={"completed": True})
    q = make_quiz(env, unit); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]})
    streak = env.c.get("/api/me/today", headers=env.stu).json()["streak"]; assert streak >= 1
    r = env.c.post(f"/api/topics/{tids[0]}/redo", headers=env.stu); assert r.json() == {"ok": True, "topics": 1}
    with Session_() as s:
        assert s.query(Progress).filter_by(user_id=sid, topic_id=tids[0]).first() is None
        h = s.query(ProgressHistory).filter_by(user_id=sid, topic_id=tids[0]).one(); assert h.completed_at is not None
    assert env.c.post(f"/api/courses/{cid}/redo", headers=env.stu).json()["topics"] == len(tids) - 1
    tree = env.c.get("/api/tree", headers=env.stu).json()
    statuses = [t["status"] for p in tree for sm in p["semesters"] for c in sm["courses"] if c["id"] == cid for un in c["units"] for t in un["topics"]]
    assert statuses and set(statuses) == {"not_started"}
    with Session_() as s: assert s.query(Attempt).filter_by(user_id=sid).count() == 1  # their score stays
    assert env.c.get("/api/me/today", headers=env.stu).json()["streak"] == streak  # and so does their streak

def test_only_what_they_can_see(env):
    i, unit = setup(env)
    other = i["course"]["Maths"]  # another program's course
    assert env.c.post(f"/api/courses/{other}/redo", headers=env.stu).status_code in (403, 404)
    assert env.c.post("/api/topics/999999/redo", headers=env.stu).status_code == 404
