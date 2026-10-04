import main
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

def first_topic(env):
    return tree(env)[0]["semesters"][0]["courses"][0]["units"][0]["topics"][0]["id"]

def test_topic_versions_record_edits_keep_a_baseline_and_restore_without_losing_anything(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,original\n")
    tid = first_topic(env); un = tree(env)[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    body = lambda **k: {"title": "Water", "unit_id": un, "content": "original", **k}
    vs = lambda: env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).json()
    assert [v["note"] for v in vs()] == ["Imported from CSV"] and vs()[0]["current"]
    assert env.c.put(f"/api/topics/{tid}", headers=env.admin, json=body()).status_code == 200 and len(vs()) == 1  # saving unchanged text adds nothing
    env.c.put(f"/api/topics/{tid}", headers=env.admin, json=body(content="second draft"))
    env.c.put(f"/api/topics/{tid}", headers=env.admin, json=body(content="third draft", guideline="g"))
    got = vs(); assert [v["note"] for v in got] == ["Edited", "Edited", "Imported from CSV"] and got[0]["current"] and not got[1]["current"] and got[0]["by"] == "admin@x.com"
    old = env.c.get(f"/api/topic-versions/{got[2]['id']}", headers=env.admin).json()
    assert old["content"] == "original" and old["now"]["content"] == "third draft" and old["topic_id"] == tid
    assert env.c.post(f"/api/topic-versions/{got[2]['id']}/restore", headers=env.admin).status_code == 200
    assert env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["content"] == "original" and env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["guideline"] == ""
    after = vs(); assert len(after) == 4 and after[0]["note"].startswith("Restored") and after[0]["current"]
    assert any(env.c.get(f"/api/topic-versions/{v['id']}", headers=env.admin).json()["content"] == "third draft" for v in after)  # what it replaced is still there

def test_old_topic_gets_a_baseline_on_first_edit_and_permissions_and_deletes_hold(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n")
    tid = first_topic(env); un = tree(env)[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    with Session_() as s: s.query(main.TopicVersion).delete(); s.commit()  # as if the topic predates version history
    assert env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).json() == []
    env.c.put(f"/api/topics/{tid}", headers=env.admin, json={"title": "Water", "unit_id": un, "content": "changed"})
    got = env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).json()
    assert [v["note"] for v in got] == ["Edited", "Before the first recorded edit"] and got[1]["by"] is None
    assert env.c.get(f"/api/topic-versions/{got[1]['id']}", headers=env.admin).json()["content"] == "w"
    for hd in (env.stu, env.fac):  # students never; faculty only for courses they own
        assert env.c.get(f"/api/topics/{tid}/versions", headers=hd).status_code == 403
        assert env.c.get(f"/api/topic-versions/{got[0]['id']}", headers=hd).status_code == 403
        assert env.c.post(f"/api/topic-versions/{got[0]['id']}/restore", headers=hd).status_code == 403
    assert env.c.get("/api/topic-versions/9999", headers=env.admin).status_code == 404
    assert env.c.delete(f"/api/topics/{tid}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.query(main.TopicVersion).count() == 0
    assert env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).status_code == 404

def test_history_is_capped_and_a_csv_reimport_is_recorded(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,v0\n")
    tid = first_topic(env)
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,v1\n")
    assert [v["note"] for v in env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).json()] == ["Imported from CSV", "Imported from CSV"]
    un = tree(env)[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    for i in range(main.VERSIONS_KEPT + 5): env.c.put(f"/api/topics/{tid}", headers=env.admin, json={"title": "Water", "unit_id": un, "content": f"e{i}"})
    got = env.c.get(f"/api/topics/{tid}/versions", headers=env.admin).json()
    assert len(got) == main.VERSIONS_KEPT and got[0]["current"]

def make_two_courses(env):
    env.csv("program,semester,course,unit,topic,content,sample_content\nMech,Semester 1,Chem,U1,Water,water notes,sample\n,,,,Fuel,fuel notes,\n,Semester 2,Physics,P1,Motion,m,\n")
    sem = tree(env)[0]["semesters"]; chem = sem[0]["courses"][0]; phys = sem[1]["courses"][0]
    return chem, phys

def test_copy_topic_makes_a_draft_in_another_course_and_keeps_names_unique(env):
    chem, phys = make_two_courses(env); water = chem["units"][0]["topics"][0]["id"]; pu = phys["units"][0]["id"]
    cp = lambda hd, tid, **b: env.c.post(f"/api/topics/{tid}/copy", headers=hd, json=b)
    r = cp(env.admin, water, unit_id=pu); assert r.status_code == 200 and r.json()["title"] == "Water"
    new = env.c.get(f"/api/topics/{r.json()['id']}", headers=env.admin).json()
    assert new["content"] == "water notes" and new["sample_content"] == "sample" and new["published"] is False and new["course"] == "Physics" and new["unit"] == "P1"
    assert env.c.get(f"/api/topics/{r.json()['id']}/versions", headers=env.admin).json()[0]["note"].startswith("Copied from Chem › U1 › Water")
    assert cp(env.admin, water, unit_id=pu).json()["title"] == "Water (copy)" and cp(env.admin, water, unit_id=pu).json()["title"] == "Water (copy 2)"
    assert [t["title"] for t in tree(env)[0]["semesters"][1]["courses"][0]["units"][0]["topics"]] == ["Motion", "Water", "Water (copy)", "Water (copy 2)"]
    assert cp(env.admin, water, unit_id=chem["units"][0]["id"]).json()["title"] == "Water (copy)"  # copying inside the same unit works too
    assert cp(env.admin, water).status_code == 400 and cp(env.admin, water, unit_id=999).status_code == 400 and cp(env.admin, 999, unit_id=pu).status_code == 404
    assert cp(env.stu, water, unit_id=pu).status_code == 403
    assert cp(env.fac, water, unit_id=pu).status_code == 403  # faculty can only copy into a course they own
    env.c.put(f"/api/courses/{phys['id']}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")})
    assert cp(env.fac, water, unit_id=pu).status_code == 200
    env.c.put(f"/api/topics/{water}/publish", headers=env.admin, json={"published": False})  # someone else's draft is not copyable
    env.c.put(f"/api/courses/{chem['id']}/owner", headers=env.admin, json={"user_id": None})
    assert cp(env.fac, water, unit_id=pu).status_code == 404

