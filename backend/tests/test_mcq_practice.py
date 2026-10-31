# MCQ practice: the bank (admins, course-owning faculty, the AI), sets with their own copy of each question, answers kept on the server until
# submitted, Lite and Pro set limits that hold under retries and races, exactly-once results, and no MCQ access for parents.
import datetime as dt, json, re, threading
import httpx
import main
from main import Session_, User, Program, Semester, Course, Unit, Topic, Setting, GuardianLink, McqItem, McqAttempt, McqAttemptItem, McqQuota, hp

WATER = ("Hard water contains dissolved calcium and magnesium salts. Temporary hardness is removed by boiling, which turns the bicarbonates into "
         "insoluble carbonates. Permanent hardness comes from sulphates and chlorides and needs ion exchange or the lime soda process. "
         "Hardness is expressed in parts per million of calcium carbonate equivalent.")
RUST = "Corrosion is the slow destruction of a metal by its surroundings. Iron rusts when oxygen and moisture form hydrated ferric oxide on its surface."
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000002000100" "05fe02fea7d6a3500000000049454e44ae426082")

def world(env):
    """A college program (semester 1: Chem, owned by fac; semester 2: Physics, owned by fac2), two live topics and a draft in Chem, and the people."""
    with Session_() as s:
        p = Program(name="B.E.", pattern="semester"); s.add(p); s.flush()
        s1, s2 = Semester(name="Semester 1", program_id=p.id, semester_no=1), Semester(name="Semester 2", program_id=p.id, semester_no=2); s.add_all([s1, s2]); s.flush()
        fac = s.query(User).filter_by(email="fac@x.com").one(); fac2 = User(name="Fac Two", email="fac2@x.com", pw=hp("pw"), role="faculty"); s.add(fac2); s.flush()
        chem = Course(name="Chem", semester_id=s1.id, program_id=p.id, faculty_owner_id=fac.id); phys = Course(name="Physics", semester_id=s2.id, program_id=p.id, faculty_owner_id=fac2.id)
        s.add_all([chem, phys]); s.flush()
        u1, u2 = Unit(name="Water", course_id=chem.id, position=1), Unit(name="Motion", course_id=phys.id, position=1); s.add_all([u1, u2]); s.flush()
        t = [Topic(title="Water hardness", content=WATER, unit_id=u1.id, course_id=chem.id, position=1, published=True),
             Topic(title="Corrosion", content=RUST, unit_id=u1.id, course_id=chem.id, position=2, published=True),
             Topic(title="Draft topic", content=WATER, unit_id=u1.id, course_id=chem.id, position=3, published=False),
             Topic(title="Velocity", content="Velocity is displacement over time.", unit_id=u2.id, course_id=phys.id, position=1, published=True)]
        s.add_all(t); s.flush()
        s.query(User).filter_by(email="stu@x.com").update({"program_id": p.id, "semester": 1, "self_registered": True,  # a Pro student: four sets a day
                                                           "pro_until": dt.datetime.utcnow() + dt.timedelta(days=30)})
        lite = User(name="Lee Lite", email="lite@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=p.id, semester=1)
        other = User(name="Otto", email="otto@x.com", pw=hp("pw"), role="student", program_id=p.id, semester=1)
        mum = User(name="Mum", email="mum@x.com", pw=hp("pw"), role="guardian", relation="parent", self_registered=True, level="college")
        tch = User(name="Ms Rani", email="rani@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="college")
        s.add_all([lite, other, mum, tch]); s.flush()
        stu = s.query(User).filter_by(email="stu@x.com").one()
        s.add_all([GuardianLink(guardian_id=mum.id, student_id=stu.id), GuardianLink(guardian_id=tch.id, student_id=stu.id)])
        s.merge(Setting(k="deepseek_key", v="sk-test-key-123456")); s.commit()
        env.ids = {"chem": chem.id, "phys": phys.id, "water": t[0].id, "rust": t[1].id, "draft": t[2].id, "vel": t[3].id, "stu": stu.id, "lite": lite.id, "other": other.id}
    env.lite, env.other, env.mum, env.rani, env.fac2 = (env.login(e) for e in ("lite@x.com", "otto@x.com", "mum@x.com", "rani@x.com", "fac2@x.com"))
    return env.ids
def q(topic, n, status="published", **kw):
    return {"topic_id": topic, "text": f"Question {n} about hardness, $x^2$", "options": [f"Option {n}a", f"Option {n}b", f"Option {n}c", f"Option {n}d"], "correct": n % 4,
            "explanation": f"Because {n}.", "difficulty": "medium", "keywords": "hardness, calcium", "status": status, **kw}
def bank(env, topic, n=6, h=None, first=0):
    for i in range(first, first + n): assert env.c.post("/api/mcq/items", headers=h or env.fac, json=q(topic, i)).status_code == 200
def start(env, h, **b): return env.c.post("/api/mcq/attempts", headers=h, json={"mode": "topic", "source": "bank", "size": 5, **b})
def submit(env, h, aid, answers=None): return env.c.post(f"/api/mcq/attempts/{aid}/submit", headers=h, json={"answers": answers or {}})
def key_of(aid):  # the right answers, read from the server's own copy
    with Session_() as s: return {r.pos: json.loads(r.snapshot)["correct"] for r in s.query(McqAttemptItem).filter_by(attempt_id=aid)}
def quota(uid):
    with Session_() as s: return s.get(McqQuota, uid)
def shift(uid, **kw):  # moves a person's set clock, as if time had passed
    with Session_() as s: s.query(McqQuota).filter_by(user_id=uid).update(kw); s.commit()

class FakeAI:  # stands in for DeepSeek: writes questions from the notes it is sent (so they pass the topic check), or fails as told
    mode, sent, calls = "ok", [], 0
    @staticmethod
    async def run(key, model, messages, max_tokens=None, timeout=45):
        FakeAI.calls += 1; FakeAI.sent.append(messages); msg = messages[-1]["content"]
        if FakeAI.mode == "timeout": raise httpx.ReadTimeout("slow")
        if FakeAI.mode == "500": raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(500))
        if FakeAI.mode == "junk" or (FakeAI.mode == "junk-then-ok" and FakeAI.calls == 1): return "I cannot do JSON today.", 10
        notes = re.search(r"Notes:\n(.*)", msg).group(1); w = [x for x in re.findall(r"[a-z]{6,}", notes.lower())][:3]
        n = int(re.search(r"Write (\d+) questions", msg).group(1))
        qs = [{"topic": 1, "text": f"Which statement about {w[i % len(w)]} is true? ({FakeAI.calls}.{i})", "options": [f"{w[0]} {i}", f"wrong {i}", f"other {i}", f"none {i}"], "correct": 0,
               "explanation": f"The notes say {w[0]}.", "difficulty": "easy", "keywords": [w[0]]} for i in range(n)]
        if FakeAI.mode == "some-bad":  # a few broken ones among them
            qs[0]["options"] = qs[0]["options"][:3]; qs[1]["correct"] = 9; qs[2]["text"] = "Who won the football world cup in 1998?"; qs[2]["options"] = ["France", "Brazil", "Italy", "Spain"]; qs[2]["explanation"] = "Sport."
        return json.dumps({"questions": qs}), 100
def fake_ai(monkeypatch, mode="ok"): FakeAI.mode, FakeAI.sent, FakeAI.calls = mode, [], 0; monkeypatch.setattr(main, "chat", lambda k, messages, **kw: (FakeAI.run)(k.key, k.model, messages, **kw))

# ---- who may do what
def test_parents_have_no_mcq_access_and_teachers_who_follow_see_only_a_summary(env):
    i = world(env); bank(env, i["water"])
    for h in (env.mum, env.rani):
        assert env.c.get("/api/mcq/home", headers=h).status_code == 403
        assert start(env, h, topic_id=i["water"]).status_code == 403 and env.c.get("/api/mcq/attempts", headers=h).status_code == 403
        assert env.c.get("/api/mcq/items", headers=h).status_code == 403 and env.c.post("/api/mcq/generate", headers=h, json={"topic_id": i["water"]}).status_code == 403
    aid = start(env, env.stu, topic_id=i["water"]).json()["id"]; submit(env, env.stu, aid, key_of(aid))
    assert env.c.get(f"/api/mcq/attempts/{aid}", headers=env.mum).status_code == 403
    for h in (env.mum, env.rani):  # parents and teachers both see the results, never the questions themselves
        m = env.c.get(f"/api/guardian/students/{i['stu']}/progress", headers=h).json()["mcq"]; assert (m["sets"], m["average"]) == (1, 100)

def test_students_and_staff_practise_and_only_owners_and_admins_manage(env):
    i = world(env)
    assert env.c.post("/api/mcq/items", headers=env.stu, json=q(i["water"], 1)).status_code == 403  # students don't write to the bank
    assert env.c.post("/api/mcq/items", headers=env.fac2, json=q(i["water"], 1)).status_code == 403  # not fac2's course
    bank(env, i["water"]); bank(env, i["vel"], 3, h=env.fac2); bank(env, i["vel"], 1, h=env.admin, first=10)
    assert env.c.get("/api/mcq/items", headers=env.fac).json()["total"] == 6 and env.c.get("/api/mcq/items", headers=env.fac2).json()["total"] == 4
    assert env.c.get("/api/mcq/items", headers=env.admin).json()["total"] == 10
    iid = env.c.get("/api/mcq/items", headers=env.fac).json()["items"][0]["id"]
    for call in (lambda: env.c.put(f"/api/mcq/items/{iid}", headers=env.fac2, json=q(i["water"], 9)), lambda: env.c.post(f"/api/mcq/items/{iid}/status", headers=env.fac2, json={"status": "retired"}),
                 lambda: env.c.delete(f"/api/mcq/items/{iid}", headers=env.fac2)): assert call().status_code == 403
    assert env.c.put(f"/api/mcq/items/{iid}", headers=env.fac, json=q(i["vel"], 9)).status_code == 403  # nor move one into a course they don't own
    assert start(env, env.stu, topic_id=i["vel"]).status_code == 403  # not the student's semester
    assert start(env, env.stu, topic_id=i["draft"]).status_code == 404  # drafts are not practised
    h = env.c.get("/api/mcq/home", headers=env.stu).json(); assert [c["name"] for c in h["courses"]] == ["Chem"] and h["courses"][0]["questions"] == 6
    assert [t["title"] for t in h["courses"][0]["topics"]] == ["Water hardness", "Corrosion"]
    r = start(env, env.fac, topic_id=i["water"]); assert r.status_code == 200  # faculty try sets too; no limit, as with the rest of their AI
    assert submit(env, env.fac, r.json()["id"]).status_code == 200 and env.c.get("/api/mcq/home", headers=env.fac).json()["quota"]["tier"] == "none"

def test_nobody_reads_or_answers_someone_elses_set(env):
    i = world(env); bank(env, i["water"]); aid = start(env, env.stu, topic_id=i["water"]).json()["id"]
    for h in (env.other, env.lite, env.fac2):
        assert env.c.get(f"/api/mcq/attempts/{aid}", headers=h).status_code == 404
        assert env.c.put(f"/api/mcq/attempts/{aid}/answers", headers=h, json={"answers": {"0": 1}}).status_code == 404
        assert submit(env, h, aid).status_code == 404 and env.c.post(f"/api/mcq/attempts/{aid}/abandon", headers=h).status_code == 404
    assert env.c.get(f"/api/mcq/attempts/{aid}", headers=env.fac).status_code == 404  # not even the course's owner while it is open
    submit(env, env.stu, aid)
    assert env.c.get(f"/api/mcq/attempts/{aid}", headers=env.fac).status_code == 200 and env.c.get(f"/api/mcq/attempts/{aid}", headers=env.fac2).status_code == 404
    assert env.c.get("/api/mcq/attempts", headers=env.other).json()["total"] == 0

# ---- the bank: content, images, maths, versions, workflow
def test_questions_carry_maths_and_uploaded_images_but_never_outside_ones(env):
    i = world(env)
    img = env.c.post("/api/uploads", headers=env.fac, content=PNG).json()["url"]
    assert env.c.post("/api/uploads", headers=env.stu, content=PNG).status_code == 403
    assert env.c.post("/api/uploads", headers=env.fac, content=b"<svg onload=alert(1)>").status_code == 400  # only real PNG, JPG, GIF or WebP
    body = q(i["water"], 1, text="Find $\\sqrt{x}$ ![graph](" + img + ") and ![t](https://evil.example/t.png)", image=img, option_images=["", img, "", ""], explanation_image=img)
    iid = env.c.post("/api/mcq/items", headers=env.fac, json=body).json()["id"]
    x = env.c.get("/api/mcq/items", headers=env.fac).json()["items"][0]
    assert "$\\sqrt{x}$" in x["text"] and img in x["text"] and "evil.example" not in x["text"] and x["option_images"][1] == img and x["explanation_image"] == img
    for bad in ({"image": "https://evil.example/a.png"}, {"option_images": ["javascript:alert(1)"]}, {"options": ["same", "Same"]}, {"options": ["only one"]}, {"correct": 4},
                {"text": "", "image": ""}, {"difficulty": "brutal"}):
        assert env.c.post("/api/mcq/items", headers=env.fac, json={**q(i["water"], 7), **bad}).status_code == 400, bad
    assert env.c.post("/api/mcq/items", headers=env.fac, json={**q(i["water"], 2), "options": ["", "b"], "option_images": [img, ""], "correct": 0}).status_code == 200  # an answer may be only an image
    assert env.c.post("/api/mcq/items", headers=env.fac, json=body).status_code == 409  # the same question twice

def test_a_set_keeps_its_own_copy_so_later_edits_change_nothing(env):
    i = world(env); bank(env, i["water"], 3)
    aid = start(env, env.stu, topic_id=i["water"], size=3).json()["id"]; keys = key_of(aid)
    with Session_() as s: items = {r.pos: r.item_id for r in s.query(McqAttemptItem).filter_by(attempt_id=aid)}
    for pos, iid in items.items():  # every question rewritten, the right answer moved
        r = env.c.put(f"/api/mcq/items/{iid}", headers=env.fac, json={**q(i["water"], 50 + pos), "correct": (keys[pos] + 1) % 4}); assert r.json()["version"] == 2
    v = env.c.get(f"/api/mcq/attempts/{aid}", headers=env.stu).json(); assert all(x["text"].startswith("Question") and "50" not in x["text"] for x in v["questions"])
    out = submit(env, env.stu, aid, keys).json(); assert out["score"] == 3 and out["percent"] == 100  # scored on the copy it was given
    assert env.c.post(f"/api/mcq/items/{items[0]}/status", headers=env.fac, json={"status": "retired"}).status_code == 200
    assert env.c.delete(f"/api/mcq/items/{items[0]}", headers=env.fac).status_code == 409  # used in a set: retire, don't delete
    assert env.c.get(f"/api/mcq/attempts/{aid}", headers=env.stu).json()["score"] == 3
    with Session_() as s: assert s.query(McqItem).filter_by(status="published", topic_id=i["water"]).count() == 2  # a retired question is not in new sets

def test_drafts_reviews_and_retired_questions_never_reach_students_and_uploads_land_whole(env):
    i = world(env)
    r = env.c.post("/api/mcq/items/bulk", headers=env.fac, json={"items": [q(i["water"], n, "draft") for n in range(4)] + [{**q(i["water"], 9), "correct": 7}], "status": "draft"})
    assert r.status_code == 400 and env.c.get("/api/mcq/items", headers=env.fac).json()["total"] == 0  # one bad row: nothing saved
    r = env.c.post("/api/mcq/items/bulk", headers=env.fac, json={"items": [q(i["water"], n) for n in range(4)] + [q(i["water"], 0)], "status": "draft"}).json()
    assert r == {"added": 4, "skipped": 1}
    assert env.c.post("/api/mcq/items/bulk", headers=env.fac, json={"items": [q(i["vel"], 1)], "status": "draft"}).status_code == 403
    assert start(env, env.stu, topic_id=i["water"]).status_code == 409  # drafts only: not enough to practise
    for x in env.c.get("/api/mcq/items", headers=env.fac).json()["items"][:3]: env.c.post(f"/api/mcq/items/{x['id']}/status", headers=env.fac, json={"status": "published"})
    assert start(env, env.stu, topic_id=i["water"]).json()["total"] == 3

# ---- sets: no answers before submitting, scoring on the server, resume, retries, abandon
def walk(o):  # every key anywhere in a JSON value
    if isinstance(o, dict): return set(o) | {k for v in o.values() for k in walk(v)}
    if isinstance(o, list): return {k for v in o for k in walk(v)}
    return set()
def test_the_answer_key_stays_on_the_server_until_the_set_is_submitted(env):
    i = world(env); bank(env, i["water"])
    r = start(env, env.stu, topic_id=i["water"]); v = r.json(); aid = v["id"]
    for got in (v, env.c.get(f"/api/mcq/attempts/{aid}", headers=env.stu).json(), env.c.get("/api/mcq/home", headers=env.stu).json(), start(env, env.stu, topic_id=i["water"]).json()):
        assert not walk(got) & {"correct", "explanation", "explanation_image", "ok", "score", "percent", "feedback"}, got
    assert "Because" not in r.text and env.c.put(f"/api/mcq/attempts/{aid}/answers", headers=env.stu, json={"answers": {"0": 1}}).json() == {"ok": True}
    keys = key_of(aid); wrong = {p: (k + 1) % 4 for p, k in keys.items()}; wrong[0] = keys[0]; wrong[1] = None
    for bad in ({"answers": {"0": 4}}, {"answers": {"9": 1}}, {"answers": {"0": -1}}):
        assert env.c.post(f"/api/mcq/attempts/{aid}/submit", headers=env.stu, json=bad).status_code == 400
    out = env.c.post(f"/api/mcq/attempts/{aid}/submit", headers=env.stu, json={"answers": wrong, "score": 5, "percent": 100}).json()  # a score sent along is ignored
    assert (out["score"], out["total"], out["percent"]) == (1, 5, 20) and out["questions"][0]["ok"] and out["questions"][1]["chosen"] is None and not out["questions"][1]["ok"]
    assert all("correct" in x and "explanation" in x for x in out["questions"]) and out["feedback"][0]["topic"] == "Water hardness" and out["feedback"][0]["status"] == "needs_study"
    assert env.c.put(f"/api/mcq/attempts/{aid}/answers", headers=env.stu, json={"answers": {"0": 2}}).status_code == 409  # no changes after

def test_resuming_retrying_and_resubmitting_never_count_another_set(env):
    i = world(env); bank(env, i["water"]); bank(env, i["rust"])
    a = start(env, env.stu, topic_id=i["water"], request_id="req-1").json(); assert not a["resumed"] and quota(i["stu"]).used == 1
    env.c.put(f"/api/mcq/attempts/{a['id']}/answers", headers=env.stu, json={"answers": {"0": 2, "1": 3}})
    b = start(env, env.stu, mode="practice", course_id=i["chem"]).json()  # another tab, the other way in: the open set comes back
    assert b["id"] == a["id"] and b["resumed"] and [x["chosen"] for x in b["questions"]][:2] == [2, 3] and quota(i["stu"]).used == 1
    assert env.c.get("/api/mcq/home", headers=env.stu).json()["open"]["answered"] == 2
    out = submit(env, env.stu, a["id"], key_of(a["id"])).json(); again = submit(env, env.stu, a["id"], {"0": 0}).json()
    assert again["already"] and again["score"] == out["score"] == 5
    c = start(env, env.stu, topic_id=i["water"], request_id="req-1").json()  # the first request sent again after it finished: the same set, still no charge
    assert c["id"] == a["id"] and c["status"] == "submitted" and quota(i["stu"]).used == 1
    d = start(env, env.stu, mode="practice", course_id=i["chem"], request_id="req-2").json(); assert d["id"] != a["id"] and d["mode"] == "practice" and quota(i["stu"]).used == 2

def test_abandoning_ends_a_set_but_gives_nothing_back(env):
    i = world(env); bank(env, i["water"])
    a = start(env, env.lite, topic_id=i["water"]).json()
    assert env.c.post(f"/api/mcq/attempts/{a['id']}/abandon", headers=env.lite).json() == {"ok": True}
    assert submit(env, env.lite, a["id"]).status_code == 409
    r = start(env, env.lite, topic_id=i["water"]); assert r.status_code == 429 and "48 hours" in r.json()["detail"]  # Lite's one set was used
    a = start(env, env.stu, topic_id=i["water"]).json(); env.c.post(f"/api/mcq/attempts/{a['id']}/abandon", headers=env.stu)
    assert start(env, env.stu, topic_id=i["water"]).json()["id"] != a["id"] and quota(i["stu"]).used == 2

# ---- limits: Lite, one set per rolling 48 hours; Pro, four per local day; both ways in share them
def test_lite_gets_one_set_in_any_48_hours(env):
    i = world(env); bank(env, i["water"]); bank(env, i["rust"])
    h = env.c.get("/api/mcq/home", headers=env.lite).json()["quota"]; assert (h["tier"], h["limit"], h["left"], h["next_at"]) == ("lite", 1, 1, None)
    a = start(env, env.lite, topic_id=i["water"]).json(); submit(env, env.lite, a["id"])
    h = env.c.get("/api/mcq/home", headers=env.lite).json()["quota"]; assert h["left"] == 0 and h["next_at"]
    for b in ({"topic_id": i["rust"]}, {"mode": "practice", "course_id": i["chem"]}, {"mode": "practice"}):  # either way in
        r = start(env, env.lite, **b); assert r.status_code == 429 and "Lite includes one MCQ set every 48 hours" in r.json()["detail"]
    now = dt.datetime.utcnow()
    shift(i["lite"], last_at=now - dt.timedelta(hours=47, minutes=59)); assert start(env, env.lite, topic_id=i["rust"]).status_code == 429  # a new day doesn't reset it
    shift(i["lite"], last_at=now - dt.timedelta(hours=48, minutes=1)); assert start(env, env.lite, topic_id=i["rust"]).status_code == 200

def test_pro_gets_four_sets_a_local_day_across_both_ways_in(env):
    i = world(env); bank(env, i["water"]); bank(env, i["rust"])
    for n, b in enumerate(({"topic_id": i["water"]}, {"mode": "practice", "course_id": i["chem"]}, {"topic_id": i["rust"]}, {"mode": "practice"})):
        a = start(env, env.stu, **b); assert a.status_code == 200, a.text; submit(env, env.stu, a.json()["id"])
        assert env.c.get("/api/mcq/home", headers=env.stu).json()["quota"]["left"] == 3 - n
    r = start(env, env.stu, topic_id=i["water"]); assert r.status_code == 429 and "today's 4 MCQ sets" in r.json()["detail"]
    h = env.c.get("/api/mcq/home", headers=env.stu).json()["quota"]; assert h["next_at"] == main.iso(main.day_start(main.local_day(dt.datetime.utcnow()) + dt.timedelta(days=1)))
    shift(i["stu"], day=main.local_day(dt.datetime.utcnow()) - dt.timedelta(days=1)); assert start(env, env.stu, topic_id=i["water"]).status_code == 200

def test_the_pro_day_turns_at_local_midnight_not_utc_midnight(env, monkeypatch):
    i = world(env); monkeypatch.setattr(main, "DAY_OFFSET", 330)  # India: the local day starts at 18:30 UTC
    with Session_() as s:
        u = s.get(User, i["stu"]); before = dt.datetime(2026, 3, 1, 18, 29); after = dt.datetime(2026, 3, 1, 18, 31)
        for _ in range(4): main.mcq_reserve(u, s, before); s.commit()
        try: main.mcq_reserve(u, s, before + dt.timedelta(seconds=30)); assert False, "a fifth set the same local day"
        except main.HTTPException as e: assert e.status_code == 429
        assert main.mcq_quota(u, s, before)["next_at"] == "2026-03-01T18:30:00Z"
        u = s.get(User, i["stu"]); assert main.mcq_reserve(u, s, after) == "pro"; s.commit()  # 00:01 in India: a new day, though still 1 March in UTC
        assert main.mcq_quota(u, s, after)["used"] == 1

def test_a_set_that_fails_to_be_made_gives_its_count_back(env, monkeypatch):
    i = world(env); bank(env, i["water"], 2)
    assert start(env, env.lite, topic_id=i["water"]).status_code == 409 and quota(i["lite"]) is None  # too few questions: nothing counted
    with Session_() as s:
        u = s.get(User, i["lite"]); main.mcq_reserve(u, s, dt.datetime.utcnow()); s.rollback()  # the attempt could not be written: the rollback gives the set back
    assert quota(i["lite"]) is None or quota(i["lite"]).last_at is None
    bank(env, i["water"], 4, first=2)
    def broken(self, rows): raise main.IntegrityError("x", {}, Exception("disk"))  # writing the set's questions fails, after the set was counted
    monkeypatch.setattr(main.Session, "add_all", broken)
    r = start(env, env.lite, topic_id=i["water"]); assert r.status_code == 409 and quota(i["lite"]).last_at is None  # given back
    monkeypatch.undo(); assert start(env, env.lite, topic_id=i["water"]).status_code == 200

def test_races_between_tabs_and_devices_never_give_an_extra_set(env):
    i = world(env); bank(env, i["water"]); bank(env, i["rust"])
    shift_used = lambda n: shift(i["stu"], day=main.local_day(dt.datetime.utcnow()), used=n, last_at=dt.datetime.utcnow())
    start(env, env.stu, topic_id=i["water"]); env.c.post("/api/mcq/attempts/1/abandon", headers=env.stu); shift_used(3)  # one set left today
    got = []
    def go(k):
        with Session_() as s:
            u = s.get(User, i["stu"])
            try: main.mcq_reserve(u, s, dt.datetime.utcnow()); s.commit(); got.append(k)
            except main.HTTPException: pass
    ts = [threading.Thread(target=go, args=(k,)) for k in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    assert len(got) == 1 and quota(i["stu"]).used == 4  # eight at once, one through
    shift_used(0); res = []
    def tab(k): res.append(start(env, env.stu, topic_id=i["water"] if k % 2 else i["rust"]).json())
    ts = [threading.Thread(target=tab, args=(k,)) for k in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
    ids_ = {r["id"] for r in res if "id" in r}; assert len(ids_) == 1 and quota(i["stu"]).used == 1  # six tabs: one set, counted once
    with Session_() as s: assert s.query(McqAttempt).filter_by(user_id=i["stu"], status="open").count() == 1

def test_a_set_is_scored_and_added_to_progress_exactly_once(env):
    i = world(env); bank(env, i["water"])
    aid = start(env, env.stu, topic_id=i["water"]).json()["id"]; keys = key_of(aid); outs = []
    ts = [threading.Thread(target=lambda: outs.append(submit(env, env.stu, aid, keys).json())) for _ in range(5)]; [t.start() for t in ts]; [t.join() for t in ts]
    assert {o.get("score") for o in outs} == {5} and sum(not o.get("already") for o in outs) == 1
    with Session_() as s:
        assert sum(main.study_days(s, i["stu"], main.local_day(dt.datetime.utcnow())).values()) == 1  # the streak counts the set once
        assert main.mcq_topic_stats(s, i["stu"]) == {i["water"]: {"answered": 5, "correct": 5, "percent": 100}}
    assert env.c.get("/api/me/today", headers=env.stu).json()["streak"] == 1
    t = env.c.get("/api/mcq/home", headers=env.stu).json()["courses"][0]["topics"][0]; assert t["stats"]["percent"] == 100
    assert env.c.get("/api/mcq/attempts", headers=env.stu).json()["items"][0]["percent"] == 100

# ---- the AI: context, checks, failures
def test_an_ai_set_is_written_from_the_topic_and_the_students_own_results(env, monkeypatch):
    i = world(env); fake_ai(monkeypatch); bank(env, i["water"])
    a = start(env, env.stu, topic_id=i["water"]).json(); keys = key_of(a["id"]); submit(env, env.stu, a["id"], {p: (k + 1) % 4 for p, k in keys.items()})  # all wrong
    shift(i["stu"], used=0)
    r = start(env, env.stu, topic_id=i["water"], source="ai", size=5); assert r.status_code == 200, r.text
    v = r.json(); assert v["source"] == "ai" and v["total"] == 5 and not walk(v) & {"correct", "explanation"}
    msg = FakeAI.sent[-1][-1]["content"]; system = FakeAI.sent[-1][0]["content"]
    assert "Water hardness" in msg and "calcium and magnesium" in msg and "Program: B.E." in msg and "Course: Chem" in msg and "Unit: Water" in msg
    assert "This student scores 0% on this topic" in msg and "hardness" in msg.split("they miss questions on:")[1]
    assert not any(x in msg for x in ("stu@x.com", "Otto", "Lee Lite", "fac@x.com")) and "Their class" not in msg  # no names; too few classmates for a class figure
    assert "strictly from the topic notes" in system
    with Session_() as s:
        rows = s.query(McqItem).filter_by(source="ai").all(); assert len(rows) == 5 and {x.status for x in rows} == {"review"} and {x.author_id for x in rows} == {None}
    assert quota(i["stu"]).used == 1 and env.c.get("/api/me/plan", headers=env.stu).json()["plan"] == "pro"
    submit(env, env.stu, v["id"]); shift(i["stu"], used=0)
    o = start(env, env.other, topic_id=i["water"], size=20).json()  # AI questions wait for review: other students get only published ones
    with Session_() as s: assert o["total"] == 6 and {s.get(McqItem, r.item_id).source for r in s.query(McqAttemptItem).filter_by(attempt_id=o["id"])} == {"teacher"}

def test_class_figures_go_to_the_ai_only_from_five_classmates_and_lite_minutes_are_not_used(env, monkeypatch):
    i = world(env); fake_ai(monkeypatch); bank(env, i["water"])
    with Session_() as s:
        p = s.get(User, i["stu"])
        for n in range(5): s.add(User(name=f"Mate {n}", email=f"m{n}@x.com", pw=hp("pw"), role="student", program_id=p.program_id, semester=1))
        s.commit()
    for n in range(5):
        h = env.login(f"m{n}@x.com"); aid = start(env, h, topic_id=i["water"]).json()["id"]; submit(env, h, aid, key_of(aid) if n % 2 else {})
    r = start(env, env.lite, topic_id=i["water"], source="ai", size=5); assert r.status_code == 200, r.text
    msg = FakeAI.sent[-1][-1]["content"]; assert "Their class averages 40% on this topic" in msg and "Mate" not in msg
    p = env.c.get("/api/me/plan", headers=env.lite).json(); assert p["minutes_used"] == 0 and p["searches_used"] == 0  # a set is counted as a set, not as Lite time

def test_the_ais_questions_are_checked_and_bad_ones_dropped(env):
    i = world(env)
    with Session_() as s: t = s.get(Topic, i["water"]); words = [main.mcq_words(t.content)]
    good = {"topic": 1, "text": "What causes temporary hardness?", "options": ["Bicarbonates", "Sulphates", "Chlorides", "Nitrates"], "correct": "A",
            "explanation": "Boiling turns bicarbonates into carbonates.", "difficulty": "Easy", "keywords": ["hardness"]}
    bad = [{**good, "options": good["options"][:3]}, {**good, "correct": 7}, {**good, "options": ["a", "a", "b", "c"]}, {**good, "explanation": ""},
           {**good, "difficulty": "impossible"}, {**good, "text": "Who painted the Mona Lisa?", "options": ["Leonardo", "Picasso", "Monet", "Dali"], "explanation": "Art history."},
           {**good, "text": ""}, "not a question", {**good, "correct": None}]
    out = main.mcq_ai_valid({"questions": [good] + bad + [good]}, [t], words, set())
    assert len(out) == 1 and out[0]["correct"] == 0 and out[0]["difficulty"] == "easy"  # the duplicate is dropped too
    assert main.mcq_ai_valid("[]", [t], words, set()) == [] and main.mcq_ai_valid({"questions": "x"}, [t], words, set()) == []

def test_ai_failures_lose_nothing_and_count_nothing(env, monkeypatch):
    i = world(env)
    for mode, code in (("timeout", 503), ("500", 503), ("junk", 502)):
        fake_ai(monkeypatch, mode); r = start(env, env.lite, topic_id=i["water"], source="ai", size=5)
        assert r.status_code == code and quota(i["lite"]) is None, (mode, r.text)
    assert FakeAI.calls == 2  # unreadable twice: one bounded retry, no more
    fake_ai(monkeypatch, "junk-then-ok"); assert start(env, env.lite, topic_id=i["water"], source="ai", size=5).status_code == 200 and FakeAI.calls == 2
    fake_ai(monkeypatch, "some-bad"); shift(i["lite"], last_at=None); r = start(env, env.stu, topic_id=i["rust"], source="ai", size=5)
    assert r.status_code == 200 and r.json()["total"] == 4 and FakeAI.calls == 2  # three dropped each time: one more try, then the 4 good ones (half or more is a set)
    with Session_() as s: s.query(Topic).filter_by(id=i["vel"]).update({"content": "Tiny."}); s.commit()
    r = env.c.post("/api/mcq/generate", headers=env.fac2, json={"topic_id": i["vel"]}); assert r.status_code == 400 and "enough notes" in r.json()["detail"]  # nothing to write from
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="")); s.commit()
    assert start(env, env.other, topic_id=i["water"], source="ai").status_code == 503  # no key: AI sets are off, the bank still works

def test_staff_ai_drafts_wait_for_review_and_carry_no_student_data(env, monkeypatch):
    i = world(env); fake_ai(monkeypatch)
    assert env.c.post("/api/mcq/generate", headers=env.fac2, json={"topic_id": i["water"]}).status_code == 403
    r = env.c.post("/api/mcq/generate", headers=env.fac, json={"topic_id": i["water"], "count": 4}).json(); assert r["added"] == 4
    assert "This student" not in FakeAI.sent[-1][-1]["content"] and env.c.get("/api/mcq/items?status=review", headers=env.fac).json()["total"] == 4
    assert env.c.get("/api/mcq/home", headers=env.fac).json()["quota"]["tier"] == "none" and quota(main.Session_().query(User).filter_by(email="fac@x.com").one().id) is None

# ---- the schema: new tables only, applied once, nothing else touched
def test_the_migration_adds_only_new_tables_and_is_safe_to_run_again(env):
    i = world(env); bank(env, i["water"])
    with Session_() as s: before = (s.query(User).count(), s.query(Topic).count(), s.query(McqItem).count())
    main.upgrade_schema(); main.upgrade_schema()
    with Session_() as s: assert (s.query(User).count(), s.query(Topic).count(), s.query(McqItem).count()) == before
    assert main.applied_migrations().count("0029_mcq_practice") == 1
    tables = set(main.inspect(main.engine).get_table_names()); assert {"mcq_items", "mcq_attempts", "mcq_attempt_items", "mcq_quota"} <= tables

def test_deleting_a_student_takes_their_sets_with_them(env):
    i = world(env); bank(env, i["water"]); aid = start(env, env.other, topic_id=i["water"]).json()["id"]
    assert env.c.delete(f"/api/admin/users/{i['other']}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.query(McqAttempt).filter_by(id=aid).count() == 0 and s.query(McqAttemptItem).filter_by(attempt_id=aid).count() == 0

def test_a_save_that_lands_after_the_submit_changes_nothing_and_lists_are_bounded(env):
    i = world(env); bank(env, i["water"]); aid = start(env, env.stu, topic_id=i["water"]).json()["id"]; keys = key_of(aid)
    out = submit(env, env.stu, aid, keys).json(); assert out["score"] == 5
    assert env.c.put(f"/api/mcq/attempts/{aid}/answers", headers=env.stu, json={"answers": {"0": (keys[0] + 1) % 4}}).status_code == 409
    with Session_() as s: assert s.query(McqAttemptItem).filter_by(attempt_id=aid, pos=0).one().chosen == keys[0]
    assert env.c.post("/api/mcq/items", headers=env.fac, json={**q(i["water"], 30), "options": [str(n) for n in range(7)]}).status_code == 400
    assert env.c.put(f"/api/mcq/attempts/{aid}/answers", headers=env.stu, json={"answers": {str(n): 0 for n in range(25)}}).status_code in (400, 409)

def test_ai_sets_are_capped_per_hour_and_carry_no_links(env, monkeypatch):
    i = world(env); fake_ai(monkeypatch, "junk")
    for _ in range(3): assert start(env, env.stu, topic_id=i["water"], source="ai", size=5).status_code == 502  # two calls each: six this hour
    r = start(env, env.stu, topic_id=i["water"], source="ai", size=5); assert r.status_code == 429 and "this hour" in r.json()["detail"] and FakeAI.calls == 6
    assert start(env, env.stu, topic_id=i["water"], size=5).status_code == 409  # the bank is still there (empty here), unaffected by the cap
    with Session_() as s: t = s.get(Topic, i["water"]); words = [main.mcq_words(t.content)]
    raw = {"questions": [{"topic": 1, "text": "Which [salt](https://evil.example) causes hardness? ![x](https://evil.example/a.png)", "options": ["Calcium", "Gold", "Neon", "Argon"],
                          "correct": 0, "explanation": "See [here](javascript:alert(1)): calcium salts.", "difficulty": "easy", "keywords": "hardness"}]}
    x = main.mcq_ai_valid(raw, [t], words, set())[0]; assert "evil" not in x["text"] + x["explanation"] and "javascript" not in x["explanation"] and "salt" in x["text"]

def test_only_students_on_lite_or_pro_have_a_limit(env):
    i = world(env); bank(env, i["water"])
    with Session_() as s:  # a student with their own key, and a school child with no family key
        s.add(User(name="Own Key", email="own@x.com", pw=hp("pw"), role="student", self_registered=True, ai_key=main.seal("sk-own-123456789012"), program_id=s.get(User, i["stu"]).program_id, semester=1))
        s.commit()
    plans = {who: env.c.get("/api/mcq/home", headers=h).json()["quota"] for who, h in (("lite", env.lite), ("pro", env.stu), ("college", env.other), ("own", env.login("own@x.com")), ("admin", env.admin), ("fac", env.fac))}
    assert (plans["lite"]["tier"], plans["lite"]["limit"]) == ("lite", 1) and (plans["pro"]["tier"], plans["pro"]["limit"]) == ("pro", 4)
    assert all(plans[w]["tier"] == "none" and plans[w]["left"] is None for w in ("college", "own", "admin", "fac"))
    h = env.other  # a student the college added: as many sets as they like
    for _ in range(6):
        r = start(env, h, topic_id=i["water"]); assert r.status_code == 200, r.text; submit(env, h, r.json()["id"])
    assert quota(i["other"]) is None

def test_teachers_publish_or_dismiss_every_waiting_question_at_once(env, monkeypatch):
    i = world(env); fake_ai(monkeypatch); bank(env, i["water"])
    a = start(env, env.stu, topic_id=i["water"], source="ai", size=5).json(); submit(env, env.stu, a["id"])  # 5 AI questions now wait, and this student had them
    env.c.post("/api/mcq/generate", headers=env.fac, json={"topic_id": i["rust"], "count": 3})  # 3 more, on another topic, that nobody has had
    with Session_() as s: s.query(Topic).filter_by(id=i["vel"]).update({"content": "Velocity measures displacement divided by elapsed time. Acceleration measures velocity change divided by elapsed time; uniform motion keeps velocity constant."}); s.commit()
    assert env.c.post("/api/mcq/generate", headers=env.fac2, json={"topic_id": i["vel"], "count": 3}).json()["added"] == 3  # fac2's own: fac can't touch them
    waiting = lambda h, **k: env.c.get("/api/mcq/items?status=review" + "".join(f"&{a}={b}" for a, b in k.items()), headers=h).json()["total"]
    assert (waiting(env.fac), waiting(env.fac2)) == (8, 3)
    assert env.c.post("/api/mcq/items/review", headers=env.stu, json={"action": "publish"}).status_code == 403
    assert env.c.post("/api/mcq/items/review", headers=env.fac, json={"action": "approve"}).status_code == 400
    r = env.c.post("/api/mcq/items/review", headers=env.fac, json={"action": "dismiss", "topic_id": i["rust"]}).json()
    assert r == {"published": 0, "retired": 0, "deleted": 3} and waiting(env.fac) == 5  # one topic only; never used, so gone
    r = env.c.post("/api/mcq/items/review", headers=env.fac, json={"action": "dismiss", "course_id": i["chem"]}).json()
    assert r == {"published": 0, "retired": 5, "deleted": 0} and waiting(env.fac) == 0  # a student had them: kept as retired, so the result stays
    assert env.c.get(f"/api/mcq/attempts/{a['id']}", headers=env.stu).json()["score"] is not None
    r = env.c.post("/api/mcq/items/review", headers=env.fac, json={"action": "publish"}).json(); assert r["published"] == 0 and waiting(env.fac2) == 3  # not fac's to publish
    assert env.c.post("/api/mcq/items/review", headers=env.fac2, json={"action": "publish"}).json()["published"] == 3 and env.c.get("/api/mcq/items?status=published", headers=env.fac2).json()["total"] == 3
