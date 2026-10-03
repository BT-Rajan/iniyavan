import csv, io
from main import Session_, User, Topic, Attempt, Progress, Quiz
from tests.test_access import CSV, ids, enrol
from tests.test_quiz_reports import setup

def two_topic_quiz(env, unit, tag=True, extra=None):
    env.c.post("/api/topics", headers=env.admin, json={"title": "Boilers", "unit_id": unit, "content": "b"})
    with Session_() as s: t = {x.title: x.id for x in s.query(Topic).filter_by(unit_id=unit)}
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": unit, "title": "Mixed", "pass_percent": 50, "published": True}).json()["id"]
    Q = lambda text, tid: {"text": text, "options": ["right", "wrong"], "correct": 0, "topic_id": tid if tag else None}
    r = env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [Q("w1", t["Water"]), Q("w2", t["Water"]), Q("b1", t["Boilers"]), Q("b2", t["Boilers"]), Q("b3", t["Boilers"])]})
    assert r.status_code == 200, r.text
    return q, t
def take(env, h, q, answers): return env.c.post(f"/api/quizzes/{q}/attempt", headers=h, json={"answers": answers}).json()
def me_id(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id

def test_attempt_result_names_strong_and_weak_topics_without_the_answer_key(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit)
    with Session_() as s: s.add(Progress(user_id=me_id("stu@x.com"), topic_id=t["Water"], reads=1)); s.commit()
    r = take(env, env.stu, q, [0, 0, 1, 1, 0])
    by = {a["title"]: a for a in r["areas"]}
    assert (by["Water"]["status"], by["Water"]["percent"], by["Water"]["study"]) == ("strong", 100, "in_progress")
    assert (by["Boilers"]["status"], by["Boilers"]["correct"], by["Boilers"]["total"], by["Boilers"]["study"], by["Boilers"]["topic_id"]) == ("needs_study", 1, 3, "not_started", t["Boilers"])
    assert [a["title"] for a in r["areas"]][0] == "Boilers"  # weakest first
    assert all("correct" not in x and "explanation" not in x for x in r["results"])  # still no answer key for students

def test_insights_use_the_latest_attempt_so_retaking_improves_the_status(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit)
    take(env, env.stu, q, [0, 0, 1, 1, 1])
    ins = env.c.get("/api/me/insights", headers=env.stu).json()
    assert [a["title"] for a in ins["needs_study"]] == ["Boilers"] and [a["title"] for a in ins["strong"]] == ["Water"] and ins["courses"][0]["percent"] == 40 and ins["quizzes_taken"] == 1
    take(env, env.stu, q, [0, 0, 0, 0, 1])  # Boilers now 2 of 3 = 67%
    ins = env.c.get("/api/me/insights", headers=env.stu).json(); assert ins["needs_study"] == [] and [a["title"] for a in ins["getting_there"]] == ["Boilers"]
    take(env, env.stu, q, [0, 0, 0, 0, 0]); ins = env.c.get("/api/me/insights", headers=env.stu).json(); assert ins["courses"][0]["percent"] == 100 and len(ins["strong"]) == 2

def test_untagged_questions_fall_back_to_the_unit_and_deleted_or_moved_topics_too(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit, tag=False); take(env, env.stu, q, [1, 1, 1, 1, 1])
    a = env.c.get("/api/me/insights", headers=env.stu).json()["needs_study"]; assert len(a) == 1 and a[0]["topic_id"] is None and a[0]["title"].endswith("general questions") and a[0]["study"] is None
    q2, t2 = two_topic_quiz(env, unit); take(env, env.stu, q2, [0, 0, 1, 1, 1])
    env.c.delete(f"/api/topics/{t2['Boilers']}", headers=env.admin)
    areas = env.c.get("/api/me/insights", headers=env.stu).json()["courses"][0]["areas"]; assert all(x["topic_id"] != t2["Boilers"] for x in areas)

def test_a_draft_topic_is_not_named_to_students(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit); take(env, env.stu, q, [0, 0, 1, 1, 1])
    with Session_() as s: s.query(Topic).filter_by(id=t["Boilers"]).update({"published": False}); s.commit()
    assert all("Boilers" not in a["title"] for a in env.c.get("/api/me/insights", headers=env.stu).json()["needs_study"])
    assert any(a["title"] == "Boilers" for a in take(env, env.admin, q, [0, 0, 1, 1, 1])["areas"])  # staff still see it

def test_the_topic_tag_must_belong_to_the_quizs_unit_and_only_staff_see_it(env):
    i, unit = setup(env); other = i["topic"]["Tools"]; q, _ = two_topic_quiz(env, unit)
    r = env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [{"text": "x", "options": ["a", "b"], "correct": 0, "topic_id": other}]}); assert r.status_code == 400
    staff, stu = env.c.get(f"/api/quizzes/{q}", headers=env.admin).json(), env.c.get(f"/api/quizzes/{q}", headers=env.stu).json()
    assert "topic_id" in staff["questions"][0] and {x["title"] for x in staff["topics"]} == {"Water", "Boilers"} and "topic_id" not in stu["questions"][0] and "topics" not in stu

