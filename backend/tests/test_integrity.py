"""Regression tests for hierarchy integrity and access control found in the forensic audit."""
import pytest
from main import Session_, User, Semester, Course, Topic, Quiz
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
def test_semester_move_keeps_courses_consistent(env):
    env.csv(CSV); i = ids(); mech1, civil = i["sem"][(i["prog"]["Mech"], "Semester 1")], i["prog"]["Civil"]
    assert env.c.put(f"/api/semesters/{mech1}", headers=env.admin, json={"name": "Semester 1", "program_id": civil}).status_code == 200
    with Session_() as s:
        for c in s.query(Course).filter_by(semester_id=mech1): assert c.program_id == civil == s.get(Semester, c.semester_id).program_id
    enrol("stu@x.com", civil, 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403

def test_semester_cannot_move_to_missing_program(env):
    env.csv(CSV); i = ids(); mech1 = i["sem"][(i["prog"]["Mech"], "Semester 1")]
    assert env.c.put(f"/api/semesters/{mech1}", headers=env.admin, json={"name": "S", "program_id": 99999}).status_code == 400

def test_student_access_ignores_stale_course_program_id(env):
    env.csv(CSV); i = ids(); civil = i["prog"]["Civil"]
    with Session_() as s: s.get(Course, i["course"]["Chem"]).program_id = civil; s.commit()  # drift left behind by an old semester move
    enrol("stu@x.com", civil, 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200

# B. Unit re-parenting
def test_unit_move_moves_topic_authorization(env):
    i = two_faculty(env); chem, work = i["course"]["Chem"], i["course"]["Workshop"]; unit, water = i["unit"][chem], i["topic"]["Water"]
    assert env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": unit, "title": "Q"}).status_code == 200
    assert env.c.put(f"/api/units/{unit}", headers=env.admin, json={"name": "U1", "course_id": work}).status_code == 200
    with Session_() as s: assert s.get(Topic, water).course_id == work and all(q.course_id == work for q in s.query(Quiz).filter_by(unit_id=unit))
    assert env.c.get(f"/api/topics/{water}", headers=env.admin).json()["course"] == "Workshop"
    assert env.c.put(f"/api/units/{unit}", headers=env.admin, json={"name": "U1", "course_id": 99999}).status_code == 400
    assert edit_topic(env, env.fac, water, unit) == 403
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac, json={"published": False}).status_code == 403
    assert env.c.delete(f"/api/topics/{water}", headers=env.fac).status_code == 403
    assert edit_topic(env, env.fac2, water, unit) == 200
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac2, json={"published": True}).status_code == 200

def test_authorization_ignores_stale_topic_course_id(env):
    i = two_faculty(env); chem, work = i["course"]["Chem"], i["course"]["Workshop"]; water = i["topic"]["Water"]
    with Session_() as s: s.get(Topic, water).course_id = work; s.commit()  # drift left behind by an old unit move
    assert edit_topic(env, env.fac2, water, i["unit"][chem]) == 403
    assert env.c.put(f"/api/topics/{water}/publish", headers=env.fac2, json={"published": False}).status_code == 403
    assert env.c.delete(f"/api/topics/{water}", headers=env.fac2).status_code == 403
    assert edit_topic(env, env.fac, water, i["unit"][chem]) == 200

# C. Faculty draft access
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
    q = env.c.post("/api/quizzes", headers=env.fac2, json={"unit_id": i["unit"][i["course"]["Workshop"]], "title": "DraftQuiz"}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.fac2, json={"questions": [{"text": "t", "options": ["a", "b"], "correct": 0}]})
    quizzes = lambda h: [x["title"] for p in env.c.get("/api/tree", headers=h).json() for sm in p["semesters"] for c in sm["courses"] for n in c["units"] for x in n["quizzes"]]
    assert "DraftQuiz" not in quizzes(env.fac) and "DraftQuiz" in quizzes(env.fac2) and "DraftQuiz" in quizzes(env.admin)
    assert env.c.get(f"/api/quizzes/{q}", headers=env.fac).status_code == 404 and env.c.get(f"/api/quizzes/{q}", headers=env.fac2).status_code == 200

# D. Student with no program
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

def test_delete_follows_real_parents_not_stale_copies(env):
    env.csv(CSV); i = ids(); chem, work = i["course"]["Chem"], i["course"]["Workshop"]
    with Session_() as s:  # drift: Water's copy says Workshop, Maths' copy says Mech
        s.get(Topic, i["topic"]["Water"]).course_id = work; s.get(Course, i["course"]["Maths"]).program_id = i["prog"]["Mech"]; s.commit()
    assert env.c.delete(f"/api/courses/{work}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.get(Topic, i["topic"]["Water"]) is not None and s.get(Topic, i["topic"]["Tools"]) is None
    assert env.c.delete(f"/api/programs/{i['prog']['Mech']}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.get(Course, i["course"]["Maths"]) is not None and s.get(Course, chem) is None and s.get(Topic, i["topic"]["Water"]) is None

def test_repair_migration_fixes_drift_and_reports_orphans_without_deleting(env):
    import main
    from main import Unit, Quiz
    env.csv(CSV); i = ids(); chem, work, civil = i["course"]["Chem"], i["course"]["Workshop"], i["prog"]["Civil"]
    with Session_() as s:
        s.get(Topic, i["topic"]["Water"]).course_id = work; s.get(Course, chem).program_id = civil  # drift
        s.add(Quiz(unit_id=i["unit"][chem], course_id=work, title="Q"))
        lost_unit = Unit(name="Lost", course_id=99999); s.add(lost_unit); s.flush()  # orphans: SQLite does not enforce the foreign keys
        lost_topic = Topic(title="LostT", unit_id=lost_unit.id, course_id=work); bad_sem = Semester(name="Gone", program_id=99999)
        no_unit = Topic(title="NoUnit", unit_id=99999, course_id=chem); s.add_all([lost_topic, bad_sem, no_unit]); s.flush(); bad_course = Course(name="Stray", semester_id=bad_sem.id, program_id=civil); s.add(bad_course); s.commit()
        ids_ = dict(unit=lost_unit.id, topic=lost_topic.id, sem=bad_sem.id, course=bad_course.id, no_unit=no_unit.id)
    with main.engine.begin() as c: fixed = main.repair_parent_copies(c)
    assert fixed == {"subjects.course_id": 1, "topics.subject_id": 1, "quizzes.course_id": 1}
    with Session_() as s:
        assert s.get(Topic, i["topic"]["Water"]).course_id == chem and s.get(Course, chem).program_id == i["prog"]["Mech"]
        assert s.query(Quiz).filter_by(title="Q").one().course_id == chem
        assert s.get(Topic, ids_["topic"]).course_id == work and s.get(Course, ids_["course"]).program_id == civil  # parents missing: left alone
        assert all(s.get(m, ids_[k]) for m, k in ((Unit, "unit"), (Topic, "topic"), (Semester, "sem"), (Course, "course")))  # nothing deleted
    with main.engine.connect() as c: rep = main.integrity_report(c)
    assert rep["units without a course"] == [ids_["unit"]] and rep["topics without a unit"] == [ids_["no_unit"]] and rep["semesters without a program"] == [ids_["sem"]]
    with main.engine.begin() as c: assert set(main.repair_parent_copies(c).values()) == {0}  # running again changes nothing
    assert "0007_repair_parent_copies" in main.applied_migrations()
