import datetime as dt
import main
from main import Session_, User, Topic, Progress, Attempt, ActivityDay
from tests.test_access import ids, enrol

CSV = ("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\nMech,Semester 1,Chem,U1,Boilers,b\nMech,Semester 1,Chem,U2,Fuels,f\nMech,Semester 1,Workshop,U1,Tools,t\n")
QS = [{"text": "Q1?", "options": ["a", "b"], "correct": 0}, {"text": "Q2?", "options": ["a", "b"], "correct": 0}]

def setup(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1); return i
def plan(env, h=None): return env.c.get("/api/me/today", headers=h or env.stu).json()
def kinds(p): return [(f["kind"], f["title"]) for f in p["focus"]]
def due(i, name, delta):
    with Session_() as s: s.get(Topic, i["topic"][name]).learning_due_at = dt.datetime.utcnow() + delta; s.commit()
def day_ago(n): return dt.datetime.utcnow() - dt.timedelta(days=n)

def test_a_new_student_is_pointed_at_the_first_topic_of_each_course(env):
    i = setup(env); p = plan(env)
    assert p["streak"] == 0 and p["active_today"] is False and p["topics_total"] == 4 and p["topics_completed"] == 0 and p["percent"] == 0 and p["quiz_average"] is None
    assert [f["kind"] for f in p["focus"]] == ["next", "next"] and {f["title"] for f in p["focus"]} == {"Water", "Tools"}  # one per course, never every topic
    assert len(p["week"]) == 7 and p["week"][-1]["today"] is True and not any(d["active"] for d in p["week"])
    f = next(x for x in p["focus"] if x["title"] == "Water"); assert f["topic_id"] == i["topic"]["Water"] and f["course"] == "Chem" and len(f["nav"]) == 4

def test_overdue_beats_due_soon_beats_weak_beats_resume_beats_quizzes(env):
    i = setup(env); due(i, "Fuels", dt.timedelta(days=-3)); due(i, "Boilers", dt.timedelta(days=1)); due(i, "Tools", dt.timedelta(days=30))
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": i["unit"][i["course"]["Chem"]], "title": "Chem quiz", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": QS})
    env.c.post(f"/api/topics/{i['topic']['Water']}/read", headers=env.stu)  # Water is now in progress
    p = plan(env); got = {k: t for k, t in kinds(p)}
    assert [f["kind"] for f in p["focus"]][:2] == ["overdue", "due_soon"] and p["focus"][0]["title"] == "Fuels" and p["focus"][0]["reason"] == "Overdue by 3 days" and p["focus"][1]["reason"] == "Due tomorrow"
    assert len(p["focus"]) == 4 and {"resume", "quiz_new"} <= set(got)
    assert next(f for f in p["focus"] if f["kind"] == "quiz_new")["reason"] == "Quiz not tried yet · 2 questions"
    assert next(f for f in p["focus"] if f["kind"] == "resume")["title"] == "Water"

def test_a_topic_appears_once_and_completed_ones_leave_the_list(env):
    i = setup(env); due(i, "Water", dt.timedelta(days=-1)); env.c.post(f"/api/topics/{i['topic']['Water']}/read", headers=env.stu)  # overdue AND in progress
    assert [t for k, t in kinds(plan(env))].count("Water") == 1 and kinds(plan(env))[0][0] == "overdue"
    env.c.put(f"/api/topics/{i['topic']['Water']}/complete", headers=env.stu); p = plan(env)
    assert "Water" not in [t for _, t in kinds(p)] and p["topics_completed"] == 1 and p["percent"] == 25 and ("next", "Boilers") in kinds(p)

def test_weak_quiz_areas_and_retakes_are_suggested(env):
    i = setup(env); unit = i["unit"][i["course"]["Chem"]]
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": unit, "title": "Chem quiz", "published": True, "pass_percent": 80}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [{**x, "topic_id": i["topic"]["Fuels"]} for x in QS]})
    env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [1, 1]})  # 0%
    p = plan(env); k = {f["kind"]: f for f in p["focus"]}
    assert k["weak"]["title"] == "Fuels" and "0%" in k["weak"]["reason"] and k["quiz_retake"]["reason"] == "Best so far 0%, pass mark 80%" and p["quiz_average"] == 0
    env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]})
    assert "quiz_retake" not in {f["kind"] for f in plan(env)["focus"]} and plan(env)["quiz_average"] == 100

def test_streak_counts_consecutive_days_and_survives_a_day_not_yet_studied(env):
    i = setup(env); w = i["topic"]["Water"]; uid = env.stu_id if hasattr(env, "stu_id") else None
    with Session_() as s: uid = s.query(User).filter_by(email="stu@x.com").first().id
    def study(n, reads=1):
        with Session_() as s:
            d = main.local_day(day_ago(n)); r = s.query(ActivityDay).filter_by(user_id=uid, day=d).first()
            if r: r.reads += reads
            else: s.add(ActivityDay(user_id=uid, day=d, reads=reads))
            s.commit()
    for n in (1, 2, 3): study(n)
    p = plan(env); assert p["streak"] == 3 and p["active_today"] is False  # today not studied yet, the streak is still alive
    assert [d["active"] for d in p["week"]][-4:] == [True, True, True, False]
    env.c.post(f"/api/topics/{w}/read", headers=env.stu); p = plan(env); assert p["streak"] == 4 and p["active_today"] is True and p["week"][-1]["active"] is True
    env.c.post(f"/api/topics/{w}/read", headers=env.stu)
    with Session_() as s: assert s.query(ActivityDay).filter_by(user_id=uid, day=main.local_day(dt.datetime.utcnow())).one().reads == 2  # one row a day
    study(5); assert plan(env)["streak"] == 4  # a gap on day 4 ends the run; day 5 does not rejoin it

def test_completions_and_quiz_attempts_count_as_study_days_even_without_opens(env):
    i = setup(env)
    with Session_() as s:
        uid = s.query(User).filter_by(email="stu@x.com").first().id
        s.add(Progress(user_id=uid, topic_id=i["topic"]["Water"], reads=1, last_read=day_ago(5), completed_at=day_ago(1)))
        s.commit()
    p = plan(env); assert p["streak"] == 1 and sum(d["active"] for d in p["week"]) == 2 and p["completed_this_week"] == 1 and p["active_days_week"] == 2

def test_the_day_follows_the_configured_offset_and_each_student_sees_only_their_own(env, monkeypatch):
    monkeypatch.setattr(main, "DAY_OFFSET", 0); t = dt.datetime(2026, 10, 5, 23, 0); assert main.local_day(t) == dt.date(2026, 10, 5)
    monkeypatch.setattr(main, "DAY_OFFSET", 330); assert main.local_day(t) == dt.date(2026, 10, 6)  # 4:30 am in India is already the next day
    assert main.streak_of({dt.date(2026, 10, 4), dt.date(2026, 10, 3)}, dt.date(2026, 10, 5)) == 2 and main.streak_of(set(), dt.date(2026, 10, 5)) == 0
    i = setup(env); env.c.post(f"/api/topics/{i['topic']['Water']}/read", headers=env.stu)
    env.add_user("other@x.com", program=i["prog"]["Mech"], semester=1); o = plan(env, env.login("other@x.com")); assert o["streak"] == 0 and o["active_today"] is False
    assert env.c.get("/api/me/today").status_code in (401, 403)

def test_old_databases_get_the_activity_table(tmp_path):
    from sqlalchemy import create_engine, inspect
    e = create_engine(f"sqlite:///{tmp_path}/o.db"); main.Base.metadata.create_all(e)
    assert "activity_days" in inspect(e).get_table_names()
