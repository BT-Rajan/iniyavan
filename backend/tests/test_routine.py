"""Own-pace routine: study days and minutes, one fixed session a day, no pile-up after missed days, a streak that rests on rest days."""
import datetime as dt, json
import main
from main import Session_, User, Topic, DaySession, Routine, ActivityDay, StudyProgress
from tests.test_access import enrol, ids
from tests.test_material import SYLLABUS

ALL, NONE_TODAY = "1111111", None
def today(): return main.local_day(dt.datetime.utcnow())
def without_today(): d = list("1111111"); d[today().weekday()] = "0"; return "".join(d)
def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def setup(env):
    env.csv(SYLLABUS); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: i["t"] = {t.title: t.id for t in s.query(Topic)}
    return i
def routine(env, days=ALL, minutes=30, at=None, h=None): return env.c.put("/api/me/routine", headers=h or env.stu, json={"days": days, "minutes": minutes, "at": at})
def session(env): return env.c.get("/api/me/session", headers=env.stu).json()
def titles(v): return [x["title"] for x in v["session"]["items"]]
def due(env, i, title, when):
    tid = i["t"][title]; un = env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["unit_id"]
    assert env.c.put(f"/api/topics/{tid}", headers=env.admin, json={"title": title, "unit_id": un, "learning_due_at": when}).status_code == 200

def test_no_routine_and_validation(env):
    setup(env); assert session(env) == {"routine": None}
    for bad in ({"days": "0000000"}, {"days": "11111"}, {"days": "1111111", "minutes": 20}, {"days": "1111111", "at": "25:00"}, {"days": "1111111", "at": "7pm"}):
        assert env.c.put("/api/me/routine", headers=env.stu, json={"minutes": 30, **bad}).status_code == 400
    assert routine(env, h=env.fac).status_code == 403 and routine(env, h=env.admin).status_code == 403
    v = routine(env, minutes=45, at="19:30").json(); assert v["routine"] == {"days": ALL, "minutes": 45, "at": "19:30", "new_per_session": 2}
    assert v["next_day"] == main.next_study_day(ALL, today()) and v["next_day"]["in"] == 1  # the app shows this instead of working it out from the phone's clock

def test_session_picks_started_then_deadline_then_each_course_in_turn(env):
    i = setup(env); env.c.post(f"/api/topics/{i['t']['Rusting']}/read", headers=env.stu)  # started
    due(env, i, "Softening methods", (dt.datetime.utcnow() + dt.timedelta(days=2)).isoformat() + "Z")
    v = routine(env, minutes=60).json()  # 3 new topics a session
    assert titles(v) == ["Rusting", "Softening methods", "Fitting"]  # started; nearest deadline; then Workshop's turn before Chem's next
    assert all(x["done"] is False for x in v["session"]["items"]) and v["planned_today"] and v["plan"]["left"] == 5

def test_the_session_is_fixed_for_the_day_and_completes(env):
    i = setup(env); v = routine(env, minutes=30).json(); first = titles(v); assert len(first) == 1
    tid = v["session"]["items"][0]["id"]
    env.c.put(f"/api/topics/{tid}/complete", headers=env.stu)
    v = session(env); assert titles(v) == first and v["session"]["items"][0]["done"] and v["session"]["done"]  # no new topic appears today
    with Session_() as s:
        assert s.query(DaySession).one().done_at is not None
        s.query(DaySession).update({"day": today() - dt.timedelta(days=1)}); s.commit()  # a new day
    v = session(env); assert titles(v) != first and len(titles(v)) == 1 and not v["session"]["done"]

def test_missed_days_do_not_pile_up(env):
    i = setup(env); routine(env, minutes=30)
    with Session_() as s:
        s.add(ActivityDay(user_id=uid("stu@x.com"), day=today() - dt.timedelta(days=5), reads=1))
        s.query(Routine).update({"started_at": dt.datetime.utcnow() - dt.timedelta(days=10)}); s.commit()
    v = session(env); assert v["missed"] == 4 and len(v["session"]["items"]) == 1  # four study days missed, still one topic today

def test_days_before_the_routine_are_not_missed(env):
    setup(env); assert routine(env).json()["missed"] == 0  # a new routine: no "welcome back"
    with Session_() as s: s.query(Routine).update({"started_at": dt.datetime.utcnow() - dt.timedelta(days=3)}); s.commit()
    assert session(env)["missed"] == 2  # only the two study days after the day it was set up
    with Session_() as s: s.query(Routine).update({"started_at": None, "updated_at": dt.datetime.utcnow()}); s.commit()
    assert session(env)["missed"] == 0  # a routine from before the start date was kept falls back to when it was last changed

