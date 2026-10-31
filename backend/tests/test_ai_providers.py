# The college answers with one AI provider at a time (DeepSeek, ChatGPT, Claude, Qwen or Perplexity), chosen under Settings; a person's own key can be any of them.
# Each request goes to that provider only, with its key and model, the safety rules first; the ledger, allowance and costs follow the provider.
import httpx, main, guardrails
from types import SimpleNamespace as NS
from tests.test_access import CSV, ids, enrol
from tests.test_school_ai import setup as school, set_key, login
from main import Session_, Setting, User, AIEgress, hp

class Spy:  # the OpenAI-style providers: records the URL, key and body of each request
    calls = []; status = 200
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        Spy.calls.append({"url": url, "auth": headers.get("Authorization"), **json})
        return httpx.Response(Spy.status, json={"choices": [{"message": {"content": "Boiling removes temporary hardness."}}], "usage": {"total_tokens": 42}}, request=httpx.Request("POST", url))
class FakeClaude:  # anthropic.AsyncAnthropic
    sent = []
    def __init__(self, **k): self.key = k.get("api_key"); self.beta = NS(messages=NS(create=self.create)); self.messages = NS(create=self.create)
    async def create(self, **kw):
        FakeClaude.sent.append({"key": self.key, **kw})
        return NS(stop_reason="end_turn", content=[NS(type="text", text="Boiling removes temporary hardness.")], usage=NS(input_tokens=30, output_tokens=12))

def setup(env, monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", Spy); monkeypatch.setattr(main.anthropic, "AsyncAnthropic", FakeClaude); Spy.calls, Spy.status, FakeClaude.sent = [], 200, []
    for v in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY", "PERPLEXITY_API_KEY"): monkeypatch.delenv(v, raising=False)
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: s.add(User(name="Self", email="a@self.com", pw=hp("pw"), role="student", self_registered=True, program_id=i["prog"]["Mech"], semester=1)); s.commit()
    return env.login("a@self.com")
def ask(env, h, q="what is hardness"): return env.c.post("/api/search/ai", headers=h, json={"q": q})
def ledger():
    with Session_() as s: return [(r.provider, r.own, r.tokens) for r in s.query(AIEgress).order_by(AIEgress.id)]

def test_the_college_answers_with_the_provider_the_admin_chose(env, monkeypatch):
    setup(env, monkeypatch)
    r = env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "openai", "keys": {"openai": "sk-proj-college-0000000000"}, "models": {"openai": "gpt-4.1"}})
    assert r.status_code == 200
    cfg = env.c.get("/api/admin/settings", headers=env.admin).json(); prov = {p["id"]: p for p in cfg["providers"]}
    assert cfg["provider"] == "openai" and cfg["key_set"] and cfg["key_hint"] == "…0000" and cfg["model"] == "gpt-4.1" and prov["openai"]["key_set"] and not prov["deepseek"]["key_set"]
    assert "sk-proj-college-0000000000" not in str(cfg)  # never the whole key
    assert ask(env, env.stu).status_code == 200
    c = Spy.calls[0]; assert c["url"] == "https://api.openai.com/v1/chat/completions" and c["auth"] == "Bearer sk-proj-college-0000000000" and c["model"] == "gpt-4.1"
    assert c["messages"][0]["role"] == "system" and c["messages"][0]["content"].startswith(guardrails.GUARDRAILS) and [m["role"] for m in c["messages"]] == ["system", "user"]  # one system message
    assert "max_tokens" not in c and ledger() == [("openai", False, 42)]
    assert env.c.post("/api/admin/ai/test", headers=env.admin).json()["ok"] is True

def test_claude_qwen_and_perplexity_answer_too(env, monkeypatch):
    setup(env, monkeypatch)
    env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "claude", "keys": {"claude": "sk-ant-college-1111111111"}})
    assert ask(env, env.stu).status_code == 200 and Spy.calls == []
    sent = FakeClaude.sent[0]; assert sent["key"] == "sk-ant-college-1111111111" and sent["model"] == "claude-opus-5-5" and sent["system"].startswith(guardrails.GUARDRAILS)
    assert [m["role"] for m in sent["messages"]] == ["user"] and ledger() == [("claude", False, 42)]
    with Session_() as s: assert main.vision_key(s) == "sk-ant-college-1111111111"  # the same Claude key reads diagrams
    for p, url, model in (("qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-plus"), ("perplexity", "https://api.perplexity.ai/chat/completions", "sonar")):
        env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": p, "keys": {p: f"key-{p}-2222222222222"}}); Spy.calls = []
        assert ask(env, env.stu, "what is " + p).status_code == 200
        assert (Spy.calls[0]["url"], Spy.calls[0]["auth"], Spy.calls[0]["model"]) == (url, f"Bearer key-{p}-2222222222222", model)

