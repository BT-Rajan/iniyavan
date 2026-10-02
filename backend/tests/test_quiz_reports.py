import csv, io
from main import Session_, User, Quiz, Attempt, Question, Course, Unit, Topic, Progress
from tests.test_access import CSV, ids, enrol

QS = [{"text": "Which ion causes temporary hardness?", "options": ["Ca(HCO3)2", "CaSO4", "NaCl"], "correct": 0, "explanation": "Bicarbonates precipitate on boiling."},
      {"text": "Unit of hardness?", "options": ["ppm", "pH"], "correct": 0}]
def setup(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: fid = s.query(User).filter_by(email="fac@x.com").first().id
    env.c.put(f"/api/admin/users/{fid}/courses", headers=env.admin, json={"course_ids": [i["course"]["Chem"]]})
    return i, i["unit"][i["course"]["Chem"]]
def make_quiz(env, unit, h=None, published=True):
    q = env.c.post("/api/quizzes", headers=h or env.admin, json={"unit_id": unit, "title": "Water quiz", "pass_percent": 50, "published": published}).json()["id"]
    assert env.c.put(f"/api/quizzes/{q}/questions", headers=h or env.admin, json={"questions": QS}).status_code == 200
    return q

def test_student_never_sees_answers_and_is_graded_on_the_server(env):
    i, unit = setup(env); q = make_quiz(env, unit)
    st = env.c.get(f"/api/quizzes/{q}", headers=env.stu).json()
    assert len(st["questions"]) == 2 and "correct" not in st["questions"][0] and "explanation" not in st["questions"][0] and st["can_edit"] is False
    assert "correct" in env.c.get(f"/api/quizzes/{q}", headers=env.admin).json()["questions"][0]
    r = env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 1]}).json()
    assert (r["score"], r["total"], r["percent"], r["passed"]) == (1, 2, 50, True) and [x["ok"] for x in r["results"]] == [True, False]
    assert all("correct" not in x and "explanation" not in x for x in r["results"])  # the answer key never goes to students, even after submitting
    staff = env.c.post(f"/api/quizzes/{q}/attempt", headers=env.admin, json={"answers": [0, 1]}).json()["results"]
    assert staff[0]["explanation"].startswith("Bicarbonates") and staff[1]["correct"] == 0  # people who can edit the quiz still see it
    r2 = env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [None, None]}).json(); assert r2["percent"] == 0 and r2["passed"] is False
    assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).json()["best"] == 50
    assert env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]}).status_code == 400

def test_quiz_scope_drafts_and_permissions(env):
    i, unit = setup(env); other = i["unit"][i["course"]["Workshop"]]
    q = make_quiz(env, unit, published=False)
    assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).status_code == 404 and env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]}).status_code == 404
    tree = lambda h: [x["id"] for p in env.c.get("/api/tree", headers=h).json() for sm in p["semesters"] for c in sm["courses"] for n in c["units"] for x in n["quizzes"]]
    assert tree(env.stu) == [] and tree(env.fac) == [q]
    env.c.put(f"/api/quizzes/{q}", headers=env.fac, json={"title": "Water quiz", "pass_percent": 60, "published": True})
    assert tree(env.stu) == [q] and env.c.get("/api/tree", headers=env.stu).json()[0]["semesters"][0]["courses"][0]["units"][0]["quizzes"][0]["pass_percent"] == 60
    assert env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": other, "title": "x"}).status_code == 403   # not their course
    assert env.c.post("/api/quizzes", headers=env.stu, json={"unit_id": unit, "title": "x"}).status_code == 403
    w = make_quiz(env, other); assert env.c.get(f"/api/quizzes/{w}", headers=env.stu).status_code == 200  # same program and semester
    enrol("stu@x.com", i["prog"]["Civil"], 1); assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).status_code == 403  # a different program
    bad = lambda qs: env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": qs}).status_code
    assert bad([{"text": "", "options": ["a", "b"], "correct": 0}]) == 400 and bad([{"text": "t", "options": ["a"], "correct": 0}]) == 400 and bad([{"text": "t", "options": ["a", "b"], "correct": 2}]) == 400

def test_deleting_a_unit_or_quiz_removes_its_questions_and_attempts(env):
    i, unit = setup(env); q = make_quiz(env, unit); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]})
    assert env.c.delete(f"/api/quizzes/{q}", headers=env.fac).status_code == 200
    with Session_() as s: assert (s.query(Quiz).count(), s.query(Question).count(), s.query(Attempt).count()) == (0, 0, 0)
    q = make_quiz(env, unit); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]})
    assert env.c.delete(f"/api/units/{unit}", headers=env.fac).status_code == 200
    with Session_() as s: assert (s.query(Quiz).count(), s.query(Question).count(), s.query(Attempt).count()) == (0, 0, 0)

def read(email, title):
    with Session_() as s:
        s.add(Progress(user_id=s.query(User).filter_by(email=email).first().id, topic_id=s.query(Topic).filter_by(title=title).first().id)); s.commit()

def test_course_report_completion_quiz_scores_and_faculty_limits(env):
    i, unit = setup(env); env.add_user("stu2@x.com", program=i["prog"]["Mech"], semester=1); env.add_user("civ@x.com", program=i["prog"]["Civil"], semester=1)
    env.c.post("/api/topics", headers=env.fac, json={"title": "Boilers", "unit_id": unit}); read("stu@x.com", "Water"); read("stu@x.com", "Boilers"); read("stu2@x.com", "Water")
    q = make_quiz(env, unit); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0, 0]})
    rows = {r["course"]: r for r in env.c.get("/api/reports/courses", headers=env.admin).json()}
    chem = rows["Chem"]; assert (chem["students"], chem["topics"], chem["avg_completion"], chem["quizzes"], chem["quiz_attempts"], chem["avg_quiz_percent"]) == (2, 2, 75, 1, 1, 100)
    assert rows["Maths"]["students"] == 1 and rows["Workshop"]["students"] == 2
    assert [r["course"] for r in env.c.get("/api/reports/courses", headers=env.fac).json()] == ["Chem"]
    assert [r["course"] for r in env.c.get(f"/api/reports/courses?program_id={i['prog']['Civil']}", headers=env.admin).json()] == ["Maths", "Survey"]
    assert [r["course"] for r in env.c.get("/api/reports/courses?semester=2", headers=env.admin).json()] == ["Survey"]
    st = {r["email"]: r for r in env.c.get(f"/api/reports/courses/{i['course']['Chem']}/students", headers=env.fac).json()["students"]}
    assert (st["stu@x.com"]["completion"], st["stu@x.com"]["avg_quiz_percent"], st["stu2@x.com"]["completion"], st["stu2@x.com"]["quizzes_taken"]) == (100, 100, 50, 0) and "civ@x.com" not in st
    assert env.c.get(f"/api/reports/courses/{i['course']['Workshop']}/students", headers=env.fac).status_code == 403
    assert env.c.get("/api/reports/courses", headers=env.stu).status_code == 403

def test_csv_export_and_formula_injection_guard(env):
    i, unit = setup(env)
    with Session_() as s: s.query(User).filter_by(email="stu@x.com").update({"name": "=HYPERLINK(\"http://evil\")"}); s.commit()
    r = env.c.get(f"/api/reports/courses/{i['course']['Chem']}/students?format=csv", headers=env.admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff")))); assert rows[0][0] == "Name" and rows[1][0].startswith("'=HYPERLINK")
    c = env.c.get("/api/reports/courses?format=csv", headers=env.admin); assert c.text.lstrip("\ufeff").splitlines()[0].startswith("Program,Semester,Course")
