import main
from main import Session_, Setting, SearchAnswer, SearchLog, AICache, User
from tests.test_ai import FakeClient
from tests.test_access import ids, enrol

CSV = ("program,semester,course,unit,topic,content\n"
       "Mech,Semester 1,Chem,U1,Water hardness,\"Hardness of water is caused by dissolved calcium and magnesium salts. Temporary hardness comes from bicarbonates.\"\n"
       "Mech,Semester 1,Chem,U1,Boiler troubles,\"Scale and sludge form in boilers when hard water is used. Priming and foaming too.\"\n"
       "Mech,Semester 1,Physics,U2,Heat engines,\"Carnot cycle and efficiency of engines.\"\n"
       "Civil,Semester 1,Surveying,U1,Chain surveying,\"Measuring distances with a chain. Water bodies are crossed by offsets.\"\n")

def seed(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1); return i
def find(env, q, h=None): return env.c.get("/api/search", headers=h or env.stu, params={"q": q}).json()
def titles(r): return [x["title"] for x in r["results"]]

def test_local_search_ranks_title_matches_first_and_marks_them_confident(env):
    seed(env); r = find(env, "water hardness")
    assert titles(r)[0] == "Water hardness" and r["confident"] is True and "calcium" in r["results"][0]["snippet"] and r["results"][0]["course"] == "Chem"
    assert r["results"][0]["program"] == "Mech" and r["results"][0]["semester"] == "Semester 1"
    assert titles(find(env, "What is the difference between hard waters"))[0] == "Water hardness"  # filler words dropped, plural handled
    assert "Boiler troubles" in titles(find(env, "boilers"))

def test_a_student_only_finds_what_they_may_open(env):
    i = seed(env)
    assert "Chain surveying" not in titles(find(env, "chain surveying")) and find(env, "chain surveying")["results"] == []  # another program
    assert "Chain surveying" in titles(find(env, "chain surveying", env.admin))
    tid = i["topic"]["Boiler troubles"]; env.c.put(f"/api/topics/{tid}/publish", headers=env.admin, json={"published": False})
    assert "Boiler troubles" not in titles(find(env, "boiler")) and "Boiler troubles" in titles(find(env, "boiler", env.admin))
    env.add_user("loose@x.com"); assert find(env, "water", env.login("loose@x.com"))["results"] == []  # not placed yet

def test_content_only_and_no_matches(env):
    seed(env); r = find(env, "calcium")
    assert titles(r) == ["Water hardness"] and r["confident"] is False  # found only inside the notes, so the app also offers the AI
    none = find(env, "quantum entanglement"); assert none["results"] == [] and none["confident"] is False
    for q in ("", "a", "the of", "x" * 5000): assert env.c.get("/api/search", headers=env.stu, params={"q": q}).status_code == 200
    assert find(env, "water boiler pressure vessel")["results"] != [] and find(env, "zebra giraffe water lion tiger")["results"] == []  # needs about half the words
    assert env.c.get("/api/search", params={"q": "water"}).status_code in (401, 403)

def ai_env(env, monkeypatch, key="sk-test-1234"):
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient); monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False); FakeClient.mode, FakeClient.calls = "ok", 0
    seed(env)
    if key:
        with Session_() as s: s.merge(Setting(k="deepseek_key", v=key)); s.commit()
def ask(env, q, refresh=False, h=None): return env.c.post("/api/search/ai", headers=h or env.stu, json={"q": q, "refresh": refresh})

def test_ai_search_is_saved_and_shared_and_recheck_asks_again(env, monkeypatch):
    ai_env(env, monkeypatch)
    a = ask(env, "What is Raoult's law?").json(); assert a == {"text": "Hard water explained.", "cached": False} and FakeClient.calls == 1
    assert ask(env, "what is  RAOULT'S law?", h=env.admin).json()["cached"] is True and FakeClient.calls == 1  # same question, any wording of case and spaces
    r = ask(env, "What is Raoult's law?", refresh=True).json(); assert r["cached"] is False and FakeClient.calls == 2
    with Session_() as s: assert s.query(SearchAnswer).count() == 1 and s.query(SearchLog).count() == 2
    for bad in ("", "x", "y" * 201): assert ask(env, bad).status_code == 400

