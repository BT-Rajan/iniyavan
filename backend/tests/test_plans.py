# Plans for self-registered people: lite (a free daily allowance on the college's key), their own key, or pro (made so by an admin until a date)
import main
from main import Session_, Setting, User, MoreRequest
from tests.test_search import ai_env, ask
from tests.test_access import ids

def lite_person(env, email="lite@x.com"):
    with Session_() as s: s.add(User(name="Lite Learner", email=email, pw=main.hp("pw1234567"), role="student", self_registered=True)); s.commit()
    with Session_() as s: uid = s.query(User).filter_by(email=email).one().id
    return env.login(email, "pw1234567"), uid

def set_limits(searches, minutes):
    with Session_() as s: s.merge(Setting(k="lite_searches", v=str(searches))); s.merge(Setting(k="lite_minutes", v=str(minutes))); s.commit()

def test_lite_people_get_a_few_free_searches_a_day_then_are_told_how_to_get_more(env, monkeypatch):
    ai_env(env, monkeypatch); h, uid = lite_person(env); set_limits(2, 20)
    p = env.c.get("/api/me/plan", headers=h).json(); assert p["plan"] == "lite" and p["searches_limit"] == 2 and p["searches_used"] == 0 and p["asked"] is False
    assert ask(env, "first question", h=h).status_code == 200 and ask(env, "second question", h=h).status_code == 200
    r = ask(env, "third question", h=h); assert r.status_code == 429 and "2 free AI searches" in r.json()["detail"] and "own DeepSeek key" in r.json()["detail"]
    assert env.c.get("/api/me/plan", headers=h).json()["searches_used"] == 2
    assert ask(env, "third question").status_code == 200  # a student the college added is not limited by this
    assert env.c.get("/api/me/plan", headers=env.stu).json() == {"plan": "college", "pro_until": None, "own_key": False}

def test_lite_learning_time_counts_each_minute_once_and_stops_new_ai_answers(env, monkeypatch):
    ai_env(env, monkeypatch); h, uid = lite_person(env); set_limits(10, 2); t = ids()["topic"]["Water hardness"]
    from tests.test_access import enrol
    with Session_() as s: u = s.get(User, uid); stu = s.query(User).filter_by(email="stu@x.com").one(); u.program_id, u.semester = stu.program_id, stu.semester; s.commit()
    clock = [1_000_000_000.0]; monkeypatch.setattr(main.time, "time", lambda: clock[0])
    for _ in range(3): env.c.post("/api/me/plan/tick", headers=h)  # three heartbeats in the same minute
    assert env.c.get("/api/me/plan", headers=h).json()["minutes_used"] == 1
    clock[0] += 61; assert env.c.get(f"/api/topics/{t}/ai/explain", headers=h).status_code == 200  # an AI answer counts its minute too
    assert env.c.get("/api/me/plan", headers=h).json()["minutes_used"] == 2
    clock[0] += 61; r = env.c.get(f"/api/topics/{t}/ai/answer", headers=h)
    assert r.status_code == 429 and "2 free minutes" in r.json()["detail"]
    assert env.c.get(f"/api/topics/{t}/ai/explain", headers=h).status_code == 200  # a saved answer still opens: it costs nothing
    env.c.post("/api/me/plan/tick", headers=env.stu)
    assert env.c.get("/api/me/plan", headers=env.stu).json()["plan"] == "college"

