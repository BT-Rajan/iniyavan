from main import Session_, Question, BankQuestion
from tests.test_quiz_reports import setup, make_quiz, QS

Q = {"text": "Which gas makes water acidic?", "options": ["CO2", "N2"], "correct": 0, "explanation": "Carbonic acid.", "tags": "Water, Acids ", "source": "Chem notes"}

def test_save_a_quiz_to_the_bank_skips_duplicates_and_keeps_the_source(env):
    i, unit = setup(env); q = make_quiz(env, unit, env.fac)
    r = env.c.post(f"/api/bank/from-quiz/{q}", headers=env.fac, json={"tags": "Water"}).json(); assert r == {"added": 2, "skipped": 0}
    assert env.c.post(f"/api/bank/from-quiz/{q}", headers=env.fac, json={}).json() == {"added": 0, "skipped": 2}
    b = env.c.get("/api/bank", headers=env.admin).json(); assert b["total"] == 2 and b["tags"] == ["water"]
    x = next(v for v in b["items"] if v["text"].startswith("Which ion")); assert x["owner"] == "fac@x.com" and x["source"].endswith("Water quiz") and x["correct"] == 0 and x["can_edit"] is True
    assert env.c.post(f"/api/bank/from-quiz/{q}", headers=env.stu, json={}).status_code == 403

def test_only_staff_use_the_bank_and_validation_applies(env):
    setup(env)
    assert env.c.get("/api/bank", headers=env.stu).status_code == 403 and env.c.post("/api/bank", headers=env.stu, json=Q).status_code == 403
    for bad in ({"text": " "}, {"options": ["only"]}, {"options": ["a", ""]}, {"correct": 5}): assert env.c.post("/api/bank", headers=env.fac, json={**Q, **bad}).status_code == 400
    assert env.c.post("/api/bank", headers=env.fac, json=Q).status_code == 200 and env.c.post("/api/bank", headers=env.admin, json=Q).status_code == 409

def test_search_and_filter(env):
    setup(env); env.c.post("/api/bank", headers=env.fac, json=Q); env.c.post("/api/bank", headers=env.admin, json={**Q, "text": "Unit of power?", "options": ["W", "J"], "tags": "physics", "source": ""})
    g = lambda **p: env.c.get("/api/bank", headers=env.fac, params=p).json()
    assert g()["total"] == 2 and g(q="acidic")["total"] == 1 and g(q="gas water")["total"] == 1 and g(tag="physics")["total"] == 1 and g(q="chem")["total"] == 1 and g(mine=True)["total"] == 1
    assert g(q="100%")["total"] == 0 and g(limit=1)["items"].__len__() == 1 and g(limit=1, offset=1)["total"] == 2

def test_only_the_owner_or_an_admin_changes_or_deletes(env):
    setup(env); env.add_user("fac2@x.com", "faculty"); f2 = env.login("fac2@x.com")
    env.c.post("/api/bank", headers=env.fac, json=Q); bid = env.c.get("/api/bank", headers=env.fac).json()["items"][0]["id"]
    assert env.c.get("/api/bank", headers=f2).json()["items"][0]["can_edit"] is False  # everyone sees it; only the owner edits
    assert env.c.put(f"/api/bank/{bid}", headers=f2, json=Q).status_code == 403 and env.c.delete(f"/api/bank/{bid}", headers=f2).status_code == 403
    assert env.c.put(f"/api/bank/{bid}", headers=env.fac, json={**Q, "text": "Edited?"}).status_code == 200
    assert env.c.put(f"/api/bank/{bid}", headers=env.admin, json={**Q, "text": "Edited by admin?"}).status_code == 200
    env.c.post("/api/bank", headers=env.fac, json={**Q, "text": "Other?"}); other = [x for x in env.c.get("/api/bank", headers=env.fac).json()["items"] if x["text"] == "Other?"][0]["id"]
    assert env.c.put(f"/api/bank/{bid}", headers=env.fac, json={**Q, "text": "Other?"}).status_code == 409  # can't become a duplicate
    assert env.c.delete(f"/api/bank/{other}", headers=env.admin).status_code == 200 and env.c.delete(f"/api/bank/{other}", headers=env.admin).status_code == 404

def test_adding_from_the_bank_copies_questions_and_respects_ownership_and_limits(env):
    i, unit = setup(env); q = make_quiz(env, unit, env.fac); env.c.post("/api/bank", headers=env.admin, json=Q)
    bid = env.c.get("/api/bank", headers=env.fac).json()["items"][0]["id"]; url = f"/api/quizzes/{q}/questions/from-bank"
    tid = i["topic"]["Water"]
    assert env.c.post(url, headers=env.stu, json={"ids": [bid]}).status_code == 403
    env.add_user("fac2@x.com", "faculty"); assert env.c.post(url, headers=env.login("fac2@x.com"), json={"ids": [bid]}).status_code == 403  # not their course
    assert env.c.post(url, headers=env.fac, json={"ids": []}).status_code == 400 and env.c.post(url, headers=env.fac, json={"ids": [999]}).status_code == 404
    assert env.c.post(url, headers=env.fac, json={"ids": [bid], "topic_id": 99999}).status_code == 400
    r = env.c.post(url, headers=env.fac, json={"ids": [bid, bid], "topic_id": tid}); assert r.status_code == 200 and r.json()["count"] == 3
    got = env.c.get(f"/api/quizzes/{q}", headers=env.fac).json()["questions"]; assert got[-1]["text"] == Q["text"] and got[-1]["topic_id"] == tid and got[-1]["correct"] == 0
    env.c.put(f"/api/bank/{bid}", headers=env.admin, json={**Q, "text": "Changed later?"}); env.c.delete(f"/api/bank/{bid}", headers=env.admin)
    assert env.c.get(f"/api/quizzes/{q}", headers=env.fac).json()["questions"][-1]["text"] == Q["text"]  # live quizzes are copies
    with Session_() as s: assert s.query(Question).filter_by(quiz_id=q).count() == 3
    env.c.post("/api/bank", headers=env.admin, json=Q); b2 = env.c.get("/api/bank", headers=env.fac).json()["items"][0]; assert b2["uses"] == 0
    env.c.post(url, headers=env.fac, json={"ids": [b2["id"]]}); assert env.c.get("/api/bank", headers=env.fac).json()["items"][0]["uses"] == 1
    with Session_() as s:
        for n in range(97): s.add(Question(quiz_id=q, pos=10 + n, text="x", options="[\"a\",\"b\"]", correct=0))
        s.commit()
    assert env.c.post(url, headers=env.fac, json={"ids": [b2["id"]]}).status_code == 400
