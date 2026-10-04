import httpx, main
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, AICache

class FakeClient:  # stands in for the DeepSeek API
    mode = "ok"; calls = 0
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        FakeClient.calls += 1; req = httpx.Request("POST", url)
        if FakeClient.mode == "boom": raise httpx.ConnectError("down", request=req)
        if FakeClient.mode in ("401", "500"): return httpx.Response(int(FakeClient.mode), json={}, request=req)
        if FakeClient.mode == "junk": return httpx.Response(200, json={"nope": 1}, request=req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hard water explained."}}], "usage": {"total_tokens": 42}}, request=req)

def setup(env, monkeypatch, key=None):
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient); monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False); FakeClient.mode, FakeClient.calls = "ok", 0
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    if key:
        with Session_() as s: s.merge(Setting(k="deepseek_key", v=key)); s.commit()
    return i["topic"]["Water"]
def ask(env, h, t): return env.c.get(f"/api/topics/{t}/ai/explain", headers=h)

def test_without_a_key_everyone_sees_ai_unavailable(env, monkeypatch):
    t = setup(env, monkeypatch)
    assert env.c.get("/api/ai/status", headers=env.stu).json() == {"available": False, "own_key": False}
    r = ask(env, env.stu, t); assert r.status_code == 503 and r.json()["detail"] == "AI unavailable. Try again later." and FakeClient.calls == 0
    assert "Admin" in ask(env, env.admin, t).json()["detail"]  # admins also learn how to fix it

def test_with_a_key_it_works_and_answers_are_shared(env, monkeypatch):
    t = setup(env, monkeypatch, "sk-test-1234")
    assert env.c.get("/api/ai/status", headers=env.stu).json() == {"available": True, "own_key": False}
    a = ask(env, env.stu, t).json(); assert a == {"text": "Hard water explained.", "cached": False}
    assert ask(env, env.admin, t).json()["cached"] is True and FakeClient.calls == 1
    with Session_() as s: assert s.query(AICache).count() == 1

def test_removing_the_key_turns_ai_off_for_all_even_saved_answers(env, monkeypatch):
    t = setup(env, monkeypatch, "sk-test-1234"); ask(env, env.stu, t)
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"remove_key": True}).status_code == 200
    assert env.c.get("/api/admin/settings", headers=env.admin).json()["key_set"] is False and ask(env, env.stu, t).status_code == 503
    env.c.put("/api/admin/settings", headers=env.admin, json={"deepseek_key": "sk-new"}); assert ask(env, env.stu, t).json()["cached"] is True
    assert env.c.put("/api/admin/settings", headers=env.stu, json={"remove_key": True}).status_code == 403

def test_provider_failures_never_leak_details_to_students(env, monkeypatch):
    t = setup(env, monkeypatch, "sk-test-1234")
    for mode in ("boom", "401", "500", "junk"):
        FakeClient.mode = mode; r = ask(env, env.stu, t)
        assert r.status_code == 503 and r.json()["detail"] == "AI unavailable. Try again later.", mode
    FakeClient.mode = "401"; assert "401" in ask(env, env.admin, t).json()["detail"]
    FakeClient.mode = "ok"; assert ask(env, env.stu, t).status_code == 200  # recovers by itself

def test_key_test_button_and_env_fallback(env, monkeypatch):
    setup(env, monkeypatch)
    assert env.c.post("/api/admin/ai/test", headers=env.admin).json()["ok"] is False
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env"); assert env.c.get("/api/ai/status", headers=env.stu).json()["available"] is True
    assert env.c.post("/api/admin/ai/test", headers=env.admin).json()["ok"] is True
    FakeClient.mode = "401"; r = env.c.post("/api/admin/ai/test", headers=env.admin).json(); assert r["ok"] is False and "invalid" in r["message"]
    assert env.c.post("/api/admin/ai/test", headers=env.stu).status_code == 403
