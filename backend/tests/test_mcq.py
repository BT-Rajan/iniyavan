import csv, io, json
from main import Session_, User, Quiz, Attempt, Question
from tests.test_access import ids, enrol

# Chem has two units (U1: Water, Hardness; U2: Boilers) so course tests can tie questions to topics anywhere in the course
CSV = ("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\nMech,Semester 1,Chem,U1,Hardness,h\nMech,Semester 1,Chem,U2,Boilers,b\n"
       "Mech,Semester 1,Workshop,U1,Tools,t\n")
IMG = "/api/uploads/" + "a" * 32 + ".png"
MCQ = ("question,a,b,c,d,correct,explanation,topic,area,question_image,a_image,b_image\n"
       "Which ion makes water hard?,Na+,Ca2+,Cl-,K+,B,Calcium salts,Hardness,,,,\n"
       "Pick the boiler shown,,,Fire tube,Water tube,C,,Boilers,,boiler.png,left.PNG,right.png\n"
       "Unit of hardness?,ppm,pH,,,ppm,,Titration,,,,\n"
       "2 + 2?,3,4,5,,2,,,Arithmetic,,,\n"
       "No answers,only one,,,,A,,,,,,\n"
       "Bad key,x,y,,,Z,,,,,,\n"
       "Two keys,x,y,,,\"A, B\",,,,,,\n"
       "Gap,x,,z,,A,,,,,,\n")