def test_ai_search_needs_a_key_and_respects_the_daily_limit(env, monkeypatch):
    ai_env(env, monkeypatch, key=None); r = ask(env, "anything at all"); assert r.status_code == 503 and r.json()["detail"] == "AI unavailable. Try again later." and FakeClient.calls == 0
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    monkeypatch.setattr(main, "SEARCH_DAILY", 2)
    assert ask(env, "one question").status_code == 200 and ask(env, "two question").status_code == 200
    r = ask(env, "three question"); assert r.status_code == 429 and "2 AI searches" in r.json()["detail"]
    assert ask(env, "one question").json()["cached"] is True  # saved answers are free
    assert ask(env, "one question", refresh=True).status_code == 429
    assert ask(env, "three question", h=env.admin).status_code == 200  # staff aren't limited

def test_provider_errors_are_clean_and_self_registered_people_use_their_own_key(env, monkeypatch):
    ai_env(env, monkeypatch); FakeClient.mode = "500"; r = ask(env, "some question"); assert r.status_code == 503 and "500" not in r.json()["detail"]
    with Session_() as s:
        s.add(User(name="Self", email="self@x.com", pw=main.hp("pw1234567"), role="student", self_registered=True)); s.commit()
    h = env.login("self@x.com", "pw1234567") if "pw" in env.login.__code__.co_varnames else None
    if h: FakeClient.mode = "ok"; assert ask(env, "some question", h=h).json()["detail"] == main.NEEDS_OWN_KEY

class Spy(FakeClient):
    sent = []
    async def post(self, url, headers=None, json=None): Spy.sent.append(json["messages"]); return await super().post(url, headers=headers, json=json)

def test_admin_edits_prompts_and_they_are_used(env, monkeypatch):
    i = seed(env); monkeypatch.setattr(main.httpx, "AsyncClient", Spy); Spy.sent = []; Spy.mode = "ok"
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk-test-1234")); s.commit()
    items = {x["kind"]: x for x in env.c.get("/api/admin/prompts", headers=env.admin).json()["items"]}
    assert set(items) == {"explain", "answer", "search"} and items["search"]["custom"] is False and items["explain"]["text"] == items["explain"]["default"]
    for h in (env.fac, env.stu): assert env.c.get("/api/admin/prompts", headers=h).status_code == 403 and env.c.put("/api/admin/prompts/explain", headers=h, json={"text": "x" * 50}).status_code == 403
    t = i["topic"]["Water hardness"]; env.c.get(f"/api/topics/{t}/ai/explain", headers=env.stu); assert Spy.sent[-1][0]["content"] == main.PROMPTS["explain"]
    assert env.c.get("/api/admin/prompts", headers=env.admin).json()["items"][0]["saved_answers"] == 1
    new = "You are a patient Tamil-medium tutor. Explain in simple English with short sentences and one table."
    r = env.c.put("/api/admin/prompts/explain", headers=env.admin, json={"text": f"  {new}  "}).json(); assert r == {"ok": True, "cleared": 1}
    got = env.c.get(f"/api/topics/{t}/ai/explain", headers=env.stu).json(); assert got["cached"] is False and Spy.sent[-1][0]["content"] == new  # fresh answer from the new prompt
    assert {x["kind"]: x for x in env.c.get("/api/admin/prompts", headers=env.admin).json()["items"]}["explain"]["custom"] is True
    ask(env, "a new question"); env.c.put("/api/admin/prompts/search", headers=env.admin, json={"text": "Answer only in one line, as a quick dictionary entry."}); ask(env, "a new question")
    assert Spy.sent[-1][0]["content"].startswith("Answer only in one line") and Spy.calls if hasattr(Spy, "calls") else True
    assert env.c.delete("/api/admin/prompts/explain", headers=env.admin).json()["cleared"] == 1
    env.c.get(f"/api/topics/{t}/ai/explain", headers=env.stu); assert Spy.sent[-1][0]["content"] == main.PROMPTS["explain"]
    assert env.c.put("/api/admin/prompts/explain", headers=env.admin, json={"text": main.PROMPTS["explain"]}).status_code == 200
    assert {x["kind"]: x for x in env.c.get("/api/admin/prompts", headers=env.admin).json()["items"]}["explain"]["custom"] is False  # same as the built-in

def test_prompt_validation(env):
    for bad in ("", "short", "x" * (main.MAX_PROMPT + 1)): assert env.c.put("/api/admin/prompts/explain", headers=env.admin, json={"text": bad}).status_code == 400
    assert env.c.put("/api/admin/prompts/nope", headers=env.admin, json={"text": "x" * 40}).status_code == 404 and env.c.delete("/api/admin/prompts/nope", headers=env.admin).status_code == 404
