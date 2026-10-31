# A parent's or teacher's dashboard: what needs them for each child, most urgent first, each with one action, and a short card per child.
import datetime as dt
import main
from main import Session_, ActivityDay, Routine, Attempt, CalendarEvent, Quiz, User
from tests.test_school_ai import setup as school, set_key, login

def dash(env, who="mum@x.com"): return env.c.get("/api/guardian/dashboard", headers=login(env, who)).json()

def test_a_quiet_child_an_exam_a_score_drop_and_ai_off_need_the_parent(env):
    i = school(); kid = i["Kavin"]; today = main.local_day(dt.datetime.utcnow()); now = dt.datetime.utcnow()
    with Session_() as s:
        s.add(ActivityDay(user_id=kid, day=today - dt.timedelta(days=4), reads=2))  # last studied four days ago
        x = s.get(User, kid); s.add(CalendarEvent(title="Science test", kind="test", day=today + dt.timedelta(days=2), scope="user", user_id=kid))
        q = Quiz(title="Water", pass_percent=50, published=True); s.add(q); s.flush()
        for k, p in enumerate((80, 85, 90, 60)): s.add(Attempt(quiz_id=q.id, user_id=kid, score=p, total=100, percent=p, at=now - dt.timedelta(days=10 - k)))  # usual 85, latest 60
        s.commit()
    d = dash(env); by = {x["key"]: x for x in d["items"]}
    assert by["quiet"]["vars"] == {"name": "Kavin", "days": 4} and by["quiet"]["level"] == "now" and by["quiet"]["action"] == "progress" and by["quiet"]["student_id"] == kid
    assert by["exam"]["vars"]["title"] == "Science test" and by["exam"]["level"] == "now"
    assert by["score_drop"]["vars"]["p"] == 60 and by["score_drop"]["vars"]["usual"] == 85
    assert by["ai_off"]["action"] == "key" and "no_routine" in by
    lv = [x["level"] for x in d["items"]]; assert lv == sorted(lv, key=main.URGENCY.get)
    c = d["students"][0]; assert c["name"] == "Kavin" and len(c["week"]) == 7 and c["last_studied"] == (today - dt.timedelta(days=4)).isoformat() and c["routine"] is False

def test_a_child_on_track_needs_nothing_and_only_guardians_see_it(env):
    i = school(); kid = i["Kavin"]; set_key(i["Mum"], "sk-parent-key-2222222222222"); today = main.local_day(dt.datetime.utcnow())
    with Session_() as s:
        for n in range(3): s.add(ActivityDay(user_id=kid, day=today - dt.timedelta(days=n), reads=1))
        s.add(Routine(user_id=kid, days="1111111", minutes=30)); s.commit()
    d = dash(env); assert d["items"] == [] and d["students"][0]["streak"] >= 3 and d["students"][0]["week"][-1] is True
    assert env.c.get("/api/guardian/dashboard", headers=login(env, "uni@x.com")).status_code == 403
    t = dash(env, "t@x.com"); assert [c["name"] for c in t["students"]] == ["Kavin"] and "ai_off" not in [x["key"] for x in t["items"]]  # the parent's key covers him
