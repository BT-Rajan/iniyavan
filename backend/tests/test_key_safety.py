import httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, User, AuditLog, hp

KEY_A = "sk-student-a-0123456789abcdefWXYZ"; ADMIN_KEY = "sk-admin-shared-9876543210fedcba"
class Spy:  # DeepSeek: records the URL and the key each request carried
    calls = []
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        Spy.calls.append((url, headers.get("Authorization")))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 3}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch, admin_key=True):
    monkeypatch.setattr(main.httpx, "AsyncClient", Spy); monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False); Spy.calls = []
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s:
        for e in ("a@self.com", "c@self.com"): s.add(User(name=e, email=e, pw=hp("pw"), role="student", self_registered=True, program_id=i["prog"]["Mech"], semester=1))
        if admin_key: s.merge(Setting(k="deepseek_key", v=ADMIN_KEY))
        s.commit()
    a, c = env.login("a@self.com"), env.login("c@self.com")
    assert env.c.put("/api/me/ai-key", headers=a, json={"key": KEY_A}).status_code == 200
    return i["topic"]["Water"], a, c

def test_the_key_is_stored_encrypted_and_never_comes_back_whole(env, monkeypatch):
    t, a, c = setup(env, monkeypatch)
    with Session_() as s: stored = s.query(User).filter_by(email="a@self.com").one().ai_key
    assert stored and KEY_A not in stored and main.unseal(stored) == KEY_A
    uid = env.c.get("/api/me", headers=a).json()["id"]
    seen = [env.c.get(u, headers=h).text for u, h in (("/api/me/ai-key", a), ("/api/me", a), ("/api/ai/status", a), ("/api/admin/users", env.admin), (f"/api/admin/users/{uid}", env.admin),
                                                        ("/api/admin/settings", env.admin), ("/api/admin/audit", env.admin), ("/api/admin/audit?format=csv", env.admin), ("/api/me/ai-key", c))]
    assert all(KEY_A not in x and KEY_A[4:-4] not in x for x in seen)
    assert env.c.get("/api/me/ai-key", headers=a).json()["key_hint"] == "…WXYZ" and env.c.get("/api/me/ai-key", headers=c).json()["key_set"] is False
    with Session_() as s: assert not any(KEY_A in (r.path or "") for r in s.query(AuditLog))  # the log keeps the path, never the body

def test_nobody_elses_request_ever_carries_the_students_key(env, monkeypatch):
    t, a, c = setup(env, monkeypatch); Spy.calls = []
    env.c.get(f"/api/topics/{t}/ai/explain", headers=env.stu)            # a staff-added student: the admin's key
    env.c.post("/api/search/ai", headers=env.stu, json={"q": "what is hardness"})
    r = env.c.post("/api/search/ai", headers=c, json={"q": "what is softening"})  # another self-registered student, no key of their own: lite, on the admin's key
    assert r.status_code == 200
    env.c.post("/api/search/ai", headers=a, json={"q": "what is ion exchange"})  # the owner: their own key
    assert Spy.calls and all(url == "https://api.deepseek.com/chat/completions" for url, _ in Spy.calls)
    assert [k for _, k in Spy.calls] == [f"Bearer {ADMIN_KEY}", f"Bearer {ADMIN_KEY}", f"Bearer {ADMIN_KEY}", f"Bearer {KEY_A}"]  # never student A's key for anyone else

def test_without_an_admin_key_staff_added_students_dont_fall_back_to_a_students_key(env, monkeypatch):
    t, a, c = setup(env, monkeypatch, admin_key=False); Spy.calls = []
    assert env.c.get(f"/api/topics/{t}/ai/explain", headers=env.stu).status_code == 503 and Spy.calls == []
    assert env.c.get("/api/ai/status", headers=env.stu).json()["available"] is False

def test_a_removed_key_is_gone_and_tries_are_limited(env, monkeypatch):
    t, a, c = setup(env, monkeypatch)
    assert env.c.delete("/api/me/ai-key", headers=a).status_code == 200
    with Session_() as s: assert s.query(User).filter_by(email="a@self.com").one().ai_key is None
    monkeypatch.setattr(main, "KEY_TRIES", 2)
    codes = [env.c.put("/api/me/ai-key", headers=c, json={"key": "sk-guess-%020d" % n}).status_code for n in range(3)]
    assert codes == [200, 200, 429]