def setup(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: fid = s.query(User).filter_by(email="fac@x.com").first().id
    env.c.put(f"/api/admin/users/{fid}/courses", headers=env.admin, json={"course_ids": [i["course"]["Chem"]]})
    return i, i["course"]["Chem"]
def parse(env, cid, text=MCQ, h=None): return env.c.post("/api/quizzes/parse-csv", headers=h or env.fac, json={"csv": text, "course_id": cid})
def make_test(env, cid, qs, h=None, **kw):
    q = env.c.post("/api/quizzes", headers=h or env.fac, json={"course_id": cid, "title": "Chem MCQ", "pass_percent": 50, "published": True, **kw}).json()["id"]
    r = env.c.put(f"/api/quizzes/{q}/questions", headers=h or env.fac, json={"questions": qs}); assert r.status_code == 200, r.text
    return q
def take(env, q, answers, h): r = env.c.post(f"/api/quizzes/{q}/attempt", headers=h, json={"answers": answers}); assert r.status_code == 200, r.text; return r.json()

def test_csv_preview_reads_answers_topics_areas_and_image_names(env):
    i, cid = setup(env); r = parse(env, cid).json()
    assert r["count"] == 4 and r["error_count"] == 4
    assert [e["row"] for e in r["errors"]] == [6, 7, 8, 9] and "Only one correct" in r["errors"][2]["error"] and "Answer B is empty" in r["errors"][3]["error"]
    q1, q2, q3, q4 = r["questions"]
    assert (q1["correct"], q1["topic_id"], q1["options"]) == (1, i["topic"]["Hardness"], ["Na+", "Ca2+", "Cl-", "K+"])
    assert q2["text"] == "Pick the boiler shown" and q2["image_name"] == "boiler.png" and q2["option_image_names"] == ["left.PNG", "right.png", "", ""] and q2["options"][:2] == ["", ""]
    assert q2["topic_id"] == i["topic"]["Boilers"]  # a topic from another unit of the course
    assert (q3["correct"], q3["topic_id"], q3["area"], q3["options"]) == (0, None, "Titration", ["ppm", "pH"])  # answer given as text; unknown topic becomes an area
    assert any("Titration" in w for w in r["warnings"]) and (q4["correct"], q4["area"]) == (1, "Arithmetic")
    assert r["images_needed"] == ["boiler.png", "left.PNG", "right.png"]
    assert parse(env, cid, "foo,bar\n1,2\n").status_code == 400
    assert parse(env, cid, h=env.stu).status_code == 403 and parse(env, i["course"]["Workshop"]).status_code == 403  # not their course
    semi = parse(env, cid, "question;a;b;correct\nQ;x;y;b\n").json(); assert semi["questions"][0]["correct"] == 1  # semicolon files work too

def test_course_test_with_images_is_taken_and_graded(env):
    i, cid = setup(env)
    qs = [{"text": "Which ion makes water hard?", "options": ["Na+", "Ca2+"], "correct": 1, "topic_id": i["topic"]["Hardness"], "explanation": "Calcium"},
          {"text": "Pick the boiler", "image": IMG, "options": ["", "Water tube"], "option_images": [IMG, ""], "correct": 0, "topic_id": i["topic"]["Boilers"]},
          {"text": "2 + 2?", "options": ["3", "4"], "correct": 1, "area": "Arithmetic"}]
    bad = env.c.post("/api/quizzes", headers=env.fac, json={"course_id": cid, "title": "T"}).json()["id"]
    put = lambda b: env.c.put(f"/api/quizzes/{bad}/questions", headers=env.fac, json={"questions": [b]}).status_code
    assert put({**qs[1], "image": "https://evil.example/x.png"}) == 400 and put({**qs[1], "option_images": ["", ""]}) == 400  # an answer needs text or an image
    assert put({**qs[0], "topic_id": i["topic"]["Tools"]}) == 400  # topic from another course
    q = make_test(env, cid, qs)
    st = env.c.get(f"/api/quizzes/{q}", headers=env.stu).json()
    assert st["kind"] == "course" and st["questions"][1]["image"] == IMG and st["questions"][1]["option_images"] == [IMG, ""] and "correct" not in st["questions"][0]
    course = env.c.get("/api/tree", headers=env.stu).json()[0]["semesters"][0]["courses"][0]; assert [t["id"] for t in course["tests"]] == [q]
    r = take(env, q, [1, 1, None], env.stu)
    assert (r["score"], r["percent"], r["passed"], r["reveal"]) == (1, 33, False, False) and "correct" not in r["results"][0]
    with Session_() as s: assert json.loads(s.get(Attempt, r["attempt_id"]).detail) == [[s.query(Question).filter_by(quiz_id=q, pos=k).one().id, ok, a] for k, ok, a in ((0, 1, 1), (1, 0, 1), (2, 0, None))]
    areas = {a["title"]: a for a in r["areas"]}; assert set(areas) == {"Hardness", "Boilers", "Arithmetic"} and areas["Arithmetic"]["area"] is True and areas["Boilers"]["unit"] == "U2"
    assert r["summary"].startswith("Good at Hardness") and "Boilers" in r["summary"]
    assert env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [5, 0, 0]}).status_code == 400  # not a choice
    env.c.put(f"/api/quizzes/{q}", headers=env.fac, json={"title": "Chem MCQ", "pass_percent": 50, "published": True, "reveal": True})
    r2 = take(env, q, [1, 0, 1], env.stu); assert r2["reveal"] is True and r2["results"][1]["correct"] == 0 and r2["results"][0]["explanation"] == "Calcium"