def test_rest_days_and_an_extra_session(env):
    setup(env); v = routine(env, days=without_today()).json()
    assert v["planned_today"] is False and v["session"] is None
    v = env.c.post("/api/me/session", headers=env.stu).json(); assert len(v["session"]["items"]) == 1  # studying anyway
    assert env.c.post("/api/me/routine/stop", headers=env.stu).status_code == 200 and session(env) == {"routine": None}
    assert env.c.post("/api/me/session", headers=env.stu).status_code == 400

def test_streak_skips_rest_days_but_breaks_on_a_missed_study_day():
    t = dt.date(2026, 10, 23)  # a Friday
    days = {t - dt.timedelta(days=k): 1 for k in (0, 1, 4)}  # Fri, Thu, then Mon (Sat, Sun were before; Tue, Wed nothing)
    assert main.streak_of(days, t) == 2  # without a routine: calendar days
    assert main.streak_of(days, t, "1001100") == 3  # study days Mon, Thu, Fri: Tue and Wed are rest days
    assert main.streak_of(days, t, "1111100") == 2  # Wed was a study day and was missed
    assert main.streak_of({t - dt.timedelta(days=1): 1}, t, "1111111") == 1  # not yet studied today keeps it alive

def test_plan_says_when_it_ends_and_advises_when_deadlines_slip(env):
    i = setup(env)
    for title in ("Hardness of water", "Softening methods", "Rusting", "Galvanising"): due(env, i, title, (dt.datetime.utcnow() + dt.timedelta(days=1)).isoformat() + "Z")
    v = routine(env, days=without_today(), minutes=15).json(); p = v["plan"]
    assert p["left"] == 5 and p["late"] >= 3 and "advice" in p and p["finish"] > today().isoformat()
    v = routine(env, days=ALL, minutes=60).json(); assert v["plan"]["late"] < p["late"]

def test_review_set_is_part_of_the_session_until_done(env):
    setup(env)
    cid = env.c.post("/api/study/courses", headers=env.stu, json={"title": "Own"}).json()["id"]
    env.c.post(f"/api/study/courses/{cid}/text", headers=env.stu, json={"text": "# A\n\none\n\n# B\n\ntwo"})
    env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={"method": "headings"}); env.c.post(f"/api/study/courses/{cid}/finish", headers=env.stu, json={})
    with Session_() as s:
        tid = s.query(main.StudyTopic).filter_by(course_id=cid).first().id
        s.add(StudyProgress(user_id=uid("stu@x.com"), topic_id=tid, completed_at=dt.datetime.utcnow(), review_due=dt.datetime.utcnow() - dt.timedelta(hours=1))); s.commit()
    v = routine(env, minutes=30).json(); items = v["session"]["items"]
    assert items[-1]["kind"] == "review" and items[-1]["course_id"] == cid and items[-1]["done"] is False
    with Session_() as s: s.query(StudyProgress).update({"review_due": dt.datetime.utcnow() + dt.timedelta(days=3)}); s.commit()  # what a finished review does
    assert session(env)["session"]["items"][-1]["done"] is True

def test_changing_the_routine_redoes_an_untouched_session_and_deleted_topics_drop_out(env):
    i = setup(env); routine(env, minutes=15); assert len(titles(session(env))) == 1
    v = routine(env, minutes=60).json(); assert len(titles(v)) == 3  # nothing done yet: today follows the new routine
    gone = v["session"]["items"][0]["id"]; assert env.c.delete(f"/api/topics/{gone}", headers=env.admin).status_code == 200
    assert gone not in [x["id"] for x in session(env)["session"]["items"]]
    env.c.put(f"/api/topics/{v['session']['items'][1]['id']}/complete", headers=env.stu)
    assert len(titles(routine(env, minutes=15).json())) == 2  # once something is done, today's session stays as it was

def test_home_streak_uses_the_routine(env):
    setup(env); me = uid("stu@x.com"); t = today()
    with Session_() as s:
        for k in (1, 3): s.add(ActivityDay(user_id=me, day=t - dt.timedelta(days=k), reads=1))
        s.commit()
    assert env.c.get("/api/me/today", headers=env.stu).json()["streak"] == 1
    rest = list("1111111"); rest[(t - dt.timedelta(days=2)).weekday()] = "0"; routine(env, days="".join(rest))
    assert env.c.get("/api/me/today", headers=env.stu).json()["streak"] == 2 and env.c.get("/api/study/me", headers=env.stu).json()["streak"] == 2

def test_next_study_day_is_counted_by_the_server_day():
    fri = dt.date(2026, 10, 23)  # a Friday
    assert main.next_study_day("1111111", fri) == {"in": 1, "weekday": 5}  # tomorrow, Saturday
    assert main.next_study_day("1000100", fri) == {"in": 3, "weekday": 0}  # Mon and Fri: the next is Monday
    assert main.next_study_day("0000100", fri) == {"in": 7, "weekday": 4}  # only Fridays: a week away
