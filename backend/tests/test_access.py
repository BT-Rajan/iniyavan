from main import Session_, User, Program, Semester, Course, Unit, Topic, CourseFaculty, CourseLink
CSV = "program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\nMech,Semester 1,Workshop,U1,Tools,t\nCivil,Semester 1,Maths,U1,Limits,l\nCivil,Semester 2,Survey,U1,Chain,c\n"
def ids():
    with Session_() as s:
        return dict(prog={p.name: p.id for p in s.query(Program)}, sem={(x.program_id, x.name): x.id for x in s.query(Semester)}, course={c.name: c.id for c in s.query(Course)},
                    unit={u.course_id: u.id for u in s.query(Unit)}, topic={t.title: t.id for t in s.query(Topic)})
def enrol(email, prog, sem):
    with Session_() as s: s.query(User).filter_by(email=email).update({"program_id": prog, "semester": sem}); s.commit()
def tree(env, h): return [(sm["name"], [(c["name"], c["shared"]) for c in sm["courses"]]) for p in env.c.get("/api/tree", headers=h).json() for sm in p["semesters"]]
def titles(env, h): return [t["title"] for p in env.c.get("/api/tree", headers=h).json() for sm in p["semesters"] for c in sm["courses"] for u in c["units"] for t in u["topics"]]

def test_student_is_scoped_to_program_and_semester(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    assert tree(env, env.stu) == [("Semester 1", [("Chem", False), ("Workshop", False)])]
    assert env.c.get(f"/api/topics/{i['topic']['Limits']}", headers=env.stu).status_code == 403
    assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200
    assert len(tree(env, env.admin)) == 3
    assert env.c.get("/api/tree", headers=env.stu).json()[0]["semesters"][0]["current"] is True

def test_future_semesters_hidden_and_roman_names(env):
    env.csv("program,semester,course,unit,topic\nMech,Sem II,Physics,U,T2\nMech,Semester 3,Thermo,U,T3\n"); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 2)
    assert [n for n, _ in tree(env, env.stu)] == ["Sem II"]
    assert env.c.get(f"/api/topics/{i['topic']['T3']}", headers=env.stu).status_code == 403

def test_common_course_shared_into_other_program(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Civil"], 1)
    assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403
    civil1 = i["sem"][(i["prog"]["Civil"], "Semester 1")]
    assert env.c.put(f"/api/courses/{i['course']['Chem']}/links", headers=env.admin, json={"semester_ids": [civil1]}).status_code == 200
    assert ("Chem", True) in tree(env, env.stu)[0][1]
    assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200
    assert env.c.get(f"/api/topics/{i['topic']['Tools']}", headers=env.stu).status_code == 403
    assert env.c.put(f"/api/courses/{i['course']['Chem']}/links", headers=env.admin, json={"semester_ids": [999]}).status_code == 400
    env.c.delete(f"/api/courses/{i['course']['Chem']}", headers=env.admin)
    with Session_() as s: assert s.query(CourseLink).count() == 0

def test_faculty_edits_only_assigned_courses(env):
    env.csv(CSV); i = ids()
    with Session_() as s: fid = s.query(User).filter_by(email="fac@x.com").first().id
    assert env.c.put(f"/api/admin/users/{fid}/courses", headers=env.fac, json={"course_ids": [i["course"]["Chem"]]}).status_code == 403
    assert env.c.put(f"/api/admin/users/{fid}/courses", headers=env.admin, json={"course_ids": [i["course"]["Chem"]]}).status_code == 200
    mine, other = i["unit"][i["course"]["Chem"]], i["unit"][i["course"]["Workshop"]]
    T = lambda u, t: {"title": t, "unit_id": u, "content": "x"}
    assert env.c.post("/api/topics", headers=env.fac, json=T(mine, "N1")).status_code == 200
    assert env.c.post("/api/topics", headers=env.fac, json=T(other, "N2")).status_code == 403
    assert env.c.put(f"/api/topics/{i['topic']['Water']}", headers=env.fac, json=T(other, "x")).status_code == 403  # can't move out of the course
    assert env.c.delete(f"/api/topics/{i['topic']['Tools']}", headers=env.fac).status_code == 403
    for method, url in [("post", "/api/courses"), ("get", "/api/admin/users"), ("get", "/api/admin/settings"), ("post", "/api/admin/import")]:
        assert getattr(env.c, method)(url, headers=env.fac, **({"json": {"name": "n", "semester_id": 1, "csv": "a"}} if method == "post" else {})).status_code == 403
    assert env.c.post("/api/topics", headers=env.stu, json=T(mine, "z")).status_code == 403

def test_drafts_are_hidden_from_students(env):
    env.csv(CSV); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: fid = s.query(User).filter_by(email="fac@x.com").first().id
    env.c.put(f"/api/admin/users/{fid}/courses", headers=env.admin, json={"course_ids": [i["course"]["Chem"]]})
    u = i["unit"][i["course"]["Chem"]]
    assert env.c.post("/api/topics", headers=env.fac, json={"title": "Draft1", "unit_id": u, "published": False}).status_code == 200
    d = ids()["topic"]["Draft1"]
    assert "Draft1" not in titles(env, env.stu) and "Draft1" in titles(env, env.fac)
    for call in (env.c.get(f"/api/topics/{d}", headers=env.stu), env.c.post(f"/api/topics/{d}/read", headers=env.stu), env.c.put(f"/api/topics/{d}/bookmark", headers=env.stu)):
        assert call.status_code == 404
    assert env.c.put(f"/api/units/{u}/publish", headers=env.fac, json={"published": True}).json()["changed"] == 1
    assert "Draft1" in titles(env, env.stu)
    assert env.c.put(f"/api/topics/{i['topic']['Tools']}/publish", headers=env.fac, json={"published": False}).status_code == 403

def test_bookmarks_are_per_topic_and_admins_do_not_have_them(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n,,,,Fuel,f\n")
    t = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["topics"]
    a, b = t[0]["id"], t[1]["id"]
    assert env.c.put(f"/api/topics/{a}/bookmark", headers=env.admin).status_code == 403
    marked = lambda h: [x["id"] for u in env.c.get("/api/tree", headers=h).json()[0]["semesters"][0]["courses"][0]["units"] for x in u["topics"] if x["bookmarked"]]
    assert marked(env.admin) == []
    assert env.c.put(f"/api/topics/{a}/bookmark", headers=env.fac).status_code == 200  # faculty may read published content, so they may save it
    assert marked(env.fac) == [a] and b not in marked(env.fac)  # only that topic, not its unit or course