def test_old_attempts_unpublished_quizzes_and_other_programs_are_ignored(env):
    i, unit = setup(env); q, t = two_topic_quiz(env, unit)
    with Session_() as s: s.add(Attempt(quiz_id=q, user_id=me_id("stu@x.com"), score=1, total=5, percent=20)); s.commit()  # from before per-question results were kept
    assert env.c.get("/api/me/insights", headers=env.stu).json()["courses"] == []
    take(env, env.stu, q, [1, 1, 1, 1, 1]); assert env.c.get("/api/me/insights", headers=env.stu).json()["quizzes_taken"] == 1
    env.c.put(f"/api/quizzes/{q}", headers=env.admin, json={"title": "Mixed", "pass_percent": 50, "published": False}); assert env.c.get("/api/me/insights", headers=env.stu).json()["courses"] == []
    env.c.put(f"/api/quizzes/{q}", headers=env.admin, json={"title": "Mixed", "pass_percent": 50, "published": True}); enrol("stu@x.com", i["prog"]["Civil"], 1)
    assert env.c.get("/api/me/insights", headers=env.stu).json()["courses"] == []  # no longer in the course's program

def test_class_view_and_student_report_for_staff_only(env):
    i, unit = setup(env); env.add_user("stu2@x.com", program=i["prog"]["Mech"], semester=1); h2 = env.login("stu2@x.com"); q, t = two_topic_quiz(env, unit)
    take(env, env.stu, q, [0, 0, 1, 1, 0]); take(env, h2, q, [1, 0, 1, 1, 1])
    cid = i["course"]["Chem"]; r = env.c.get(f"/api/reports/courses/{cid}/weak-areas", headers=env.admin).json()
    boil, water = r["areas"][0], r["areas"][1]
    assert r["students_with_results"] == 2 and (boil["title"], boil["correct"], boil["total"], boil["students"], boil["needs_study"]) == ("Boilers", 1, 6, 2, 2)
    assert (water["title"], water["correct"], water["total"], water["percent"], water["strong"], water["needs_study"]) == ("Water", 3, 4, 75, 1, 1)
    rows = {x["email"]: x for x in env.c.get(f"/api/reports/courses/{cid}/students", headers=env.admin).json()["students"]}
    assert (rows["stu@x.com"]["strong"], rows["stu@x.com"]["needs_study"]) == (["Water"], ["Boilers"]) and (rows["stu2@x.com"]["strong"], rows["stu2@x.com"]["needs_study"]) == ([], ["Boilers", "Water"])
    text = env.c.get(f"/api/reports/courses/{cid}/students?format=csv", headers=env.admin).text.lstrip("﻿"); head = next(csv.reader(io.StringIO(text)))
    assert head[-2:] == ["Strong areas", "Needs another round of study"]
    assert env.c.get(f"/api/reports/courses/{cid}/weak-areas", headers=env.stu).status_code == 403
    assert env.c.get(f"/api/reports/courses/{i['course']['Workshop']}/weak-areas", headers=env.fac).status_code == 403

def test_migrations_add_the_new_columns(env):
    import main
    from sqlalchemy import inspect
    cols = lambda t: {c["name"] for c in inspect(main.engine).get_columns(t)}
    assert "topic_id" in cols("quiz_questions") and "detail" in cols("quiz_attempts") and "0014_attempts_detail" in main.applied_migrations()