def test_copy_unit_takes_topics_and_quizzes_as_drafts_and_remaps_question_topics(env):
    chem, phys = make_two_courses(env); u1 = chem["units"][0]; water, fuel = [t["id"] for t in u1["topics"]]
    q = env.c.post("/api/quizzes", headers=env.admin, json={"unit_id": u1["id"], "title": "Check", "pass_percent": 60, "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.admin, json={"questions": [
        {"text": "Q1", "options": ["a", "b"], "correct": 1, "topic_id": fuel}, {"text": "Q2", "options": ["a", "b", "c"], "correct": 0, "explanation": "why"}]})
    env.c.put(f"/api/topics/{fuel}/publish", headers=env.admin, json={"published": False})
    r = env.c.post(f"/api/units/{u1['id']}/copy", headers=env.admin, json={"course_id": phys["id"]}).json()
    assert (r["name"], r["topics"], r["quizzes"]) == ("U1", 2, 1)
    nu = next(x for x in tree(env)[0]["semesters"][1]["courses"][0]["units"] if x["id"] == r["id"])
    assert [t["title"] for t in nu["topics"]] == ["Water", "Fuel"] and all(t["published"] is False for t in nu["topics"]) and nu["quizzes"][0]["published"] is False and nu["quizzes"][0]["questions"] == 2
    got = env.c.get(f"/api/quizzes/{nu['quizzes'][0]['id']}", headers=env.admin).json()
    assert [(x["text"], x["correct"], x["topic_id"]) for x in got["questions"]] == [("Q1", 1, nu["topics"][1]["id"]), ("Q2", 0, None)] and got["questions"][1]["explanation"] == "why"
    again = env.c.post(f"/api/units/{u1['id']}/copy", headers=env.admin, json={"course_id": phys["id"], "with_quizzes": False}).json()
    assert again["name"] == "U1 (copy)" and again["quizzes"] == 0
    assert env.c.post(f"/api/units/{u1['id']}/copy", headers=env.admin, json={}).status_code == 400 and env.c.post("/api/units/999/copy", headers=env.admin, json={"course_id": 1}).status_code == 404
    assert env.c.post(f"/api/units/{u1['id']}/copy", headers=env.fac, json={"course_id": phys["id"]}).status_code == 403
    env.c.put(f"/api/courses/{phys['id']}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")})  # faculty owns only the target: no draft topics, no quizzes of the original
    fr = env.c.post(f"/api/units/{u1['id']}/copy", headers=env.fac, json={"course_id": phys["id"]}).json()
    assert fr["topics"] == 1 and fr["quizzes"] == 0

def test_dashboard_card_lists_search_sort_page_and_point_at_details(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n,,,,Fuel,f\n,,,,Air,a\n")
    t = tree(env)[0]; course = t["semesters"][0]["courses"][0]; topics = course["units"][0]["topics"]
    for x in topics[:2]: env.c.put(f"/api/topics/{x['id']}/publish", headers=env.admin, json={"published": False})
    for i in range(7): env.add_user(f"stud{i}@x.com")  # active students with no program: all unplaced and never opened
    get = lambda kind, h=None, **kw: env.c.get("/api/overview/list", headers=h or env.admin, params={"kind": kind, **kw})
    page1 = get("unenrolled").json(); assert page1["total"] >= 7 and len(page1["items"]) == 5 and page1["items"][0]["target"]["type"] == "user"
    page2 = get("unenrolled", offset=5).json(); assert page2["items"] and not {i["id"] for i in page1["items"]} & {i["id"] for i in page2["items"]}
    names = [i["title"] for i in get("students", order="name", limit=50).json()["items"]]; assert names == sorted(names, key=str.lower)
    assert [i["title"] for i in get("students", order="name_desc", limit=50).json()["items"]] == names[::-1]
    hit = get("students", q="stud3@x.com").json(); assert hit["total"] == 1 and hit["items"][0]["sub"] == "stud3@x.com"
    d = get("drafts").json(); assert d["total"] == 2 and d["items"][0]["target"]["type"] == "topic"
    assert get("topics").json()["total"] == 3 and get("courses").json()["items"][0]["target"]["type"] == "course"
    assert get("unowned").json()["total"] == 1 and get("empty_courses").json()["total"] == 0
    assert get("nope").status_code == 404 and get("students", h=env.fac).status_code == 403 and get("courses", h=env.stu).status_code == 403
    assert get("courses", h=env.fac).json()["total"] == 0 and get("drafts", h=env.fac).json()["total"] == 0  # faculty see only their own courses
