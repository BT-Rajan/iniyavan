import base64, io, httpx, main, guardrails
from types import SimpleNamespace as NS
from PIL import Image
from tests.test_access import CSV, ids, enrol
from main import Session_, Setting, AIEgress

def jpeg(w=2400, h=1800):
    buf = io.BytesIO(); Image.new("RGB", (w, h), "white").save(buf, "JPEG"); return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

class FakeClaude:  # anthropic.AsyncAnthropic, recording what was sent
    sent = []; reply = "The diagram shows a boiler with scale on its tubes."; stop = "end_turn"
    def __init__(self, **k): self.beta = NS(messages=NS(create=self.create)); FakeClaude.key = k.get("api_key")
    async def create(self, **kw):
        FakeClaude.sent.append(kw)
        return NS(stop_reason=FakeClaude.stop, content=[NS(type="text", text=FakeClaude.reply)], usage=NS(input_tokens=1500, output_tokens=80))
class FakeDeepSeek:
    sent = []
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, url, headers=None, json=None):
        FakeDeepSeek.sent.append(json["messages"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "Temporary hardness is removed by boiling."}}], "usage": {"total_tokens": 30}}, request=httpx.Request("POST", url))

def setup(env, monkeypatch, vision=True):
    monkeypatch.setattr(main.anthropic, "AsyncAnthropic", FakeClaude); monkeypatch.setattr(main.httpx, "AsyncClient", FakeDeepSeek)
    FakeClaude.sent, FakeDeepSeek.sent, FakeClaude.stop = [], [], "end_turn"; monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s:
        s.merge(Setting(k="deepseek_key", v="sk-test-1234"))
        if vision: s.merge(Setting(k="vision_key", v="sk-ant-test-9999"))
        s.commit()

def test_the_photo_is_read_on_the_server_shrunk_and_never_stored(env, monkeypatch):
    setup(env, monkeypatch); monkeypatch.setattr(main, "ocr_ready", lambda: True)
    import pytesseract; seen = {}
    def ocr(im, lang=None, timeout=None): seen["size"] = im.size; return "Define hardness of water.\n\n\n\n(2 marks)"
    monkeypatch.setattr(pytesseract, "image_to_string", ocr)
    r = env.c.post("/api/photo/read", headers=env.stu, json={"image": jpeg()}).json()
    assert r == {"text": "Define hardness of water.\n\n(2 marks)", "ocr": True} and max(seen["size"]) == 1568
    assert env.c.post("/api/photo/read", headers=env.stu, json={"image": "not a picture"}).status_code == 400
    assert FakeClaude.sent == [] and FakeDeepSeek.sent == []  # reading sends nothing anywhere

def test_text_questions_go_to_deepseek_as_text_only(env, monkeypatch):
    setup(env, monkeypatch)
    r = env.c.post("/api/photo/ask", headers=env.stu, json={"question": "Explain this", "text": "Define hardness of water.", "image": jpeg()}).json()
    assert r["via"] == "deepseek" and FakeClaude.sent == []
    msgs = FakeDeepSeek.sent[0]; assert msgs[0]["content"] == guardrails.GUARDRAILS and "Define hardness of water." in msgs[-1]["content"] and "base64" not in str(msgs)
    with Session_() as s: assert s.query(AIEgress).filter_by(kind="photo").count() == 1

def test_a_diagram_goes_to_claude_with_the_safety_rules_first(env, monkeypatch):
    setup(env, monkeypatch)
    assert env.c.get("/api/ai/status", headers=env.stu).json()["vision"] is True
    r = env.c.post("/api/photo/ask", headers=env.stu, json={"question": "What does the diagram show?", "text": "Fig 2.1", "image": jpeg(), "diagram": True}).json()
    assert r == {"text": FakeClaude.reply, "via": "claude"} and FakeClaude.key == "sk-ant-test-9999"
    kw = FakeClaude.sent[0]
    assert kw["model"] == "claude-opus-5-5" and kw["system"].startswith(guardrails.GUARDRAILS) and kw["fallbacks"] == "default"
    img, txt = kw["messages"][0]["content"]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg" and guardrails.OPEN in txt["text"] and "What does the diagram show?" in txt["text"]
    with Session_() as s: assert s.query(AIEgress).filter_by(kind="vision", ok=True).count() == 1
    FakeClaude.stop = "refusal"
    assert env.c.post("/api/photo/ask", headers=env.stu, json={"question": "What is this?", "image": jpeg(), "diagram": True}).json()["text"] == main.REFUSED

def test_without_a_claude_key_a_diagram_falls_back_to_its_text(env, monkeypatch):
    setup(env, monkeypatch, vision=False)
    assert env.c.get("/api/ai/status", headers=env.stu).json()["vision"] is False
    r = env.c.post("/api/photo/ask", headers=env.stu, json={"question": "Explain", "text": "Fig 2.1 boiler", "image": jpeg(), "diagram": True}).json()
    assert r["via"] == "deepseek" and FakeClaude.sent == []
    assert env.c.post("/api/photo/ask", headers=env.stu, json={"question": "Explain", "text": "", "image": jpeg(), "diagram": True}).status_code == 400

def test_photo_questions_have_a_daily_limit_and_crisis_care(env, monkeypatch):
    setup(env, monkeypatch); monkeypatch.setattr(main, "PHOTO_DAILY", 1)
    ask = lambda q: env.c.post("/api/photo/ask", headers=env.stu, json={"question": q, "text": "Some text"})
    assert ask("Explain").status_code == 200 and ask("Explain again").status_code == 429
    r = ask("i want to kill myself").json(); assert r["support"] is True and len(FakeDeepSeek.sent) == 1

def test_admins_set_and_test_the_claude_key(env, monkeypatch):
    setup(env, monkeypatch, vision=False)
    env.c.put("/api/admin/settings", headers=env.admin, json={"vision_key": "sk-ant-new-4321", "vision_model": "claude-sonnet-5-5"})
    cfg = env.c.get("/api/admin/settings", headers=env.admin).json(); assert cfg["vision_set"] and cfg["vision_hint"] == "…4321" and cfg["vision_model"] == "claude-sonnet-5-5"
    assert env.c.post("/api/admin/vision/test", headers=env.admin).json()["ok"] is True and FakeClaude.sent[-1]["model"] == "claude-sonnet-5-5"
    env.c.put("/api/admin/settings", headers=env.admin, json={"remove_vision_key": True})
    assert env.c.get("/api/admin/settings", headers=env.admin).json()["vision_set"] is False

def test_self_registered_people_never_use_the_colleges_claude_key(env, monkeypatch):
    setup(env, monkeypatch)
    with Session_() as s: u = s.query(main.User).filter_by(email="stu@x.com").one(); u.self_registered = True; u.ai_key = main.seal("sk-own-1111") if hasattr(main, "seal") else None; s.commit()
    assert env.c.get("/api/ai/status", headers=env.stu).json()["vision"] is False
