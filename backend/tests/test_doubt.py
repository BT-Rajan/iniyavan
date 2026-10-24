"""A doubt: the app's own copy answers first; only the program, semester, course and topic names and the marked phrase may go to the AI, and the answer is kept."""
import httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, AIEgress, DoubtAnswer, Topic

class Spy:  # DeepSeek: records exactly what was sent
    sent = []; mode = "ok"
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        Spy.sent.append(json["messages"]); req = httpx.Request("POST", url)
        if Spy.mode == "boom": raise httpx.ConnectError("down", request=req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hardness is dissolved calcium and magnesium."}}], "usage": {"total_tokens": 9}}, request=req)

def setup(env, monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", Spy); Spy.sent, Spy.mode = [], "ok"
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    t = i["topic"]["Water"]
    with Session_() as s:
        s.get(Topic, t).content = "Water is called hard when it holds salts. Temporary hardness comes from bicarbonates of calcium. Boiling removes it."; s.commit()
    return t
def local(env, h, t, phrase): return env.c.post(f"/api/topics/{t}/doubt", headers=h, json={"phrase": phrase})
def ask(env, h, t, phrase): return env.c.post(f"/api/topics/{t}/doubt/ask", headers=h, json={"phrase": phrase})

def test_the_local_step_sends_nothing_and_shows_where_the_phrase_sits(env, monkeypatch):
    t = setup(env, monkeypatch)
    r = local(env, env.stu, t, "bicarbonates").json()
    assert Spy.sent == [] and "bicarbonates of calcium" in r["passage"] and r["saved"] is None
    assert set(r["where"]) == {"program", "semester", "course", "topic"} and r["ai_left"] == main.DOUBT_DAILY
    assert local(env, env.stu, t, "something the notes never say").json()["passage"] == ""

def test_only_the_labels_and_the_phrase_go_to_the_ai_never_the_notes(env, monkeypatch):
    t = setup(env, monkeypatch)
    r = ask(env, env.stu, t, "bicarbonates").json(); assert r == {"text": "Hardness is dissolved calcium and magnesium.", "cached": False}
    sent = " ".join(m["content"] for m in Spy.sent[0])
    assert "bicarbonates" in sent and "Program:" in sent and "Semester:" in sent and "Course:" in sent and "Topic:" in sent
    assert "Temporary hardness comes from" not in sent and "Boiling removes it" not in sent and "holds salts" not in sent  # no notes
    with Session_() as s: assert s.query(AIEgress).filter_by(kind="doubt", ok=True).count() == 1 and s.query(DoubtAnswer).count() == 1

def test_the_same_doubt_is_never_sent_twice_and_is_shown_from_the_kept_copy(env, monkeypatch):
    t = setup(env, monkeypatch); ask(env, env.stu, t, "bicarbonates")
    again = ask(env, env.admin, t, "  Bicarbonates ").json(); assert again["cached"] is True and len(Spy.sent) == 1  # spacing and case don't make it a new doubt
    assert local(env, env.stu, t, "bicarbonates").json()["saved"] == "Hardness is dissolved calcium and magnesium."

def test_a_failed_call_is_logged_but_does_not_use_up_a_doubt(env, monkeypatch):
    t = setup(env, monkeypatch); Spy.mode = "boom"
    assert ask(env, env.stu, t, "bicarbonates").status_code == 503
    with Session_() as s: assert s.query(AIEgress).filter_by(kind="doubt", ok=False).count() == 1 and s.query(DoubtAnswer).count() == 0
    assert local(env, env.stu, t, "bicarbonates").json()["ai_left"] == main.DOUBT_DAILY

def test_the_daily_limit_and_phrase_size(env, monkeypatch):
    t = setup(env, monkeypatch); monkeypatch.setattr(main, "DOUBT_DAILY", 2)
    assert ask(env, env.stu, t, "first phrase").status_code == 200 and ask(env, env.stu, t, "second phrase").status_code == 200
    assert ask(env, env.stu, t, "third phrase").status_code == 429 and ask(env, env.stu, t, "first phrase").status_code == 200  # a kept answer is free
    assert ask(env, env.stu, t, "x" * 301).status_code == 400 and ask(env, env.stu, t, " ").status_code == 400

def test_a_phrase_that_reads_like_a_crisis_is_answered_with_care_without_the_ai(env, monkeypatch):
    t = setup(env, monkeypatch); r = ask(env, env.stu, t, "I want to kill myself").json()
    assert r.get("support") is True and Spy.sent == []

def test_access_rules_and_the_admin_report(env, monkeypatch):
    t = setup(env, monkeypatch); ask(env, env.stu, t, "bicarbonates")
    assert env.c.post(f"/api/topics/{t}/doubt/ask", json={"phrase": "x y"}).status_code in (401, 403)
    assert env.c.get("/api/admin/egress", headers=env.stu).status_code == 403
    rep = env.c.get("/api/admin/egress", headers=env.admin).json(); row = next(x for x in rep["by_kind"] if x["kind"] == "doubt")
    assert row["requests"] == 1 and row["failed"] == 0 and row["chars"] > 0
    assert env.c.get(f"/api/topics/{t}/ai/doubt", headers=env.stu).status_code == 404  # not reachable as a topic answer