def test_attempt_review_is_for_the_student_and_course_staff_only(env):
    i, cid = setup(env); q = make_test(env, cid, [{"text": "Q1", "options": ["a", "b"], "correct": 0}, {"text": "Q2", "options": ["a", "b", "c"], "correct": 2}])
    aid = take(env, q, [0, 1], env.stu)["attempt_id"]
    d = env.c.get(f"/api/attempts/{aid}", headers=env.stu).json()
    assert (d["score"], d["total"], d["reveal"]) == (1, 2, False) and [(x["ok"], x["chosen"]) for x in d["questions"]] == [(True, 0), (False, 1)] and "correct" not in d["questions"][1]
    staff = env.c.get(f"/api/attempts/{aid}", headers=env.fac).json(); assert staff["questions"][1]["correct"] == 2 and staff["user"] == "stu@x.com"
    env.add_user("stu2@x.com"); assert env.c.get(f"/api/attempts/{aid}", headers=env.login("stu2@x.com")).status_code == 403
    env.add_user("fac2@x.com", "faculty"); assert env.c.get(f"/api/attempts/{aid}", headers=env.login("fac2@x.com")).status_code == 403
    mine = env.c.get(f"/api/quizzes/{q}/attempts", headers=env.stu).json(); assert [x["id"] for x in mine["items"]] == [aid]
    res = env.c.get(f"/api/quizzes/{q}/results", headers=env.fac).json()["questions"]; assert [(x["correct"], x["right"]) for x in res] == [(0, 1), (2, 0)]  # key and count never mix
    uid = d["user_id"]; assert env.c.get(f"/api/quizzes/{q}/attempts?user_id={uid}", headers=env.fac).json()["items"][0]["percent"] == 50
    assert env.c.get(f"/api/quizzes/{q}/attempts?user_id={uid}", headers=env.login("stu2@x.com")).status_code == 403

def test_results_give_final_scores_question_analysis_and_a_drill_down(env):
    i, cid = setup(env); env.add_user("stu2@x.com"); env.add_user("stu3@x.com"); enrol("stu2@x.com", i["prog"]["Mech"], 1); enrol("stu3@x.com", i["prog"]["Mech"], 1)
    q = make_test(env, cid, [{"text": "Q1", "options": ["a", "b", "c"], "correct": 0, "area": "Ions"}, {"text": "Q2", "options": ["a", "b"], "correct": 1, "area": "Units"}])
    s2 = env.login("stu2@x.com")
    take(env, q, [0, 1], env.stu); take(env, q, [1, 0], env.stu)  # best 100, latest 0
    take(env, q, [2, 1], s2)
    take(env, q, [0, 1], env.fac)  # staff tries are not counted
    r = env.c.get(f"/api/quizzes/{q}/results", headers=env.fac).json(); sm = r["summary"]
    assert (sm["students"], sm["took"], sm["not_taken"], sm["attempts"], sm["passed"], sm["pass_rate"]) == (3, 2, 1, 3, 2, 100)
    assert (sm["average"], sm["highest"], sm["lowest"], sm["average_latest"]) == (75, 100, 50, 25) and sm["distribution"][9]["count"] == 1 and sm["distribution"][5]["count"] == 1
    st = {x["email"]: x for x in r["students"]}
    assert (st["stu@x.com"]["best"], st["stu@x.com"]["latest"], st["stu@x.com"]["attempts"]) == (100, 0, 2) and st["stu@x.com"]["needs_study"] == ["Ions", "Units"]
    assert st["stu2@x.com"]["strong"] == ["Units"] and [x["email"] for x in r["not_taken"]] == ["stu3@x.com"]
    q1, q2 = r["questions"]
    assert (q1["total"], q1["right"], q1["picks"], q1["percent"]) == (2, 0, [0, 1, 1], 0) and (q2["picks"], q2["percent"]) == ([1, 1], 50)  # latest attempts only
    assert (q1["correct"], q2["correct"]) == (0, 1)  # the answer key, not a count
    assert {a["title"]: a["students"] for a in r["areas"]} == {"Ions": 2, "Units": 2}
    rows = list(csv.reader(io.StringIO(env.c.get(f"/api/quizzes/{q}/results?format=csv", headers=env.fac).text.lstrip("﻿"))))
    assert rows[0][3].startswith("Final score") and {r_[1]: r_[3] for r_ in rows[1:]} == {"stu@x.com": "100", "stu2@x.com": "50", "stu3@x.com": ""}
    env.add_user("fac2@x.com", "faculty"); assert env.c.get(f"/api/quizzes/{q}/results", headers=env.login("fac2@x.com")).status_code == 403
    assert env.c.get(f"/api/quizzes/{q}/results", headers=env.stu).status_code == 403

