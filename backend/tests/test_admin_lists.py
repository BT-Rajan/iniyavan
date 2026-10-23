from main import Session_, User, Progress, Bookmark, Course, Program

def tree(env): return env.c.get("/api/tree", headers=env.admin).json()
def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).one().id

def test_admin_course_list_searches_filters_sorts_and_pages(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Thermo,U1,Heat,h\n,,,,Work,w\nMech,Semester 2,Fluids,U1,Flow,f\nCivil,Semester 1,Surveying,U1,Levels,l\n")
    get = lambda **kw: env.c.get("/api/admin/courses", headers=env.admin, params=kw).json()
    r = get(); assert r["total"] == 3 and [c["name"] for c in r["items"]] == ["Fluids", "Surveying", "Thermo"]
    thermo = next(c for c in r["items"] if c["name"] == "Thermo")
    assert (thermo["program"], thermo["semester"], thermo["units"], thermo["topics"], thermo["owner"]) == ("Mech", "Semester 1", 1, 2, None)
    assert [c["name"] for c in get(q="civil")["items"]] == ["Surveying"]  # program names match too
    assert {c["name"] for c in get(program_id=thermo["program_id"])["items"]} == {"Thermo", "Fluids"}
    assert get(order="topics")["items"][0]["name"] == "Thermo" and get(order="name_desc")["items"][0]["name"] == "Thermo"
    page2 = get(limit=2, offset=2); assert page2["total"] == 3 and [c["name"] for c in page2["items"]] == ["Thermo"]
    assert env.c.put(f"/api/courses/{thermo['id']}/archive", headers=env.admin, json={"archived": True}).status_code == 200
    assert get()["total"] == 2 and [c["name"] for c in get(status="archived")["items"]] == ["Thermo"] and get(status="all")["total"] == 3
    assert env.c.get("/api/admin/courses", headers=env.fac).status_code == 403 and env.c.get("/api/admin/courses", headers=env.stu).status_code == 403

def test_deleting_a_user_removes_their_records_but_keeps_content(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Thermo,U1,Heat,h\n")
    p = tree(env)[0]; course = p["semesters"][0]["courses"][0]; tid = course["units"][0]["topics"][0]["id"]
    env.add_user("gone@x.com", program=p["id"], semester=1); h = env.login("gone@x.com")
    assert env.c.post(f"/api/topics/{tid}/read", headers=h).status_code == 200 and env.c.put(f"/api/topics/{tid}/bookmark", headers=h).status_code == 200
    env.c.put(f"/api/courses/{course['id']}/owner", headers=env.admin, json={"faculty_owner_id": uid("fac@x.com")})
    gid = uid("gone@x.com")
    assert env.c.delete(f"/api/admin/users/{gid}", headers=env.admin).json() == {"ok": True}
    with Session_() as s:
        assert s.get(User, gid) is None and not s.query(Progress).filter_by(user_id=gid).count() and not s.query(Bookmark).filter_by(user_id=gid).count()
    assert env.c.post("/api/login", json={"email": "gone@x.com", "password": "pw"}).status_code in (401, 403)
    assert env.c.delete(f"/api/admin/users/{uid('fac@x.com')}", headers=env.admin).status_code == 200  # an owner: the course stays, now without an owner
    with Session_() as s:
        c = s.get(Course, course["id"]); assert c is not None and c.faculty_owner_id is None and s.get(Program, p["id"]) is not None
    assert env.c.delete(f"/api/admin/users/{uid('admin@x.com')}", headers=env.admin).status_code == 400  # never yourself
    assert env.c.delete(f"/api/admin/users/{uid('stu@x.com')}", headers=env.stu).status_code == 403 and env.c.delete("/api/admin/users/9999", headers=env.admin).status_code == 404
