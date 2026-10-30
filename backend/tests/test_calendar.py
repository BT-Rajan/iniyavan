# The calendar: events people add (for everyone, a program, a term, a course, or one person) beside what Zigora already knows (deadlines,
# study sessions, days studied, results, Pro ending); who may add what; a parent's view of a child; the private link a phone subscribes to;
# and reminders in the notifications.
import datetime as dt
import main
from main import Session_, User, Program, Semester, Course, Unit, Topic, Quiz, Attempt, Routine, DaySession, ActivityDay, GuardianLink, CalendarEvent, hp

def world(env):
    """B.E. Civil semester 1 with a course the faculty member owns, a topic due in two days, and the student placed there with a routine,
    a day studied, a quiz result; a parent following them; another student elsewhere."""
    now = dt.datetime.utcnow(); today = main.local_day(now)
    with Session_() as s:
        fac = s.query(User).filter_by(email="fac@x.com").one(); stu = s.query(User).filter_by(email="stu@x.com").one()
        p = Program(name="B.E. Civil", pattern="semester"); other = Program(name="B.Sc.", pattern="semester"); s.add_all([p, other]); s.flush()
        sem = Semester(name="Semester 1", program_id=p.id, semester_no=1); s.add(sem); s.flush()
        c = Course(name="Chemistry", program_id=p.id, semester_id=sem.id, faculty_owner_id=fac.id); c2 = Course(name="Elsewhere", program_id=other.id); s.add_all([c, c2]); s.flush()
        un = Unit(name="Water", course_id=c.id, position=0); s.add(un); s.flush()
        t = Topic(title="Hardness", unit_id=un.id, course_id=c.id, content="x", published=True, position=0, learning_due_at=main.day_start(today + dt.timedelta(days=2)) + dt.timedelta(hours=10))
        q = Quiz(unit_id=un.id, course_id=c.id, title="Water quiz", published=True); s.add_all([t, q]); s.flush()
        stu.program_id, stu.semester = p.id, 1
        s.add_all([Routine(user_id=stu.id, days="1111111", minutes=30, at="19:30", started_at=now - dt.timedelta(days=3)), DaySession(user_id=stu.id, day=today - dt.timedelta(days=1), items="[]", done_at=now - dt.timedelta(days=1)),
                   ActivityDay(user_id=stu.id, day=today - dt.timedelta(days=1), reads=2), Attempt(quiz_id=q.id, user_id=stu.id, score=2, total=2, percent=100, at=now - dt.timedelta(hours=1))])
        mum = User(name="Amma", email="mum@x.com", pw=hp("pw"), role="guardian", relation="parent", self_registered=True, level="college")
        far = User(name="Far Away", email="far@x.com", pw=hp("pw"), role="student", program_id=other.id, semester=1); s.add_all([mum, far]); s.flush()
        s.add(GuardianLink(guardian_id=mum.id, student_id=stu.id, status="active")); s.commit()
        return {"today": today, "program": p.id, "other": other.id, "course": c.id, "c2": c2.id, "topic": t.id, "stu": stu.id, "far": far.id}
def cal(env, h, d0, d1, **q): return env.c.get("/api/calendar", headers=h, params={"start": d0.isoformat(), "end": d1.isoformat(), **q})
def ev(env, h, **b): return env.c.post("/api/calendar/events", headers=h, json={"title": "Exam", "kind": "exam", "day": b.pop("day").isoformat(), **b})

def test_events_reach_exactly_the_people_they_are_for(env):
    w = world(env); d = w["today"] + dt.timedelta(days=5)
    assert ev(env, env.admin, title="Holiday", kind="holiday", day=d, scope="all").status_code == 200
    assert ev(env, env.admin, title="Civil fair", kind="event", day=d, scope="program", program_id=w["program"]).status_code == 200
    assert ev(env, env.admin, title="Sem 1 exams", day=d, end_day=(d + dt.timedelta(days=4)).isoformat(), scope="semester", program_id=w["program"], semester=1).status_code == 200
    assert ev(env, env.fac, title="Chem test", kind="test", day=d, at="09:30", scope="course", course_id=w["course"]).status_code == 200
    assert ev(env, env.admin, title="Other course", day=d, scope="course", course_id=w["c2"]).status_code == 200
    assert ev(env, env.stu, title="Revise", kind="reminder", day=d).status_code == 200  # a student's own
    mine = {i["title"] for i in cal(env, env.stu, w["today"], d + dt.timedelta(days=10)).json()["items"] if i["id"].startswith("ev:")}
    assert mine == {"Holiday", "Civil fair", "Sem 1 exams", "Chem test", "Revise"}
    far = env.login("far@x.com"); assert {i["title"] for i in cal(env, far, d, d).json()["items"]} == {"Holiday", "Other course"}  # their own program's course, not Civil's
    later = cal(env, env.stu, d + dt.timedelta(days=3), d + dt.timedelta(days=3)).json()["items"]; assert "Sem 1 exams" in {i["title"] for i in later}  # several days
    chem = next(i for i in cal(env, env.stu, d, d).json()["items"] if i["title"] == "Chem test"); assert chem["at"] == "09:30" and chem["sub"] == "Chemistry" and chem["event"]["can_edit"] is False

