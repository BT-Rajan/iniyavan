import json, httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, User, AICache, AIEgress, Topic, hp

class Fake:  # DeepSeek: "translates" by tagging each part, and bills 100 tokens a call
    calls = []
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        user = json["messages"][-1]["content"]; Fake.calls.append(user)
        body = user.split("\n", 1)[1].rsplit("\n", 1)[0].split("\n\n", 1)[1] if "Format:" in user else "OK"  # the part between the fence markers, after the Format line
        return httpx.Response(200, json={"choices": [{"message": {"content": "[ta] " + body}}], "usage": {"total_tokens": 100}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch, content=None):
    monkeypatch.setattr(main.httpx, "AsyncClient", Fake); Fake.calls = []
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1); t = i["topic"]["Water"]
    with Session_() as s:
        s.merge(Setting(k="deepseek_key", v="sk-test-1234"))
        if content: s.get(Topic, t).content = content
        s.commit()
    return t

def test_notes_are_translated_once_in_parts_and_shared(env, monkeypatch):
    t = setup(env, monkeypatch, content="\n\n".join(f"Paragraph {n}. " + "word " * 300 for n in range(6)))
    env.c.put("/api/me/lang", headers=env.stu, json={"lang": "ta"})
    r = env.c.get(f"/api/topics/{t}/translation", headers=env.stu).json()
    assert r["cached"] is False and r["format"] == "markdown" and r["content"].count("[ta]") == len(Fake.calls) > 1  # long notes go in several parts
    assert all("Paragraph" in c for c in Fake.calls) and "".join(Fake.calls).count("Paragraph") == 6  # every paragraph sent once
    calls = len(Fake.calls); env.c.put("/api/me/lang", headers=env.admin, json={"lang": "ta"})
    assert env.c.get(f"/api/topics/{t}/translation", headers=env.admin).json()["cached"] is True and len(Fake.calls) == calls  # shared
    env.c.put("/api/me/lang", headers=env.admin, json={"lang": "en"})
    assert env.c.get(f"/api/topics/{t}/translation", headers=env.admin).status_code == 400  # English readers have the original

def test_html_notes_split_at_block_ends():
    parts = main.note_parts("<h2>A</h2>" + "<p>" + "x" * 2000 + "</p>" + "<p>" + "y" * 2000 + "</p><p>tail", "html")
    assert len(parts) == 2 and parts[0].endswith("</p>") and "".join(parts) == "<h2>A</h2>" + "<p>" + "x" * 2000 + "</p>" + "<p>" + "y" * 2000 + "</p><p>tail"

def test_translated_html_is_cleaned(env, monkeypatch):
    t = setup(env, monkeypatch)
    with Session_() as s: x = s.get(Topic, t); x.content, x.content_format = "<p>Hard water</p>", "html"; s.commit()
    monkeypatch.setattr(Fake, "post", lambda self, url, headers=None, json=None: _evil(url))
    env.c.put("/api/me/lang", headers=env.stu, json={"lang": "ar"})
    r = env.c.get(f"/api/topics/{t}/translation", headers=env.stu).json()
    assert "<script" not in r["content"] and "onerror" not in r["content"] and "ماء" in r["content"]
async def _evil(url):
    return httpx.Response(200, json={"choices": [{"message": {"content": '<p onclick="x()">ماء عسر</p><script>alert(1)</script><img src=x onerror=alert(1)>'}}], "usage": {"total_tokens": 5}}, request=httpx.Request("POST", url))

def test_the_monthly_allowance_stops_new_requests_but_not_saved_answers(env, monkeypatch):
    t = setup(env, monkeypatch)
    env.c.put("/api/admin/settings", headers=env.admin, json={"budget_deepseek": 150})
    ask = lambda q: env.c.post("/api/search/ai", headers=env.stu, json={"q": q})
    assert ask("what is hardness").status_code == 200                      # 100 of 150
    assert ask("what is softening").status_code == 200                     # 200: over now
    r = ask("what is zeolite"); assert r.status_code == 503 and "allowance" in r.json()["detail"]
    assert ask("what is hardness").json()["cached"] is True                 # saved answers still work
    cfg = env.c.get("/api/admin/settings", headers=env.admin).json()["budget"]["deepseek"]; assert cfg == {"limit": 150, "used": 200}
    b = env.c.get("/api/admin/budget", headers=env.admin).json(); assert b["deepseek"]["share"] > 1 and b["claude"]["limit"] == 0
    assert env.c.get("/api/admin/budget", headers=env.stu).status_code == 403
    env.c.put("/api/admin/settings", headers=env.admin, json={"budget_deepseek": 0})  # 0 = no limit
    assert ask("what is zeolite").status_code == 200

def test_own_key_users_are_outside_the_allowance(env, monkeypatch):
    t = setup(env, monkeypatch)
    with Session_() as s:
        s.add(User(name="Own", email="own@x.com", pw=hp("pw"), role="student", self_registered=True, ai_key=main.seal("sk-own-key-0123456789abcdef"))); s.commit()
    env.c.put("/api/admin/settings", headers=env.admin, json={"budget_deepseek": 1})
    own = env.login("own@x.com")
    assert env.c.post("/api/search/ai", headers=own, json={"q": "what is hardness"}).status_code == 200
    with Session_() as s: assert s.query(AIEgress).filter_by(own=True).count() == 1
    assert env.c.get("/api/admin/budget", headers=env.admin).json()["deepseek"]["used"] == 0  # their tokens are not the college's
