from main import Session_, User

def tree(env): return env.c.get("/api/tree", headers=env.admin).json()

def test_overview_tells_admin_what_needs_attention_and_faculty_only_their_courses(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n,,,,Fuel,f\n")
    t = tree(env)[0]; course = t["semesters"][0]["courses"][0]; topics = course["units"][0]["topics"]
    env.c.put(f"/api/topics/{topics[1]['id']}/publish", headers=env.admin, json={"published": False})
    env.add_user("new@x.com")  # an active student with no program or semester
    a = env.c.get("/api/overview", headers=env.admin).json(); kinds = {x["kind"]: x["count"] for x in a["attention"]}
    assert a["courses"] == 1 and a["topics"] == 2 and a["drafts"] == 1 and a["people"]["faculty"] == 1 and a["people"]["active_week"] == 0
    assert kinds["drafts"] == 1 and kinds["unowned"] == 1 and kinds["unenrolled"] >= 1 and kinds["never_opened"] >= 1
    f = env.c.get("/api/overview", headers=env.fac).json()  # faculty own nothing yet: no college-wide numbers leak
    assert f["courses"] == 0 and "people" not in f and f["attention"] == []
    assert env.c.get("/api/overview", headers=env.stu).status_code == 403

def test_rollover_previews_then_moves_students_up_and_handles_the_last_semester(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,A,U,T,x\nMech,Semester 2,B,U,T,x\n")
    pid = tree(env)[0]["id"]
    for e, sem in (("s1@x.com", 1), ("s2@x.com", 2), ("none@x.com", None)): env.add_user(e, program=pid, semester=sem)
    env.add_user("other@x.com", program=pid + 99, semester=1)  # another program: untouched
    url = f"/api/admin/programs/{pid}/rollover"
    prev = env.c.post(url, headers=env.admin, json={}).json()
    assert prev["dry_run"] and (prev["moved"], prev["finishing"], prev["unplaced"], prev["last_semester"]) == (1, 1, 1, 2)
    sem = lambda e: next(u.semester for u in Session_().query(User) if u.email == e)
    assert sem("s1@x.com") == 1  # the preview changed nothing
    done = env.c.post(url, headers=env.admin, json={"dry_run": False}).json(); assert done["moved"] == 1
    assert sem("s1@x.com") == 2 and sem("s2@x.com") == 2 and sem("none@x.com") is None and sem("other@x.com") == 1
    act = lambda e: next(u.active for u in Session_().query(User) if u.email == e)
    assert act("s2@x.com")  # keep is the default
    env.c.post(url, headers=env.admin, json={"dry_run": False, "finishing": "deactivate"})
    assert not act("s1@x.com") and not act("s2@x.com") and act("none@x.com")
    assert env.c.post(url, headers=env.admin, json={"finishing": "bad"}).status_code == 400
    assert env.c.post(url, headers=env.fac, json={}).status_code == 403 and env.c.post("/api/admin/programs/999/rollover", headers=env.admin, json={}).status_code == 404

def uid(email):
    with Session_() as s: return next(u.id for u in s.query(User) if u.email == email)
def user(email):
    with Session_() as s: return next(s.expunge(u) or u for u in s.query(User) if u.email == email)

def test_bulk_actions_apply_to_many_users_and_skip_what_cannot_apply(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,A,U,T,x\n")
    pid = tree(env)[0]["id"]
    for e in ("a@x.com", "b@x.com", "c@x.com"): env.add_user(e)
    ids = [uid(e) for e in ("a@x.com", "b@x.com", "c@x.com")]
    bulk = lambda hd=None, **b: env.c.post("/api/admin/users/bulk", headers=hd or env.admin, json=b)
    r = bulk(ids=ids, action="set_placement", program_id=pid, semester=3).json()
    assert r["changed"] == 3 and all((user(e).program_id, user(e).semester) == (pid, 3) for e in ("a@x.com", "b@x.com", "c@x.com"))
    r = bulk(ids=ids + [uid("fac@x.com")], action="set_placement", program_id=pid, semester=2).json()  # faculty have no placement
    assert r["changed"] == 3 and r["skipped"][0]["reason"].startswith("Only students")
    assert bulk(ids=ids, action="set_placement").status_code == 400 and bulk(ids=ids, action="set_placement", program_id=999).status_code == 400
    r = bulk(ids=ids[:2] + [uid("admin@x.com")], action="disable").json()  # never yourself
    assert r["changed"] == 2 and r["skipped"] == [{"id": uid("admin@x.com"), "name": "admin@x.com", "reason": "That is your own account"}]
    assert not user("a@x.com").active and user("c@x.com").active
    assert env.c.post("/api/login", json={"email": "a@x.com", "password": "pw"}).status_code in (401, 403)
    r = bulk(ids=ids, action="enable").json(); assert r["changed"] == 2 and r["skipped_count"] == 1  # c was never off
    r = bulk(ids=ids + [uid("admin@x.com")], action="reset_passwords").json()
    assert r["changed"] == 3 and len(r["credentials"]) == 3 and r["skipped_count"] == 1 and all(len(c["password"]) >= 8 for c in r["credentials"])
    c0 = r["credentials"][0]; ok = env.c.post("/api/login", json={"email": c0["email"], "password": c0["password"]}).json()
    assert ok["user"]["must_change"] is True  # the one-time password works and forces a new one
    assert env.c.post("/api/login", json={"email": c0["email"], "password": "pw"}).status_code == 401
    assert bulk(ids=[], action="enable").status_code == 400 and bulk(ids=ids, action="nuke").status_code == 400 and bulk(ids=list(range(1, 202)), action="reset_passwords").status_code == 400
    for hd in (env.fac, env.stu): assert bulk(hd, ids=ids, action="disable").status_code == 403

def test_bulk_disable_of_faculty_reports_courses_left_without_an_owner(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,A,U,T,x\n")
    cid = tree(env)[0]["semesters"][0]["courses"][0]["id"]
    assert env.c.put(f"/api/courses/{cid}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")}).status_code == 200
    r = env.c.post("/api/admin/users/bulk", headers=env.admin, json={"ids": [uid("fac@x.com")], "action": "disable"}).json()
    assert r["changed"] == 1 and r["courses_needing_owner"] == 1
