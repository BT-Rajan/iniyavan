# The admin's dashboard lists only what needs doing, most urgent first, each with its action; it warns ahead (an allowance that will run out
# this month, Pro ending this week) and says "all clear" with the next date when nothing does.
import datetime as dt
import main
from main import Session_, Setting, User, AIEgress, MoreRequest, AIFlag, Topic, CalendarEvent, hp
from tests.test_quiz_reports import setup

def dash(env): return env.c.get("/api/admin/dashboard", headers=env.admin).json()
def keys(d): return [x["key"] for x in d["items"]]

def test_nothing_to_do_says_all_clear_with_the_next_date(env):
    setup(env); today = main.local_day(dt.datetime.utcnow())
    with Session_() as s:
        s.merge(Setting(k="deepseek_key", v="sk-college-0000000000000")); s.merge(Setting(k="mail_gmail", v="z@gmail.com")); s.merge(Setting(k="mail_gmail_pw", v=main.seal("abcdabcdabcdabcd")))
        s.add(CalendarEvent(title="Semester exams", kind="exam", day=today + dt.timedelta(days=9), scope="all")); s.commit()
    d = dash(env)
    assert [x["key"] for x in d["items"] if x["level"] == "now"] == [] and "ai_off" not in keys(d) and d["next"] == {"title": "Semester exams", "date": (today + dt.timedelta(days=9)).isoformat()}

def test_urgent_things_come_first_each_with_its_action(env):
    i, unit = setup(env); now = dt.datetime.utcnow(); sid = env.c.get("/api/me", headers=env.stu).json()["id"]
    with Session_() as s:
        s.merge(Setting(k="deepseek_key", v="sk-college-0000000000000")); s.merge(Setting(k="budget_deepseek", v="1000000")); s.merge(Setting(k="mail_fails", v="4"))
        start = main.month_start(); elapsed = max((now - start).days, 1)
        s.add(AIEgress(user_id=sid, kind="search", tokens=int(1000000 * elapsed / 20), provider="deepseek", at=start + dt.timedelta(hours=1)))  # on pace to run out around day 20
        for _ in range(3): s.add(AIEgress(user_id=sid, kind="search", tokens=0, ok=False, provider="deepseek", at=now))  # the last three got no answer
        p1 = User(name="Pro ending", email="p1@x.com", pw=hp("pw"), role="student", self_registered=True, pro_until=now + dt.timedelta(days=3))
        p2 = User(name="Pro later", email="p2@x.com", pw=hp("pw"), role="student", self_registered=True, pro_until=now + dt.timedelta(days=30))
        s.add_all([p1, p2]); s.flush(); s.add(MoreRequest(user_id=p2.id))
        t = s.query(Topic).filter_by(unit_id=unit).first(); t.published = False; t.learning_due_at = now + dt.timedelta(days=2)
        s.add(AIFlag(user_id=sid, topic_id=t.id, source="topic", kind="explain", excerpt="x", at=now - dt.timedelta(days=5))); s.commit()
    d = dash(env); by = {x["key"]: x for x in d["items"]}
    assert {"ai_failing", "more_ai", "pro_ending", "flags", "drafts_due", "mail_failing"} <= set(by)
    if now.day < 18: assert by["allowance_soon"]["action"] == "settings" and by["allowance_soon"]["target"] == {"tab": "ai"}  # early enough in the month to be ahead of it
    assert by["ai_failing"]["action"] == "test_ai" and by["ai_failing"]["vars"]["name"] == "DeepSeek"
    assert by["pro_ending"]["vars"]["n"] == 1 and by["pro_ending"]["target"] == {"plan": "pro_ending"} and by["more_ai"]["target"] == {"plan": "asked"}
    assert by["flags"]["level"] == "now" and by["flags"]["vars"]["days"] == 5 and by["drafts_due"]["target"] == {"kind": "drafts"} and by["mail_failing"]["target"] == {"tab": "mail"}
    lv = [x["level"] for x in d["items"]]; assert lv == sorted(lv, key=main.URGENCY.get)  # most urgent first
    names = [u["name"] for u in env.c.get("/api/admin/users?plan=pro_ending", headers=env.admin).json()["items"]]; assert names == ["Pro ending"]

def test_an_allowance_already_used_up_and_ai_off_are_urgent_and_only_admins_see_this(env):
    setup(env); sid = env.c.get("/api/me", headers=env.stu).json()["id"]
    with Session_() as s:
        s.merge(Setting(k="budget_deepseek", v="10")); s.add(AIEgress(user_id=sid, kind="search", tokens=50, provider="deepseek", at=dt.datetime.utcnow())); s.commit()
    by = {x["key"]: x for x in dash(env)["items"]}
    assert by["allowance_out"]["level"] == "now" and by["ai_off"]["level"] == "now" and by["mail_off"]["level"] == "later"
    for h in (env.fac, env.stu): assert env.c.get("/api/admin/dashboard", headers=h).status_code == 403

def test_the_graphs_and_where_each_one_leads(env):
    i, unit = setup(env); now = dt.datetime.utcnow(); today = main.local_day(now); sid = env.c.get("/api/me", headers=env.stu).json()["id"]
    with Session_() as s:
        s.add(main.ActivityDay(user_id=sid, day=today - dt.timedelta(days=2), reads=3))
        s.add(AIEgress(user_id=sid, kind="search", tokens=500, provider="deepseek", at=now)); s.add(AIEgress(user_id=sid, kind="vision", tokens=200, at=now))  # an old row: a photo is Claude
        s.add(AIEgress(user_id=sid, kind="search", tokens=999, provider="openai", own=True, at=now))  # their own key: not the college's
        s.add(User(name="Lite", email="lite@x.com", pw=hp("pw"), role="student", self_registered=True)); s.commit()
    c = env.c.get("/api/admin/charts?days=14", headers=env.admin).json()
    assert len(c["activity"]) == 14 and c["activity"][-3] == {"date": (today - dt.timedelta(days=2)).isoformat(), "students": 1} and c["activity"][-1]["students"] == 0
    assert [p["id"] for p in c["ai"]["providers"]] == ["deepseek", "claude"] and c["ai"]["days"][-1]["tokens"] == {"deepseek": 500, "claude": 200}
    plans = {p["plan"]: p["people"] for p in c["plans"]}; assert plans["lite"] == 1 and plans["college"] >= 1
    assert all(set(x) >= {"course_id", "course", "completion", "students"} for x in c["courses"])
    lst = env.c.get(f"/api/overview/list?kind=active_day&date={(today - dt.timedelta(days=2)).isoformat()}&limit=10", headers=env.admin).json()  # a bar's students
    assert [x["title"] for x in lst["items"]] == [env.c.get("/api/me", headers=env.stu).json()["name"]]
    names = [x["name"] for x in env.c.get("/api/admin/users?plan=lite&limit=50", headers=env.admin).json()["items"]]; assert "Lite" in names
    assert "Lite" not in [x["name"] for x in env.c.get("/api/admin/users?plan=college&limit=50", headers=env.admin).json()["items"]]
    assert env.c.get("/api/admin/charts", headers=env.fac).status_code == 403 and env.c.get("/api/overview/list?kind=active_day&date=2026-01-01", headers=env.fac).status_code == 403
