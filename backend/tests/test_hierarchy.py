"""Admin academic structure: Program > Semester (explicit number) > Course (> faculty owner), made in context and kept consistent."""
import main
from main import Session_, User, Program, Semester, Course, Unit, Topic
from tests.test_access import CSV, ids, enrol

def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def program(env, name, h=None): return env.c.post("/api/programs", headers=h or env.admin, json={"name": name, "terms": 0})
def semester(env, pid, name, no, h=None): return env.c.post(f"/api/programs/{pid}/semesters", headers=h or env.admin, json={"name": name, "semester_no": no})
def course(env, pid, sid, name, owner=None, h=None):
    return env.c.post(f"/api/programs/{pid}/semesters/{sid}/courses", headers=h or env.admin, json={"name": name, **({"faculty_owner_id": owner} if owner else {})})
def tree_sems(env, h=None): return [(p["name"], [(sm["name"], sm["number"], [c["name"] for c in sm["courses"]]) for sm in p["semesters"]]) for p in env.c.get("/api/tree", headers=h or env.admin).json()]
def consistent():  # every copied parent id agrees with the real chain
    with Session_() as s:
        for co in s.query(Course): assert co.program_id == s.get(Semester, co.semester_id).program_id
        for t in s.query(Topic): assert t.course_id == s.get(Unit, t.unit_id).course_id

# 1-6
def test_admin_builds_program_semester_course_in_context(env):
    r = program(env, "B.Tech Mech"); assert r.status_code == 200; pid = r.json()["id"]                        # 1
    r = semester(env, pid, "Semester 1", 1); assert r.status_code == 200; sid = r.json()["id"]                 # 2
    with Session_() as s: assert (s.get(Semester, sid).program_id, s.get(Semester, sid).semester_no) == (pid, 1)  # 3
    r = course(env, pid, sid, "Engineering Chemistry", uid("fac@x.com")); assert r.status_code == 200; cid = r.json()["id"]  # 4
    with Session_() as s:
        co = s.get(Course, cid); assert co.semester_id == sid                                                  # 5
        assert s.get(Semester, co.semester_id).program_id == pid == co.program_id and co.faculty_owner_id == uid("fac@x.com")  # 6
    assert tree_sems(env) == [("B.Tech Mech", [("Semester 1", 1, ["Engineering Chemistry"])])]
    assert semester(env, 99999, "Semester 1", 1).status_code == 404 and semester(env, pid, " ", 2).status_code == 400 and course(env, pid, sid, "").status_code == 400

# 7-10
def test_semester_numbers_are_unique_per_program_and_decide_order(env):
    a, b = program(env, "A").json()["id"], program(env, "B").json()["id"]
    assert semester(env, a, "Semester 1", 1).status_code == 200
    r = semester(env, a, "First semester again", 1); assert r.status_code == 400 and "already has semester 1" in r.json()["detail"]  # 7
    assert semester(env, b, "Semester 1", 1).status_code == 200                                              # 8
    for name, no in (("Semester 3", 3), ("Semester 2", 2)): assert semester(env, a, name, no).status_code == 200
    assert [x[1] for x in tree_sems(env)[0][1]] == [1, 2, 3]                                                   # 9: by number, not insertion or name
    assert [x["number"] for x in env.c.get(f"/api/admin/programs/{a}", headers=env.admin).json()["semester_list"]] == [1, 2, 3]
    for bad in (0, 9, None): assert env.c.post(f"/api/programs/{a}/semesters", headers=env.admin, json={"name": "S", "semester_no": bad}).status_code in (400, 422)

