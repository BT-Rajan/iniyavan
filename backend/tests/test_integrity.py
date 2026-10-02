"""Regression tests for hierarchy integrity and access control found in the forensic audit."""
import pytest
from main import Session_, User, Semester, Course, Topic
from tests.test_access import CSV, ids, enrol, titles

def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def assign(env, email, *course_ids):
    assert env.c.put(f"/api/admin/users/{uid(email)}/courses", headers=env.admin, json={"course_ids": list(course_ids)}).status_code == 200
def two_faculty(env):
    """fac@x.com edits Chem, fac2@x.com edits Workshop (both Mech, Semester 1)."""
    env.csv(CSV); i = ids(); env.add_user("fac2@x.com", "faculty"); env.fac2 = env.login("fac2@x.com")
    assign(env, "fac@x.com", i["course"]["Chem"]); assign(env, "fac2@x.com", i["course"]["Workshop"])
    return i
def edit_topic(env, h, tid, unit_id, title="Water"):
    return env.c.put(f"/api/topics/{tid}", headers=h, json={"title": title, "unit_id": unit_id, "content": "edited"}).status_code

# A. Semester re-parenting
@pytest.mark.xfail(strict=True, reason="audit: moving a semester leaves Course.program_id stale")
def test_semester_move_keeps_courses_consistent(env):
    env.csv(CSV); i = ids(); mech1, civil = i["sem"][(i["prog"]["Mech"], "Semester 1")], i["prog"]["Civil"]
    assert env.c.put(f"/api/semesters/{mech1}", headers=env.admin, json={"name": "Semester 1", "program_id": civil}).status_code == 200
    with Session_() as s:
        for c in s.query(Course).filter_by(semester_id=mech1): assert c.program_id == civil == s.get(Semester, c.semester_id).program_id
    enrol("stu@x.com", civil, 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403

@pytest.mark.xfail(strict=True, reason="audit: semester edit accepts a program that does not exist")
def test_semester_cannot_move_to_missing_program(env):
    env.csv(CSV); i = ids(); mech1 = i["sem"][(i["prog"]["Mech"], "Semester 1")]
    assert env.c.put(f"/api/semesters/{mech1}", headers=env.admin, json={"name": "S", "program_id": 99999}).status_code == 400

@pytest.mark.xfail(strict=True, reason="audit: student access trusts the copied Course.program_id")
def test_student_access_ignores_stale_course_program_id(env):
    env.csv(CSV); i = ids(); civil = i["prog"]["Civil"]
    with Session_() as s: s.get(Course, i["course"]["Chem"]).program_id = civil; s.commit()  # drift left behind by an old semester move
    enrol("stu@x.com", civil, 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200

# B. Unit re-parenting
@pytest.mark.xfail(strict=True, reason="audit: moving a unit leaves Topic.course_id stale, so the old course's faculty keep edit rights")
def test_unit_move_moves_topic_authorization(env):
    i = two_faculty(env); chem, work = i["course"]["Chem"], i["course"]["Workshop"]; unit, water = i["unit"][chem], i["topic"]["Water"]
    assert env.c.put(f"/api/units/{unit}", headers=env.admin, json={"name": "U1", "course_id": work}).status_code == 200
    with Session_() as s: assert s.get(Topic, water).course_id == work
    assert edit_topic(env, env.fac, water, unit) == 403
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac, json={"published": False}).status_code == 403
    assert env.c.delete(f"/api/topics/{water}", headers=env.fac).status_code == 403
    assert edit_topic(env, env.fac2, water, unit) == 200
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac2, json={"published": True}).status_code == 200

@pytest.mark.xfail(strict=True, reason="audit: topic authorization trusts the copied Topic.course_id")
def test_authorization_ignores_stale_topic_course_id(env):
    i = two_faculty(env); chem, work = i["course"]["Chem"], i["course"]["Workshop"]; water = i["topic"]["Water"]
    with Session_() as s: s.get(Topic, water).course_id = work; s.commit()  # drift left behind by an old unit move
    assert edit_topic(env, env.fac2, water, i["unit"][chem]) == 403
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac2, json={"published": False}).status_code == 403
    assert env.c.delete(f"/api/topics/{water}", headers=env.fac2).status_code == 403
    assert edit_topic(env, env.fac, water, i["unit"][chem]) == 200

# C. Faculty draft access
@pytest.mark.xfail(strict=True, reason="audit: faculty can read drafts in courses they are not assigned to")
def test_faculty_cannot_read_other_course_drafts(env):
    i = two_faculty(env)
    assert env.c.post("/api/topics", headers=env.fac2, json={"title": "WDraft", "unit_id": i["unit"][i["course"]["Workshop"]], "published": False}).status_code == 200
    d = ids()["topic"]["WDraft"]
    for call in (lambda h: env.c.get(f"/api/topics/{d}", headers=h), lambda h: env.c.post(f"/api/topics/{d}/read", headers=h),
                 lambda h: env.c.put(f"/api/topics/{d}/bookmark", headers=h)):
        assert call(env.fac).status_code == 404
        assert call(env.fac2).status_code == 200 and call(env.admin).status_code == 200
    assert "WDraft" not in titles(env, env.fac) and "WDraft" in titles(env, env.fac2) and "WDraft" in titles(env, env.admin)
    assert env.c.get(f"/api/topics/{i['topic']['Tools']}", headers=env.fac).status_code == 200  # published content stays readable

# D. Student with no program
@pytest.mark.xfail(strict=True, reason="audit: a student with no program sees every program")
def test_student_without_program_gets_no_academic_content(env):
    env.csv(CSV); i = ids()
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": i["unit"][i["course"]["Chem"]], "title": "Q", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [{"text": "t", "options": ["a", "b"], "correct": 0}]})
    assert env.c.get("/api/tree", headers=env.stu).json() == []
    assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403
    assert env.c.post(f"/api/topics/{i['topic']['Water']}/read", headers=env.stu).status_code == 403
    assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).status_code == 403
    assert env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]}).status_code == 403
    assert len(env.c.get("/api/tree", headers=env.admin).json()) == 2 and len(env.c.get("/api/tree", headers=env.fac).json()) == 2

# Quiz answer key
@pytest.mark.xfail(strict=True, reason="audit: the attempt response returns the correct answer for every question")
def test_attempt_response_has_no_answer_key(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": i["unit"][i["course"]["Chem"]], "title": "Q", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [{"text": "t", "options": ["a", "b", "c"], "correct": 2, "explanation": "It is c"}]})
    r = env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [None]})
    assert r.status_code == 200; body = r.json()
    assert (body["score"], body["total"], body["percent"], body["passed"]) == (0, 1, 0, False)
    assert all("correct" not in x and "explanation" not in x for x in body["results"]) and "It is c" not in r.text