def test_switching_provider_without_its_key_turns_ai_off_until_one_is_saved(env, monkeypatch):
    setup(env, monkeypatch)
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-deepseek-college-33333")); s.commit()
    env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "qwen"})
    assert env.c.get("/api/ai/status", headers=env.stu).json()["available"] is False and ask(env, env.stu).status_code == 503 and Spy.calls == []
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "gemini"}).status_code == 400
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"keys": {"gemini": "x" * 30}}).status_code == 400
    env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "deepseek"}); assert ask(env, env.stu).status_code == 200  # the saved DeepSeek key still works

def test_a_persons_own_key_can_be_any_provider(env, monkeypatch):
    a = setup(env, monkeypatch)
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-deepseek-college-33333")); s.commit()
    assert env.c.put("/api/me/ai-key", headers=a, json={"key": "pplx-own-key-4444444444444", "provider": "gemini"}).status_code == 400
    r = env.c.put("/api/me/ai-key", headers=a, json={"key": "pplx-own-key-4444444444444", "provider": "perplexity"}); assert r.status_code == 200
    assert Spy.calls[-1]["url"] == "https://api.perplexity.ai/chat/completions" and Spy.calls[-1]["max_tokens"] == 16  # the key was checked with Perplexity
    k = env.c.get("/api/me/ai-key", headers=a).json(); assert (k["provider"], k["provider_name"], k["key_hint"]) == ("perplexity", "Perplexity", "…4444") and len(k["providers"]) == 5
    Spy.calls = []; assert ask(env, a).status_code == 200 and env.c.get("/api/me/plan", headers=a).json()["plan"] == "own"
    assert (Spy.calls[0]["url"], Spy.calls[0]["auth"]) == ("https://api.perplexity.ai/chat/completions", "Bearer pplx-own-key-4444444444444") and ledger()[-1] == ("perplexity", True, 42)
    Spy.calls = []; ask(env, env.stu, "what is scale"); assert Spy.calls[0]["auth"] == "Bearer sk-deepseek-college-33333"  # nobody else uses it
    Spy.status = 401; r = env.c.put("/api/me/ai-key", headers=a, json={"key": "sk-ant-wrong-55555555555555", "provider": "openai"})
    assert r.status_code == 400 and "ChatGPT rejected this key (401)" in r.json()["detail"]
    assert env.c.get("/api/me/ai-key", headers=a).json()["provider"] == "perplexity"  # a key that failed the check changes nothing
    env.c.delete("/api/me/ai-key", headers=a)
    with Session_() as s: u = s.query(User).filter_by(email="a@self.com").one(); assert u.ai_key is None and u.ai_provider is None

def test_a_parents_claude_key_answers_for_their_child_and_is_not_the_colleges_cost(env, monkeypatch):
    setup(env, monkeypatch); i = school(); set_key(i["Mum"], "sk-ant-parent-666666666666")
    with Session_() as s: s.get(User, i["Mum"]).ai_provider = "claude"; s.merge(Setting(k="budget_deepseek", v="1")); s.commit()
    h = login(env, "kavin"); r = ask(env, h)
    assert r.status_code == 200 and FakeClaude.sent[0]["key"] == "sk-ant-parent-666666666666" and Spy.calls == []
    assert ledger()[-1] == ("claude", True, 42)  # paid by the parent: outside the college's allowance and costs
    assert env.c.get("/api/admin/budget", headers=env.admin).json()["claude"]["used"] == 0

def test_each_provider_has_its_own_monthly_allowance(env, monkeypatch):
    setup(env, monkeypatch)
    env.c.put("/api/admin/settings", headers=env.admin, json={"ai_provider": "openai", "keys": {"openai": "sk-proj-college-0000000000"}, "budgets": {"openai": 40}})
    assert ask(env, env.stu, "first").status_code == 200  # 42 tokens: now over the ChatGPT allowance
    r = ask(env, env.admin, "second"); assert r.status_code == 503 and "ChatGPT allowance" in r.json()["detail"]
    b = env.c.get("/api/admin/budget", headers=env.admin).json(); assert b["openai"] == {"limit": 40, "used": 42, "share": 1.05} and b["deepseek"]["used"] == 0 and b["names"]["openai"] == "ChatGPT"
