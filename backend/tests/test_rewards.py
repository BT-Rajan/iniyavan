import httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, User, ShareUse, SearchAnswer, hp

class Fake:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        c = '{"text": "It means the salts stay dissolved."}' if "highlighted" in str(json["messages"]) else "Hardness is calcium and magnesium."
        return httpx.Response(200, json={"choices": [{"message": {"content": c}}], "usage": {"total_tokens": 9}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch, n=3):
    monkeypatch.setattr(main.httpx, "AsyncClient", Fake)
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s:
        for k in range(n): s.add(User(name=f"P{k}", email=f"p{k}@x.com", pw=hp("pw"), role="student", program_id=i["prog"]["Mech"], semester=1))
        s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    return i["topic"]["Water"], [env.login(f"p{k}@x.com") for k in range(n)]
def search(env, h, q="what is hardness"): return env.c.post("/api/search/ai", headers=h, json={"q": q})

def test_others_reusing_my_search_count_once_a_day_and_never_my_own(env, monkeypatch):
    t, peers = setup(env, monkeypatch)
    search(env, env.stu); search(env, env.stu)                       # the author, twice: nothing
    for h in peers: search(env, h); search(env, h)                    # three others, each twice today: three uses
    r = env.c.get("/api/me/profile", headers=env.stu).json()["rewards"]
    assert r["uses"] == 3 and r["points"] == 0 and r["toward_next"] == 3 and r["top"] == [{"source": "search", "label": "what is hardness", "uses": 3}]
    assert env.c.get("/api/me/profile", headers=peers[0]).json()["rewards"]["uses"] == 0
    assert "rewards" not in env.c.get("/api/me/profile", headers=env.admin).json()  # staff are not rewarded
    a = search(env, peers[0]).json(); assert "author" not in str(a) and "stu@x.com" not in str(a)  # others never see who asked first

def test_every_thousand_uses_earn_a_hundred_points_however_they_add_up(env, monkeypatch):
    t, peers = setup(env, monkeypatch, n=1)
    with Session_() as s: uid = s.query(User).filter_by(email="stu@x.com").one().id
    with Session_() as s:  # 500 answers used twice each = 1000 uses
        s.add_all([ShareUse(author_id=uid, viewer_id=1000 + v, source="search", ref=r, day=main.dt.date(2026, 1, 1)) for r in range(1, 501) for v in range(2)]); s.commit()
    r = env.c.get("/api/me/profile", headers=env.stu).json()["rewards"]; assert r["uses"] == 1000 and r["points"] == 100 and r["toward_next"] == 0
    with Session_() as s: s.add_all([ShareUse(author_id=uid, viewer_id=5000 + v, source="search", ref=900, day=main.dt.date(2026, 1, 2)) for v in range(999)]); s.commit()
    assert env.c.get("/api/me/profile", headers=env.stu).json()["rewards"]["points"] == 100   # 1999 uses: still 100
    with Session_() as s: s.add(ShareUse(author_id=uid, viewer_id=9999, source="search", ref=901, day=main.dt.date(2026, 1, 3))); s.commit()
    assert env.c.get("/api/me/profile", headers=env.stu).json()["rewards"]["points"] == 200

def test_highlight_explanations_and_doubts_count_too(env, monkeypatch):
    t, peers = setup(env, monkeypatch, n=1)
    hl = lambda h: env.c.post(f"/api/topics/{t}/highlights", headers=h, json={"text": "calcium salts"}).json()["id"]
    env.c.post(f"/api/me/highlights/{hl(env.stu)}/explain", headers=env.stu)
    env.c.post(f"/api/me/highlights/{hl(peers[0])}/explain", headers=peers[0])
    r = env.c.get("/api/me/profile", headers=env.stu).json()["rewards"]; assert r["uses"] == 1 and r["top"][0]["source"] == "line"