def test_semester_name_does_not_decide_its_number(env):  # 10
    pid = program(env, "Mech").json()["id"]
    late = semester(env, pid, "Semester 1", 4).json()["id"]; early = semester(env, pid, "Foundation year", 1).json()["id"]
    c_late, c_early = course(env, pid, late, "Late").json()["id"], course(env, pid, early, "Early").json()["id"]
    for cid in (c_late, c_early): env.c.post("/api/units", headers=env.admin, json={"name": "U", "course_id": cid})
    with Session_() as s: units = {u.course_id: u.id for u in s.query(Unit)}
    for cid, title in ((c_late, "LateTopic"), (c_early, "EarlyTopic")): env.c.post("/api/topics", headers=env.admin, json={"title": title, "unit_id": units[cid]})
    with Session_() as s: tid = {t.title: t.id for t in s.query(Topic)}
    enrol("stu@x.com", pid, 1)
    assert [x[0] for x in tree_sems(env, env.stu)[0][1]] == ["Foundation year"]
    assert env.c.get(f"/api/topics/{tid['LateTopic']}", headers=env.stu).status_code == 403 and env.c.get(f"/api/topics/{tid['EarlyTopic']}", headers=env.stu).status_code == 200
    assert env.c.get("/api/tree", headers=env.stu).json()[0]["semesters"][0]["current"] is True
    assert env.c.put(f"/api/semesters/{late}", headers=env.admin, json={"name": "Semester 1", "program_id": pid, "semester_no": 1}).status_code == 400
    assert env.c.put(f"/api/semesters/{late}", headers=env.admin, json={"name": "Renamed", "program_id": pid}).status_code == 200  # number kept when left out
    with Session_() as s: assert s.get(Semester, late).semester_no == 4

# 11-14
def test_course_needs_a_semester_of_the_program_it_is_made_in(env):
    a, b = program(env, "A").json()["id"], program(env, "B").json()["id"]; sa = semester(env, a, "Semester 1", 1).json()["id"]
    assert course(env, a, 99999, "X").status_code == 404                                                       # 11
    assert env.c.post("/api/courses", headers=env.admin, json={"name": "X", "semester_id": 99999}).status_code == 400
    assert env.c.post("/api/courses", headers=env.admin, json={"name": "X"}).status_code == 422
    assert course(env, b, sa, "Wrong program").status_code == 404                                              # 12
    with Session_() as s: assert s.query(Course).count() == 0
    r = env.c.post("/api/courses", headers=env.admin, json={"name": "Flat", "semester_id": sa}); assert r.status_code == 200  # the older flat form still checks the same way
    with Session_() as s: assert s.get(Course, r.json()["id"]).program_id == a

def test_moving_a_course_moves_its_program_and_keeps_its_owner(env):
    env.csv(CSV); i = ids(); chem = i["course"]["Chem"]; civil = i["prog"]["Civil"]; civil2 = i["sem"][(civil, "Semester 2")]
    assert env.c.put(f"/api/courses/{chem}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")}).status_code == 200
    assert env.c.put(f"/api/courses/{chem}/links", headers=env.admin, json={"semester_ids": [civil2]}).status_code == 200
    assert env.c.put(f"/api/courses/{chem}", headers=env.admin, json={"name": "Chem", "semester_id": civil2}).status_code == 200  # 13
    with Session_() as s:
        co = s.get(Course, chem); assert (co.semester_id, co.program_id) == (civil2, civil) and co.faculty_owner_id == uid("fac@x.com")  # 14
        assert s.query(main.CourseLink).filter_by(course_id=chem).count() == 0  # no shared copy left in its own new home
    consistent()
    enrol("stu@x.com", civil, 2); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 200
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.stu).status_code == 403
    assert env.c.put(f"/api/topics/{i['topic']['Water']}/publish", headers=env.fac, json={"published": True}).status_code == 200  # owner still edits it
    assert [c for _, sems in tree_sems(env) for _, n, cs in sems for c in cs].count("Chem") == 1