def test_gradebook_and_my_scores_cover_course_tests_and_unit_quizzes(env):
    i, cid = setup(env)
    t = make_test(env, cid, [{"text": "Q", "options": ["a", "b"], "correct": 0}])
    uq = env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": i["unit"][cid], "title": "Unit quiz", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{uq}/questions", headers=env.fac, json={"questions": [{"text": "Q", "options": ["a", "b"], "correct": 0}, {"text": "R", "options": ["a", "b"], "correct": 0}]})
    take(env, t, [0], env.stu); take(env, uq, [0, 1], env.stu)
    g = env.c.get(f"/api/courses/{cid}/gradebook", headers=env.fac).json()
    assert [x["title"] for x in g["tests"]] == ["Chem MCQ", "Unit quiz"] and g["tests"][1]["unit"] in ("U1", "U2")
    row = g["students"][0]; assert (row["scores"], row["taken"], row["final"], row["passed"]) == ([100, 50], 2, 75, 2)
    assert "Final score" in env.c.get(f"/api/courses/{cid}/gradebook?format=csv", headers=env.fac).text
    assert env.c.get(f"/api/courses/{cid}/gradebook", headers=env.stu).status_code == 403
    me = env.c.get("/api/me/scores", headers=env.stu).json()["courses"]
    chem = next(c for c in me if c["course"] == "Chem"); assert (chem["final"], chem["taken"], chem["passed"]) == (75, 2, 2)
    assert {x["title"]: (x["best"], x["attempts"], x["kind"]) for x in chem["tests"]} == {"Chem MCQ": (100, 1, "course"), "Unit quiz": (50, 1, "unit")}

def test_drafts_archived_courses_old_attempts_and_deleting_the_course(env):
    i, cid = setup(env); q = make_test(env, cid, [{"text": "Q", "options": ["a", "b"], "correct": 0, "area": "A"}], published=False)
    assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).status_code == 404
    assert env.c.get("/api/tree", headers=env.stu).json()[0]["semesters"][0]["courses"][0]["tests"] == []
    env.c.put(f"/api/quizzes/{q}", headers=env.fac, json={"title": "T", "published": True})
    with Session_() as s:  # an attempt saved before chosen answers were kept
        uid = s.query(User).filter_by(email="stu@x.com").first().id; qq = s.query(Question).filter_by(quiz_id=q).first()
        a = Attempt(quiz_id=q, user_id=uid, score=1, total=1, percent=100, detail=json.dumps([[qq.id, 1]])); s.add(a); s.commit(); aid = a.id
    d = env.c.get(f"/api/attempts/{aid}", headers=env.stu).json(); assert d["questions"][0]["chosen_known"] is False and d["areas"][0]["title"] == "A"
    assert env.c.get(f"/api/quizzes/{q}/results", headers=env.fac).json()["questions"][0]["picks_known"] == 0
    assert env.c.put(f"/api/courses/{cid}/archive", headers=env.admin, json={"archived": True}).status_code == 200
    assert env.c.get(f"/api/quizzes/{q}", headers=env.stu).status_code == 403 and env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]}).status_code == 403
    assert env.c.delete(f"/api/courses/{cid}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.get(Quiz, q) is None and s.query(Attempt).filter_by(quiz_id=q).count() == 0

def test_course_topics_list_for_a_new_test(env):
    i, cid = setup(env)
    got = env.c.get(f"/api/courses/{cid}/topics", headers=env.fac).json(); assert [(t["unit"], t["title"]) for t in got] == [("U1", "Water"), ("U1", "Hardness"), ("U2", "Boilers")]
    assert env.c.get(f"/api/courses/{cid}/topics", headers=env.stu).status_code == 403 and env.c.get(f"/api/courses/{i['course']['Workshop']}/topics", headers=env.fac).status_code == 403
