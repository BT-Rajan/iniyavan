# A student's dashboard: what to do next (most useful first, each with one action) and this week at a glance; extra signals beyond the ranked next
# steps: a streak at risk on a routine day, an exam coming with weak topics, MCQ topics to practise again, the free AI allowance running low.
import datetime as dt
import main
from main import Session_, ActivityDay, Routine, CalendarEvent, LiteUse, Setting, User
from tests.test_quiz_reports import setup, make_quiz
from tests.test_insights import two_topic_quiz, take, me_id

def dash(env, h=None): return env.c.get("/api/me/dashboard", headers=h or env.stu).json()

def test_next_steps_an_exam_with_weak_topics_and_this_week(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit); sid = me_id("stu@x.com"); today = main.local_day(dt.datetime.utcnow())
    take(env, env.stu, q, [0, 0, 1, 1, 1])  # Boilers 0 of 3: a weak topic, and the quiz is below its pass mark
    with Session_() as s: s.add(CalendarEvent(title="Chemistry test", kind="test", day=today + dt.timedelta(days=2), scope="user", user_id=sid)); s.commit()
    d = dash(env); by = {x["key"]: x for x in d["items"]}
    assert by["exam"]["vars"] == {"title": "Chemistry test", "date": (today + dt.timedelta(days=2)).isoformat(), "n": 1} and by["exam"]["action"] == "progress" and by["exam"]["level"] == "now"
    focus = [x for x in d["items"] if x["key"].startswith("focus_")]; assert focus and all(x["title"] and x["text"] for x in focus)
    assert any(x["action"] in ("topic", "quiz") and x["target"] for x in focus) and len(d["items"]) <= 5
    assert len(d["week"]) == 7 and d["week"][-1] is True and d["routine"] is False  # taking the quiz today counts as studying

def test_a_streak_at_risk_and_the_free_ai_running_low(env, monkeypatch):
    i, unit = setup(env); sid = me_id("stu@x.com"); today = main.local_day(dt.datetime.utcnow())
    with Session_() as s:
        for n in (1, 2): s.add(ActivityDay(user_id=sid, day=today - dt.timedelta(days=n), reads=1))  # a 2-day streak, nothing yet today
        s.add(Routine(user_id=sid, days="1111111", minutes=20, at="00:00")); u = s.get(User, sid); u.self_registered = True
        s.merge(Setting(k="lite_searches", v="10")); s.add(LiteUse(user_id=sid, day=today, searches=9, minutes=0, last_min=0)); s.commit()
    by = {x["key"]: x for x in dash(env)["items"]}
    assert by["streak"]["vars"] == {"n": 2} and by["streak"]["level"] == "now"
    assert by["lite"]["vars"] == {"used": 9, "limit": 10} and by["lite"]["action"] == "plan"
    assert env.c.get("/api/me/dashboard", headers=env.fac).status_code == 403