# 15-19
def test_faculty_cannot_build_or_change_the_structure(env):
    pid = program(env, "Mech").json()["id"]; sid = semester(env, pid, "Semester 1", 1).json()["id"]; s2 = semester(env, pid, "Semester 2", 2).json()["id"]
    cid = course(env, pid, sid, "Chem", uid("fac@x.com")).json()["id"]
    for h in (env.fac, env.stu):  # fac owns Chem and still can't
        assert program(env, "P", h).status_code == 403                                                          # 15
        assert semester(env, pid, "Semester 3", 3, h).status_code == 403                                       # 16
        assert env.c.post("/api/semesters", headers=h, json={"name": "S", "program_id": pid, "semester_no": 3}).status_code == 403
        assert course(env, pid, sid, "New", h=h).status_code == 403                                            # 17
        assert env.c.put(f"/api/courses/{cid}", headers=h, json={"name": "Chem", "semester_id": s2}).status_code == 403   # 18
        assert env.c.put(f"/api/courses/{cid}", headers=h, json={"name": "Renamed", "semester_id": sid}).status_code == 403
        assert env.c.put(f"/api/courses/{cid}/owner", headers=h, json={"user_id": None}).status_code == 403   # 19
        assert env.c.put(f"/api/semesters/{sid}", headers=h, json={"name": "S", "program_id": pid, "semester_no": 5}).status_code == 403
        for kind, rid in (("courses", cid), ("semesters", sid), ("programs", pid)): assert env.c.delete(f"/api/{kind}/{rid}", headers=h).status_code == 403
    with Session_() as s: co = s.get(Course, cid); assert (co.name, co.semester_id, co.faculty_owner_id) == ("Chem", sid, uid("fac@x.com"))
    assert env.c.post("/api/units", headers=env.fac, json={"name": "U1", "course_id": cid}).status_code == 200  # content inside it is theirs

# 20-22
def test_csv_import_numbers_semesters_and_keeps_the_hierarchy_consistent(env):
    text = ("program,semester,semester_no,course,unit,topic\nMech,Semester 1,,Chem,U1,Water\nMech,Final year,8,Project,U1,Report\n"
            "Mech,Electives,,Free,U1,Any\nCivil,Sem II,,Survey,U1,Chain\n")
    r = env.c.post("/api/admin/import", headers=env.admin, json={"csv": text, "dry_run": False}); assert r.status_code == 200   # 20
    body = r.json(); assert body["valid_rows"] == 4 and body["created"]["semesters"] == 4
    assert body["warnings"] == ["Mech › Electives has no semester number yet. Set it under Programs."]
    with Session_() as s: nums = {x.name: x.semester_no for x in s.query(Semester)}
    assert nums == {"Semester 1": 1, "Final year": 8, "Electives": None, "Sem II": 2}
    consistent()                                                                                               # 22
    with main.engine.connect() as c: rep = main.integrity_report(c)
    assert all(not v for k, v in rep.items() if k != "semesters without a number") and len(rep["semesters without a number"]) == 1
    with Session_() as s: assert all(c.faculty_owner_id is None for c in s.query(Course))  # imported courses wait for an owner
    clash = env.c.post("/api/admin/import", headers=env.admin, json={"csv": "program,semester,semester_no,course,unit,topic\nMech,Another,1,X,U,T\n", "dry_run": True}).json()
    assert clash["valid_rows"] == 0 and "already has semester 1" in clash["errors"][0]["error"]
    assert env.c.post("/api/admin/import", headers=env.fac, json={"csv": text, "dry_run": True}).status_code == 403  # 21
    assert env.c.post("/api/admin/import", headers=env.stu, json={"csv": text, "dry_run": True}).status_code == 403

# Migration 0010
def test_semester_number_migration_fills_only_unambiguous_numbers(env):
    with Session_() as s:
        a, b = Program(name="A"), Program(name="B"); s.add_all([a, b]); s.flush()
        rows = {n: Semester(name=n, program_id=p.id) for n, p in (("Semester 2", a), ("Sem IV", a), ("Electives", a), ("Semester III", b), ("Semester 3", b), ("Semester 1", b))}
        s.add_all(rows.values()); s.add(Semester(name="Taken", program_id=a.id, semester_no=5)); s.add(Semester(name="Semester 5", program_id=a.id)); s.commit()
        ids_ = {n: x.id for n, x in rows.items()}
    with main.engine.begin() as c: assert main.semester_numbers(c) == 3
    with Session_() as s: got = {x.name: x.semester_no for x in s.query(Semester)}
    assert got == {"Semester 2": 2, "Sem IV": 4, "Electives": None, "Semester III": None, "Semester 3": None, "Semester 1": 1, "Taken": 5, "Semester 5": None}
    with main.engine.begin() as c: assert main.semester_numbers(c) == 0
    assert "0010_semesters_semester_no" in main.applied_migrations() and ids_