def test_asking_for_more_and_an_admin_making_someone_pro_until_a_date(env, monkeypatch):
    ai_env(env, monkeypatch); h, uid = lite_person(env); set_limits(1, 20)
    mails = []; monkeypatch.setattr(main, "mail_on", lambda s=None: True); monkeypatch.setattr(main, "send_mail", lambda to, subj, body, **k: mails.append((to, subj, body)))
    assert env.c.post("/api/me/plan/request", headers=env.stu, json={}).status_code == 400  # college students have no limit to lift
    r = env.c.post("/api/me/plan/request", headers=h, json={"note": "  Exams next week  "}); assert r.status_code == 200
    assert env.c.post("/api/me/plan/request", headers=h, json={}).json()["message"] == "Your request is with your admin."  # one open request at a time
    assert env.c.get("/api/me/plan", headers=h).json()["asked"] is True
    att = {a["kind"]: a for a in env.c.get("/api/overview", headers=env.admin).json()["attention"]}; assert att["more_ai"]["count"] == 1
    lst = env.c.get("/api/admin/users?plan=asked", headers=env.admin).json(); assert lst["total"] == 1 and lst["items"][0]["asked"] and lst["items"][0]["plan"] == "lite"
    d = env.c.get(f"/api/admin/users/{uid}", headers=env.admin).json(); assert d["asked"]["note"] == "Exams next week"
    with Session_() as s: stu_id = s.query(User).filter_by(email="stu@x.com").one().id
    assert env.c.put(f"/api/admin/users/{stu_id}/pro", headers=env.admin, json={"days": 30}).status_code == 400  # only self-registered people have plans
    assert env.c.put(f"/api/admin/users/{uid}/pro", headers=env.stu, json={"days": 30}).status_code == 403
    for bad in ({"days": 0}, {"until": "2001-01-01"}, {"until": "soon"}): assert env.c.put(f"/api/admin/users/{uid}/pro", headers=env.admin, json=bad).status_code == 400
    r = env.c.put(f"/api/admin/users/{uid}/pro", headers=env.admin, json={"until": "2099-12-31"}); assert r.status_code == 200 and r.json()["plan"] == "pro" and r.json()["pro_until"].startswith("2099-12-31")
    assert mails and mails[-1][0] == "lite@x.com" and "31 December 2099" in mails[-1][2]
    assert env.c.get("/api/admin/users?plan=asked", headers=env.admin).json()["total"] == 0 and env.c.get("/api/admin/users?plan=pro", headers=env.admin).json()["total"] == 1
    assert all(ask(env, f"pro question {n}", h=h).status_code == 200 for n in range(3))  # no lite limit now
    assert env.c.get("/api/me/profile", headers=h).json()["ai"]["plan"] == "pro"
    assert env.c.put(f"/api/admin/users/{uid}/pro", headers=env.admin, json={"end": True}).json()["plan"] == "lite"
    with Session_() as s: u = s.get(User, uid); u.pro_until = main.dt.datetime.utcnow() - main.dt.timedelta(minutes=1); s.commit()
    assert env.c.get("/api/me/plan", headers=h).json()["plan"] == "lite"  # pro ends by itself after its date

def test_the_admin_sets_the_free_allowance(env):
    assert env.c.get("/api/admin/settings", headers=env.admin).json()["lite"] == {"searches": 10, "minutes": 20}
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"lite_searches": 15, "lite_minutes": 30}).status_code == 200
    assert env.c.get("/api/admin/settings", headers=env.admin).json()["lite"] == {"searches": 15, "minutes": 30}
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"lite_minutes": -1}).status_code == 400

def test_a_saved_answer_or_a_failed_ai_call_uses_no_free_search(env, monkeypatch):
    from tests.test_ai import FakeClient
    ai_env(env, monkeypatch); h, uid = lite_person(env); set_limits(2, 20)
    assert ask(env, "What is hard water?").status_code == 200  # a college student's question: now saved for everyone
    assert ask(env, "what is HARD water?", h=h).json()["cached"] is True
    assert env.c.get("/api/me/plan", headers=h).json()["searches_used"] == 0  # a saved answer costs nothing
    FakeClient.mode = "boom"; assert ask(env, "Why does soap not lather?", h=h).status_code >= 500
    FakeClient.mode = "500"; assert ask(env, "Why does soap not lather?", h=h).status_code >= 500
    assert env.c.get("/api/me/plan", headers=h).json()["searches_used"] == 0  # nor does an AI call that failed
    FakeClient.mode = "ok"; assert ask(env, "Why does soap not lather?", h=h).json()["cached"] is False
    assert env.c.get("/api/me/plan", headers=h).json()["searches_used"] == 1
