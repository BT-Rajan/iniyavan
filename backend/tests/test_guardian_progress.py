# What a parent or teacher sees of a student they look after: per course, their scores with strong and weak topics, how regularly they study
# (the last four weeks, streak, routine) and their MCQ practice results. Never their notes, highlights or answers.
import datetime as dt
import main
from main import Session_, ActivityDay, Routine, Progress, User
from tests.test_insights import two_topic_quiz, take, me_id
from tests.test_quiz_reports import setup
from tests.test_guardian import guardian, link

def test_a_parent_sees_scores_strong_and_weak_topics_and_study_activity(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit); sid = me_id("stu@x.com")
    take(env, env.stu, q, [0, 0, 1, 1, 0])  # Water 2 of 2, Boilers 1 of 3
    today = main.local_day(dt.datetime.utcnow())
    with Session_() as s:
        for n in (0, 1, 2, 10, 40): s.merge(ActivityDay(user_id=sid, day=today - dt.timedelta(days=n), reads=1))
        s.add(Routine(user_id=sid, days="1111100", minutes=45, at="19:00")); s.add(Progress(user_id=sid, topic_id=t["Water"], reads=2, completed_at=dt.datetime.utcnow()))
        s.commit()
    g = guardian("mum@x.com"); link(g, sid); h = env.login("mum@x.com")
    d = env.c.get(f"/api/guardian/students/{sid}/progress", headers=h).json()
    sc = d["scores"]; assert sc["quizzes_taken"] == 1 and [c["percent"] for c in sc["courses"]] == [60]
    assert [(a["title"], a["percent"]) for a in sc["strong"]] == [("Water", 100)] and [a["title"] for a in sc["needs_study"]] == ["Boilers"]
    a = d["activity"]; assert a["streak"] >= 3 and a["active_today"] and a["active_days_week"] == 3 and a["active_days_28"] == 4 and a["completed_this_week"] == 1
    assert len(a["days"]) == 28 and a["days"][-1] == {"date": today.isoformat(), "active": True} and a["routine"] == {"days": "1111100", "minutes": 45, "at": "19:00"}
    assert d["mcq"] == {"sets": 0, "average": None, "last_at": None, "revisit": []}
    assert "results" not in str(d) and "answers" not in d  # their scores, never their answers

def test_only_linked_guardians_who_were_accepted_see_it(env):
    i, unit = setup(env); sid = me_id("stu@x.com")
    other = guardian("other@x.com"); h = env.login("other@x.com")
    assert env.c.get(f"/api/guardian/students/{sid}/progress", headers=h).status_code in (403, 404)
    link(guardian("t@x.com", "teacher"), sid, status="invited")
    assert env.c.get(f"/api/guardian/students/{sid}/progress", headers=env.login("t@x.com")).status_code == 403  # until the student accepts
    assert env.c.get(f"/api/guardian/students/{sid}/progress", headers=env.stu).status_code == 403
