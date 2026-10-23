import json, httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, AICache, AIFlag, SearchAnswer, Topic, Course, User

class Fake:  # DeepSeek, answering in whatever shape it is told
    reply = {"text": "It means the salts stay dissolved."}; calls = 0; last = None
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        Fake.calls += 1; Fake.last = json; c = Fake.reply if isinstance(Fake.reply, str) else __import__("json").dumps(Fake.reply)
        return httpx.Response(200, json={"choices": [{"message": {"content": c}}], "usage": {"total_tokens": 20}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", Fake); Fake.reply, Fake.calls = {"text": "It means the salts stay dissolved."}, 0
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    return i["topic"]["Water"]
def hl(env, t, text="calcium salts", who=None): return env.c.post(f"/api/topics/{t}/highlights", headers=who or env.stu, json={"text": text}).json()

def test_a_highlight_gets_an_explanation_saved_per_passage(env, monkeypatch):
    t = setup(env, monkeypatch); h = hl(env, t)
    r = env.c.post(f"/api/me/highlights/{h['id']}/explain", headers=env.stu).json()["explain"]
    assert r["text"] == "It means the salts stay dissolved." and r["id"] and "calcium salts" in Fake.last["messages"][-1]["content"] and Fake.last["max_tokens"] == main.STEPS["line"]
    assert env.c.get(f"/api/topics/{t}/highlights", headers=env.stu).json()["items"][0]["explain"]["text"] == r["text"]
    assert env.c.get("/api/me/highlights", headers=env.stu).json()["items"][0]["explain"]["id"] == r["id"]
    h2 = hl(env, t, "  Calcium   salts ", who=env.admin)  # the same words from someone else: no new AI call
    assert env.c.post(f"/api/me/highlights/{h2['id']}/explain", headers=env.admin).json()["explain"]["id"] == r["id"] and Fake.calls == 1
    assert env.c.post(f"/api/me/highlights/{h['id']}/explain", headers=env.admin).status_code == 404  # only your own highlights
    assert env.c.get(f"/api/topics/{t}/ai/line", headers=env.stu).status_code == 404

def test_highlight_explanations_have_a_daily_limit(env, monkeypatch):
    t = setup(env, monkeypatch); monkeypatch.setattr(main, "LINE_DAILY", 2)
    codes = [env.c.post(f"/api/me/highlights/{hl(env, t, f'passage {n}')['id']}/explain", headers=env.stu).status_code for n in range(3)]
    assert codes == [200, 200, 429]

def test_a_flag_reaches_the_owner_without_the_students_name_and_rewrite_drops_the_saved_reply(env, monkeypatch):
    t = setup(env, monkeypatch); Fake.reply = {"points": ["a", "b", "c"], "hook": "Why?", "hook_answer": "Because."}
    g = env.c.get(f"/api/topics/{t}/ai/gist", headers=env.stu).json(); assert g["id"]
    with Session_() as s:
        fac = s.query(User).filter_by(email="fac@x.com").one().id; s.query(Course).filter(Course.id == s.get(Topic, t).course_id).update({"faculty_owner_id": fac}); s.commit()
    assert env.c.post("/api/ai/flag", headers=env.stu, json={"source": "topic", "id": g["id"], "topic_id": t, "reason": "Point b is wrong"}).json() == {"ok": True}
    env.c.post("/api/ai/flag", headers=env.stu, json={"source": "topic", "id": g["id"], "topic_id": t})  # twice: counted once
    env.c.post("/api/ai/flag", headers=env.admin, json={"source": "topic", "id": g["id"], "topic_id": t, "reason": "b and c"})
    r = env.c.get("/api/flags", headers=env.fac).json(); f = r["items"][0]
    assert r["total"] == 1 and f["count"] == 2 and f["reasons"] == ["b and c", "Point b is wrong"] and f["topic"] == "Water" and "user" not in json.dumps(f) and "stu@x.com" not in json.dumps(f)
    assert env.c.get("/api/flags", headers=env.stu).status_code == 403
    assert env.c.post(f"/api/flags/{f['id']}/resolve", headers=env.fac, json={"action": "rewrite"}).json()["closed"] == 2
    with Session_() as s: assert s.get(AICache, g["id"]) is None
    calls = Fake.calls; env.c.get(f"/api/topics/{t}/ai/gist", headers=env.stu); assert Fake.calls == calls + 1  # written again on the next request
    assert env.c.get("/api/flags", headers=env.fac).json()["total"] == 0

def test_search_flags_go_to_admins_and_keep_lets_the_answer_stand(env, monkeypatch):
    setup(env, monkeypatch); Fake.reply = "Hardness is calcium and magnesium."
    a = env.c.post("/api/search/ai", headers=env.stu, json={"q": "what is hardness"}).json(); assert a["id"]
    env.c.post("/api/ai/flag", headers=env.stu, json={"source": "search", "id": a["id"]})
    assert env.c.get("/api/flags", headers=env.fac).json()["total"] == 0  # not a faculty member's topic
    f = env.c.get("/api/flags", headers=env.admin).json()["items"][0]; assert f["kind"] == "search" and f["excerpt"].startswith("Hardness")
    env.c.post(f"/api/flags/{f['id']}/resolve", headers=env.admin, json={"action": "keep"})
    with Session_() as s: assert s.get(SearchAnswer, a["id"]) is not None and s.query(AIFlag).filter_by(status="kept").count() == 1

def test_the_revision_sheet_lists_saved_gists_and_my_highlights(env, monkeypatch):
    t = setup(env, monkeypatch); Fake.reply = {"points": ["one", "two", "three"], "hook": "Why?", "hook_answer": "Because."}
    env.c.get(f"/api/topics/{t}/ai/gist", headers=env.stu); hl(env, t, "calcium salts")
    with Session_() as s: uid = s.get(Topic, t).unit_id
    r = env.c.get(f"/api/units/{uid}/revision", headers=env.stu).json(); row = next(x for x in r["topics"] if x["id"] == t)
    assert row["gist"]["points"] == ["one", "two", "three"] and row["highlights"] == ["calcium salts"] and all("gist" in x for x in r["topics"])
    calls = Fake.calls; env.c.get(f"/api/units/{uid}/revision", headers=env.stu); assert Fake.calls == calls  # the sheet itself never calls the AI

def test_a_flagged_step_reads_as_text_not_json(env, monkeypatch):
    t = setup(env, monkeypatch); h = hl(env, t); e = env.c.post(f"/api/me/highlights/{h['id']}/explain", headers=env.stu).json()["explain"]
    env.c.post("/api/ai/flag", headers=env.stu, json={"source": "topic", "id": e["id"], "topic_id": t})
    assert env.c.get("/api/flags", headers=env.admin).json()["items"][0]["excerpt"] == "It means the salts stay dissolved."
