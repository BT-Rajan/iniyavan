# A topic's diagram: the teacher turns it on (and may say what to draw), the AI draws an interactive HTML page once per topic and language,
# and only students past Lite can open it, in a sandbox where nothing can be loaded from anywhere
import datetime as dt
import main
from main import Session_, User, AICache
from tests.test_search import ai_env
from tests.test_access import ids
from tests.test_plans import lite_person

PAGE = ("<!doctype html><html><head><title>Hardness</title></head><body><h1>Hard water</h1><p>Tap a part.</p>"
        "<svg viewBox='0 0 100 50'><circle cx='20' cy='25' r='10' onclick='alert(1)'/></svg><script>var x=1</script></body></html>")

def drawn(monkeypatch, reply=PAGE):  # the stand-in AI: counts its calls and keeps what it was told
    seen = []
    async def fake(u, s, key, prompt, msg, max_tokens=None, kind="", topic_id=None, **k):
        seen.append((prompt, msg, kind)); return f"```html\n{reply}\n```", 1200
    monkeypatch.setattr(main, "ask_ai", fake); return seen

def turn_on(env, t, note=""):
    with Session_() as s: unit = s.get(main.Topic, t).unit_id
    r = env.c.put(f"/api/topics/{t}", headers=env.admin, json={"title": "Water hardness", "unit_id": unit, "diagram": True, "diagram_note": note})
    assert r.status_code == 200, r.text

def placed(env, uid):  # a self-registered person put in the same program and semester as the college's student
    with Session_() as s:
        u = s.get(User, uid); stu = s.query(User).filter_by(email="stu@x.com").one(); u.program_id, u.semester = stu.program_id, stu.semester; s.commit()

def test_no_diagram_until_the_teacher_turns_it_on(env, monkeypatch):
    ai_env(env, monkeypatch); seen = drawn(monkeypatch); t = ids()["topic"]["Water hardness"]
    assert env.c.get(f"/api/topics/{t}", headers=env.stu).json()["diagram"] is None
    assert env.c.get(f"/api/topics/{t}/diagram", headers=env.stu).status_code == 404 and seen == []
    assert env.c.get(f"/api/topics/{t}/ai/diagram", headers=env.stu).status_code == 404  # never through the general step door, which has no Pro check
    turn_on(env, t, "  A flow of the lime-soda process  ")
    full = env.c.get(f"/api/topics/{t}", headers=env.admin).json()
    assert full["diagram_on"] is True and full["diagram_note"] == "A flow of the lime-soda process" and full["diagram"] == "on"
    with Session_() as s: unit = s.get(main.Topic, t).unit_id
    assert env.c.put(f"/api/topics/{t}", headers=env.admin, json={"title": "Water hardness", "unit_id": unit, "diagram_note": "x" * 1001}).status_code == 400

def test_a_college_student_opens_it_and_everyone_shares_one_drawing(env, monkeypatch):
    ai_env(env, monkeypatch); seen = drawn(monkeypatch); t = ids()["topic"]["Water hardness"]; turn_on(env, t, "the lime-soda process")
    assert env.c.get(f"/api/topics/{t}", headers=env.stu).json()["diagram"] == "on"
    r = env.c.get(f"/api/topics/{t}/diagram", headers=env.stu); assert r.status_code == 200, r.text
    d = r.json(); assert d["cached"] is False and d["frame_url"].startswith(f"/api/topics/{t}/diagram/frame?t=")
    prompt, msg, kind = seen[0]; assert kind == "topic_diagram" and "inline SVG" in prompt and "The teacher asks for this diagram: the lime-soda process" in msg
    f = env.c.get(d["frame_url"]); assert f.status_code == 200 and f.text.startswith("<!doctype html>") and "```" not in f.text
    csp = f.headers["content-security-policy"]
    assert "sandbox allow-scripts;" in csp and "allow-same-origin" not in csp and "default-src 'none'" in csp  # its scripts run, but it can't reach anything
    assert env.c.get(f"/api/topics/{t}/diagram", headers=env.admin).json()["cached"] is True and len(seen) == 1  # drawn once, shared
    with Session_() as s: assert s.query(AICache).filter_by(topic_id=t, kind="diagram").count() == 1
    assert env.c.get(f"/api/topics/{t}/diagram/frame?t=nonsense").status_code == 401

def test_lite_sees_it_comes_with_pro_and_pro_opens_it(env, monkeypatch):
    ai_env(env, monkeypatch); seen = drawn(monkeypatch); t = ids()["topic"]["Water hardness"]; turn_on(env, t)
    h, uid = lite_person(env); placed(env, uid)
    assert env.c.get(f"/api/topics/{t}", headers=h).json()["diagram"] == "pro"
    r = env.c.get(f"/api/topics/{t}/diagram", headers=h); assert r.status_code == 403 and "Diagrams come with Pro" in r.json()["detail"] and seen == []
    url = env.c.get(f"/api/topics/{t}/diagram", headers=env.stu).json()["frame_url"]  # a link made for someone else is theirs alone
    assert "user" not in url and env.c.get(url.replace(url.split("t=")[1], main.frame_pass(main.Session_().get(User, uid), t))).status_code == 403
    with Session_() as s: s.get(User, uid).pro_until = dt.datetime.utcnow() + dt.timedelta(days=30); s.commit()
    assert env.c.get(f"/api/topics/{t}", headers=h).json()["diagram"] == "on"
    assert env.c.get(f"/api/topics/{t}/diagram", headers=h).json()["cached"] is True and len(seen) == 1

def test_a_reply_that_is_not_a_whole_drawing_is_not_kept(env, monkeypatch):
    ai_env(env, monkeypatch); t = ids()["topic"]["Water hardness"]; turn_on(env, t)
    for bad in ("Here is a diagram description, no HTML.", "<!doctype html><html><body><p>no drawing</p></body></html>",
                "<!doctype html><html><body><svg viewBox='0 0 1 1'>",  # cut off
                "<!doctype html><html><body><svg></svg>" + "x" * 70_000 + "</body></html>"):
        drawn(monkeypatch, bad)
        assert env.c.get(f"/api/topics/{t}/diagram", headers=env.stu).status_code == 502
    with Session_() as s: assert s.query(AICache).filter_by(topic_id=t, kind="diagram").count() == 0
    seen = drawn(monkeypatch); assert env.c.get(f"/api/topics/{t}/diagram", headers=env.stu).status_code == 200 and len(seen) == 1

def test_a_changed_note_or_topic_draws_it_again(env, monkeypatch):
    ai_env(env, monkeypatch); seen = drawn(monkeypatch); t = ids()["topic"]["Water hardness"]; turn_on(env, t, "a flow")
    env.c.get(f"/api/topics/{t}/diagram", headers=env.stu); turn_on(env, t, "a comparison table as a drawing")
    assert env.c.get(f"/api/topics/{t}/diagram", headers=env.stu).json()["cached"] is False and len(seen) == 2
