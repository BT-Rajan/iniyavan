from main import Session_, User

def uid(email):
    with Session_() as s: return next(u.id for u in s.query(User) if u.email == email)

def setup(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n,,,,Fuel,f\n,,,U2,Air,a\n")
    t = env.c.get("/api/tree", headers=env.admin).json()[0]; sem = t["semesters"][0]; co = sem["courses"][0]
    env.add_user("s2@x.com", program=t["id"], semester=1); env.s2 = env.login("s2@x.com")
    r = env.c.put(f"/api/courses/{co['id']}", headers=env.admin, json={"name": "Chem", "semester_id": sem["id"], "faculty_owner_id": uid("fac@x.com")}); assert r.status_code == 200, r.text
    ids = dict(prog=t["id"], sem=sem["id"], course=co["id"], u1=co["units"][0]["id"], u2=co["units"][1]["id"], water=co["units"][0]["topics"][0]["id"], fuel=co["units"][0]["topics"][1]["id"], air=co["units"][1]["topics"][0]["id"])
    return ids
def arch(env, h, kind, rid, on=True): return env.c.put(f"/api/{kind}/{rid}/archive", headers=h, json={"archived": on})
def course_of(env, h): return env.c.get("/api/tree", headers=h).json()[0]["semesters"][0]["courses"][0]
def topic(env, h, tid): return env.c.get(f"/api/topics/{tid}", headers=h)

def test_archiving_a_course_makes_it_unavailable_to_students_and_restoring_brings_it_back(env):
    i = setup(env)
    assert topic(env, env.s2, i["water"]).status_code == 200
    assert arch(env, env.admin, "courses", i["course"]).status_code == 200
    r = topic(env, env.s2, i["water"]); assert r.status_code == 403 and "unavailable right now" in r.json()["detail"]
    c = course_of(env, env.s2); assert c["archived"] and c["units"] == [] and c["name"] == "Chem"  # a locked name, nothing inside
    assert topic(env, env.admin, i["water"]).status_code == 200 and topic(env, env.fac, i["water"]).status_code == 200  # admin and the owner can still open it
    a = course_of(env, env.admin); assert a["archived"] and a["archived_self"] and len(a["units"]) == 2
    assert env.c.get("/api/overview", headers=env.admin).json()["courses"] == 0  # archived courses leave the dashboard numbers
    assert arch(env, env.admin, "courses", i["course"], False).json()["archived"] is False
    assert topic(env, env.s2, i["water"]).status_code == 200 and not course_of(env, env.s2)["archived"]
    assert env.c.get("/api/overview", headers=env.admin).json()["courses"] == 1

def test_archiving_a_program_archives_everything_under_it_and_restoring_returns_it(env):
    i = setup(env)
    assert arch(env, env.admin, "topics", i["fuel"]).status_code == 200  # archived on its own first
    assert arch(env, env.admin, "programs", i["prog"]).status_code == 200
    t = env.c.get("/api/tree", headers=env.admin).json()[0]; sm = t["semesters"][0]; co = sm["courses"][0]
    assert t["archived"] and sm["archived"] and co["archived"] and all(u["archived"] for u in co["units"]) and all(x["archived"] for u in co["units"] for x in u["topics"])
    assert topic(env, env.s2, i["air"]).status_code == 403
    r = arch(env, env.admin, "courses", i["course"], False); assert r.status_code == 400 and "program" in r.json()["detail"]  # the program has to come back first
    assert arch(env, env.admin, "programs", i["prog"], False).status_code == 200
    assert topic(env, env.s2, i["water"]).status_code == 200 and topic(env, env.s2, i["air"]).status_code == 200
    assert topic(env, env.s2, i["fuel"]).status_code == 403  # what was archived on its own stays archived
    assert arch(env, env.admin, "topics", i["fuel"], False).status_code == 200 and topic(env, env.s2, i["fuel"]).status_code == 200

def test_archived_topics_and_units_are_hidden_from_students_but_not_staff(env):
    i = setup(env)
    arch(env, env.fac, "topics", i["fuel"]); arch(env, env.fac, "units", i["u2"])
    titles = lambda h: [x["title"] for u in course_of(env, h)["units"] for x in u["topics"]]
    assert titles(env.s2) == ["Water"] and sorted(titles(env.admin)) == ["Air", "Fuel", "Water"] and len(course_of(env, env.s2)["units"]) == 1
    assert topic(env, env.s2, i["fuel"]).status_code == 403 and topic(env, env.s2, i["air"]).status_code == 403
    assert env.c.get("/api/overview/list", headers=env.fac, params={"kind": "topics", "limit": 50}).json()["total"] == 1  # staff counts leave them out too

def test_who_may_archive(env):
    i = setup(env)
    assert arch(env, env.fac, "courses", i["course"]).status_code == 200 and arch(env, env.fac, "courses", i["course"], False).status_code == 200  # the owner archives and restores
    assert arch(env, env.fac, "programs", i["prog"]).status_code == 403 and arch(env, env.fac, "semesters", i["sem"]).status_code == 403
    assert arch(env, env.s2, "courses", i["course"]).status_code == 403
    env.add_user("fac2@x.com", "faculty"); other = env.login("fac2@x.com")
    assert arch(env, other, "courses", i["course"]).status_code == 403 and arch(env, other, "topics", i["water"]).status_code == 403  # not their course
    arch(env, env.admin, "semesters", i["sem"])
    r = arch(env, env.fac, "courses", i["course"], False); assert r.status_code == 400 and "Ask an admin" in r.json()["detail"]
    assert arch(env, env.admin, "nope", 1).status_code == 404 and arch(env, env.admin, "topics", 9999).status_code == 404

def test_admin_programs_list_hides_archived_unless_asked(env):
    i = setup(env); arch(env, env.admin, "programs", i["prog"])
    get = lambda **kw: env.c.get("/api/admin/programs", headers=env.admin, params=kw).json()
    assert get()["total"] == 0 and get(status="archived")["items"][0]["archived"] is True and get(status="all")["total"] == 1

def test_archived_quiz_unit_and_reports(env):
    i = setup(env)
    qid = env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": i["u1"], "title": "Q", "pass_percent": 50, "published": True}).json()["id"]
    assert env.c.put(f"/api/quizzes/{qid}/questions", headers=env.fac, json={"questions": [{"text": "?", "options": ["a", "b"], "correct": 0}]}).status_code == 200
    assert env.c.get(f"/api/quizzes/{qid}", headers=env.s2).status_code == 200
    arch(env, env.fac, "units", i["u1"])
    assert env.c.get(f"/api/quizzes/{qid}", headers=env.s2).status_code == 403 and env.c.post(f"/api/quizzes/{qid}/attempt", headers=env.s2, json={"answers": [0]}).status_code == 403
    assert env.c.get(f"/api/quizzes/{qid}", headers=env.fac).status_code == 200  # the owner can still open it
    arch(env, env.fac, "units", i["u1"], False); arch(env, env.fac, "courses", i["course"])
    assert env.c.get("/api/reports/courses", headers=env.admin).json() == []