def test_who_may_add_and_change_what(env):
    w = world(env); d = w["today"] + dt.timedelta(days=1)
    assert ev(env, env.stu, day=d, scope="all").status_code == 403 and ev(env, env.stu, day=d, user_id=w["far"]).status_code == 403
    assert ev(env, env.fac, day=d, scope="course", course_id=w["c2"]).status_code == 403 and ev(env, env.fac, day=d, scope="program", program_id=w["program"]).status_code == 403
    mum = env.login("mum@x.com"); assert ev(env, mum, title="Dentist", kind="reminder", day=d, user_id=w["stu"]).status_code == 200  # for their child
    assert ev(env, mum, day=d, user_id=w["far"]).status_code == 403
    for bad in ({"title": " "}, {"kind": "party"}, {"at": "25:00"}, {"end_day": (d - dt.timedelta(days=1)).isoformat()}, {"end_day": (d + dt.timedelta(days=90)).isoformat()}, {"scope": "galaxy"}):
        assert ev(env, env.stu, day=d, **bad).status_code == 400, bad
    assert env.c.get("/api/calendar", headers=env.stu, params={"start": "2026-01-01", "end": "2026-12-31"}).status_code == 400  # one range at a time
    eid = ev(env, env.fac, title="Chem test", day=d, scope="course", course_id=w["course"]).json()["event"]["id"]
    assert env.c.put(f"/api/calendar/events/{eid}", headers=env.stu, json={"title": "Cancelled!", "day": d.isoformat(), "scope": "user"}).status_code == 403
    r = env.c.put(f"/api/calendar/events/{eid}", headers=env.fac, json={"title": "Chem test (moved)", "kind": "test", "day": (d + dt.timedelta(days=1)).isoformat(), "scope": "course", "course_id": w["course"]})
    assert r.status_code == 200 and r.json()["date"] == (d + dt.timedelta(days=1)).isoformat()
    assert env.c.delete(f"/api/calendar/events/{eid}", headers=mum).status_code == 403 and env.c.delete(f"/api/calendar/events/{eid}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.query(CalendarEvent).filter_by(id=eid).first() is None

def test_what_zigora_knows_is_on_the_calendar_too(env):
    w = world(env); t = w["today"]
    items = cal(env, env.stu, t - dt.timedelta(days=3), t + dt.timedelta(days=3)).json()["items"]; by = lambda k: [i for i in items if i["kind"] == k]
    due = by("deadline"); assert [(i["title"], i["sub"], i["date"], i["state"]) for i in due] == [("Hardness", "Chemistry", (t + dt.timedelta(days=2)).isoformat(), "planned")]
    ses = {i["date"]: i["state"] for i in by("session")}
    assert ses[(t - dt.timedelta(days=1)).isoformat()] == "done" and ses[(t - dt.timedelta(days=2)).isoformat()] == "missed" and ses[t.isoformat()] == "planned"
    assert (t - dt.timedelta(days=4)).isoformat() not in ses and by("session")[0]["at"] == "19:30"  # nothing before the routine began
    assert [i["date"] for i in by("studied")] == [(t - dt.timedelta(days=1)).isoformat()]
    assert [(i["title"], i["sub"]) for i in by("result")] == [("Water quiz", "100%")]
    with Session_() as s: s.query(User).filter_by(id=w["stu"]).update({"pro_until": main.day_start(t + dt.timedelta(days=3)) + dt.timedelta(hours=9)}); s.commit()
    assert "Pro ends" in {i["title"] for i in cal(env, env.stu, t, t + dt.timedelta(days=3)).json()["items"]}
    assert cal(env, env.admin, t, t).json()["items"] == []  # staff see the events they manage, nobody's study plan

def test_a_parent_sees_their_childs_calendar_and_no_one_elses(env):
    w = world(env); t = w["today"]; mum = env.login("mum@x.com")
    r = cal(env, mum, t, t + dt.timedelta(days=3)).json(); assert r["students"] == [{"id": w["stu"], "name": "stu@x.com"}] and r["items"] == []
    ev(env, mum, title="Buy a calculator", kind="reminder", day=t + dt.timedelta(days=1))  # the parent's own
    kid = cal(env, mum, t, t + dt.timedelta(days=3), student=w["stu"]).json()
    assert kid["student"]["id"] == w["stu"] and "Hardness" in {i["title"] for i in kid["items"]} and "Buy a calculator" in {i["title"] for i in kid["items"]}
    assert cal(env, mum, t, t, student=w["far"]).status_code == 404 and cal(env, env.stu, t, t, student=w["far"]).status_code == 404

def test_the_subscribe_link_gives_a_calendar_a_phone_understands(env):
    w = world(env); d = w["today"] + dt.timedelta(days=4)
    ev(env, env.fac, title="Chem test; part 1, theory", kind="test", day=d, at="09:30", scope="course", course_id=w["course"], notes="Bring a pen\nand a pencil")
    ev(env, env.admin, title="Pongal", kind="holiday", day=d, end_day=(d + dt.timedelta(days=2)).isoformat(), scope="all")
    assert env.c.get("/api/calendar/link", headers=env.stu).json() == {"on": False}
    path = env.c.post("/api/calendar/link", headers=env.stu).json()["path"]; r = env.c.get(path)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar") and r.text.startswith("BEGIN:VCALENDAR\r\n") and r.text.endswith("END:VCALENDAR\r\n")
    body = r.text.replace("\r\n ", "")  # unfold
    assert "SUMMARY:Chem test\\; part 1\\, theory" in body and "DESCRIPTION:Chemistry · Bring a pen\\nand a pencil" in body
    t0 = dt.datetime.combine(d, dt.time(9, 30)) - dt.timedelta(minutes=main.DAY_OFFSET); assert f"DTSTART:{t0:%Y%m%dT%H%M%SZ}" in body  # the local clock, in UTC
    assert f"DTSTART;VALUE=DATE:{d:%Y%m%d}" in body and f"DTEND;VALUE=DATE:{d + dt.timedelta(days=3):%Y%m%d}" in body  # Pongal, three days
    assert "SUMMARY:Hardness" in body and "SUMMARY:Water quiz" not in body  # deadlines go to the phone; results don't
    assert all(len(x.encode()) <= 75 for x in r.text.split("\r\n"))
    with Session_() as s: assert s.query(User).filter_by(id=w["stu"]).one().cal_token not in path  # only a hash is kept
    new = env.c.post("/api/calendar/link", headers=env.stu).json()["path"]; assert env.c.get(path).status_code == 404 and env.c.get(new).status_code == 200  # a new link ends the old
    env.c.post("/api/calendar/link/off", headers=env.stu); assert env.c.get(new).status_code == 404 and env.c.get("/api/calendar/feed/short.ics").status_code == 404
    mum = env.login("mum@x.com"); ev(env, mum, title="Dentist", kind="reminder", day=d, user_id=w["stu"])
    feed = env.c.get(env.c.post("/api/calendar/link", headers=mum).json()["path"]).text.replace("\r\n ", "")
    assert "SUMMARY:stu@x.com: Chem test" in feed and feed.count("Dentist") == 1 and "SUMMARY:stu@x.com: Dentist" in feed  # a parent's: each child's, named

def test_events_today_and_tomorrow_are_reminders(env):
    w = world(env); t = w["today"]
    ev(env, env.fac, title="Chem test", kind="test", day=t + dt.timedelta(days=1), at="09:30", scope="course", course_id=w["course"])
    ev(env, env.admin, title="Far later", day=t + dt.timedelta(days=9), scope="all")
    notes = {n["text"]: n for n in env.c.get("/api/me/notifications", headers=env.stu).json()["items"]}
    assert notes["Chem test"]["sub"] == "Tomorrow · 09:30" and notes["Chem test"]["unread"] and "Far later" not in notes
    mum = env.login("mum@x.com"); assert "stu@x.com: Chem test" in {n["text"] for n in env.c.get("/api/me/notifications", headers=mum).json()["items"]}

def test_the_migration_adds_the_calendar_once(env):
    main.upgrade_schema(); main.upgrade_schema()
    assert main.applied_migrations().count("0031_calendar") == 1 and "calendar_events" in main.inspect(main.engine).get_table_names()
    assert [c["name"] for c in main.inspect(main.engine).get_columns("users")].count("cal_token") == 1
