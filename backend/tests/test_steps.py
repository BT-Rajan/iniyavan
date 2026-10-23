import datetime as dt, json, httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, AICache, Progress, User

GIST = {"points": ["Hard water carries calcium and magnesium salts.", "Boiling removes only temporary hardness.", "It wastes soap and scales boilers."],
        "hook": "Why does boiling remove only one kind?", "hook_answer": "Bicarbonates break down into insoluble carbonates; chlorides stay dissolved."}
class Fake:  # DeepSeek, answering each step in JSON (or not, when told to misbehave)
    reply = GIST; calls = 0; last = None
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        Fake.calls += 1; Fake.last = json; content = Fake.reply if isinstance(Fake.reply, str) else "```json\n" + __import__("json").dumps(Fake.reply) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 30}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", Fake); Fake.reply, Fake.calls = GIST, 0
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    return i["topic"]["Water"]

def test_the_gist_is_short_json_saved_once_and_steps_are_capped(env, monkeypatch):
    t = setup(env, monkeypatch)
    r = env.c.get(f"/api/topics/{t}/ai/gist", headers=env.stu).json()
    assert r["data"]["hook"] == GIST["hook"] and len(r["data"]["points"]) == 3 and r["cached"] is False
    assert Fake.last["max_tokens"] == main.STEPS["gist"] and "JSON" in Fake.last["messages"][0]["content"]
    assert env.c.get(f"/api/topics/{t}/ai/gist", headers=env.admin).json()["cached"] is True and Fake.calls == 1
    Fake.reply = {"question": "Distinguish temporary and permanent hardness (2 marks)", "answer": "Temporary: bicarbonates, removed by boiling.", "tip": "Name the salts."}
    r = env.c.get(f"/api/topics/{t}/ai/exam", headers=env.stu).json(); assert r["data"]["tip"] == "Name the salts."
    assert "Question pattern" in Fake.last["messages"][1]["content"]  # exam steps see the pattern and guideline
    assert env.c.get(f"/api/topics/{t}/ai/search", headers=env.stu).status_code == 404

def test_a_step_the_ai_garbles_is_not_saved(env, monkeypatch):
    t = setup(env, monkeypatch); Fake.reply = "Sure! Here is why..."
    assert env.c.get(f"/api/topics/{t}/ai/why", headers=env.stu).status_code == 502
    with Session_() as s: assert s.query(AICache).filter_by(kind="why").count() == 0

def test_remember_this_asks_from_a_topic_read_days_ago(env, monkeypatch):
    t = setup(env, monkeypatch)
    assert env.c.get("/api/me/recall", headers=env.stu).json() == {"item": None}
    env.c.post(f"/api/topics/{t}/read", headers=env.stu); env.c.get(f"/api/topics/{t}/ai/gist", headers=env.stu)
    assert env.c.get("/api/me/recall", headers=env.stu).json() == {"item": None}  # read today: too soon
    with Session_() as s:
        uid = s.query(User).filter_by(email="stu@x.com").one().id
        s.query(Progress).filter_by(user_id=uid, topic_id=t).update({"last_read": dt.datetime.utcnow() - dt.timedelta(days=4)}); s.commit()
    calls = Fake.calls; r = env.c.get("/api/me/recall", headers=env.stu).json()["item"]
    assert r["topic_id"] == t and r["question"] == GIST["hook"] and r["answer"] == GIST["hook_answer"] and Fake.calls == calls  # no AI call

def test_students_are_not_nudged_about_lateness_or_low_scores():
    assert "overdue" not in main.STUDENT_NOTES and "quiz_retake" not in main.STUDENT_NOTES
