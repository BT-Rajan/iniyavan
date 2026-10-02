"""Course owner model: one faculty owner per course, assigned only by admins, and the only faculty member who may edit the course."""
import main
from main import Session_, User, Course, CourseFaculty, Unit, Topic, Quiz, Progress
from tests.test_access import CSV, ids, enrol, titles

def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def owner_of(cid):
    with Session_() as s: return s.get(Course, cid).faculty_owner_id
def setup(env):
    env.csv(CSV); i = ids(); env.add_user("fac2@x.com", "faculty"); env.fac2 = env.login("fac2@x.com")
    i["chem"], i["work"] = i["course"]["Chem"], i["course"]["Workshop"]; i["cu"] = i["unit"][i["chem"]]; i["water"] = i["topic"]["Water"]
    return i
def own(env, cid, email, h=None): return env.c.put(f"/api/courses/{cid}/owner", headers=h or env.admin, json={"user_id": uid(email) if email else None}).status_code
def edits(env, h, i):
    """Status codes for every content operation a course owner has, on Chem."""
    c = env.c; out = {}
    out["create_unit"] = c.post("/api/units", headers=h, json={"name": "New unit", "course_id": i["chem"]}).status_code
    out["edit_unit"] = c.put(f"/api/units/{i['cu']}", headers=h, json={"name": "U1", "course_id": i["chem"]}).status_code
    out["create_topic"] = c.post("/api/topics", headers=h, json={"title": "New topic", "unit_id": i["cu"], "published": False}).status_code
    out["edit_topic"] = c.put(f"/api/topics/{i['water']}", headers=h, json={"title": "Water", "unit_id": i["cu"], "content": "edited"}).status_code
    out["publish_topic"] = c.put(f"/api/topics/{i['water']}/publish", headers=h, json={"published": True}).status_code
    out["publish_unit"] = c.put(f"/api/units/{i['cu']}/publish", headers=h, json={"published": True}).status_code
    out["create_quiz"] = c.post("/api/quizzes", headers=h, json={"unit_id": i["cu"], "title": "Q"}).status_code
    return out
ALLOWED = lambda d: set(d.values()) == {200}
DENIED = lambda d: set(d.values()) == {403}

# 1-6: who can assign an owner
def test_admin_assigns_changes_and_removes_owner(env):
    i = setup(env)
    assert own(env, i["chem"], "fac@x.com") == 200 and owner_of(i["chem"]) == uid("fac@x.com")      # 1 assign
    assert own(env, i["chem"], "fac2@x.com") == 200 and owner_of(i["chem"]) == uid("fac2@x.com")    # 2 change
    assert own(env, i["chem"], None) == 200 and owner_of(i["chem"]) is None                          # 3 remove
    assert env.c.get(f"/api/topics/{i['water']}", headers=env.admin).status_code == 200              # content untouched

def test_only_admins_assign_owners(env):
    i = setup(env)
    for h in (env.fac, env.fac2, env.stu):                                                            # 4-6 non-admin, faculty, student
        assert own(env, i["chem"], "fac@x.com", h) == 403
        assert env.c.put(f"/api/admin/users/{uid('fac@x.com')}/courses", headers=h, json={"course_ids": [i["chem"]]}).status_code == 403
        assert env.c.post("/api/courses", headers=h, json={"name": "X", "semester_id": 1, "faculty_owner_id": uid("fac@x.com")}).status_code == 403
    assert owner_of(i["chem"]) is None

def test_owner_must_be_an_active_faculty_member(env):
    i = setup(env); env.add_user("off@x.com", "faculty")
    with Session_() as s: s.query(User).filter_by(email="off@x.com").update({"active": False}); s.commit()
    for who in ("stu@x.com", "admin@x.com", "off@x.com"): assert own(env, i["chem"], who) == 400
    assert env.c.put(f"/api/courses/{i['chem']}/owner", headers=env.admin, json={"user_id": 99999}).status_code == 400
    assert env.c.put("/api/courses/99999/owner", headers=env.admin, json={"user_id": uid("fac@x.com")}).status_code == 404
    assert owner_of(i["chem"]) is None

# 7-12: what the owner can do, and what other faculty can't
def test_owner_manages_content_and_other_faculty_cannot(env):
    i = setup(env); own(env, i["chem"], "fac@x.com")
    assert ALLOWED(edits(env, env.fac, i))                                                            # 7-11
    assert DENIED(edits(env, env.fac2, i))                                                            # 12 (no additional editors)
    assert env.c.delete(f"/api/topics/{i['water']}", headers=env.fac2).status_code == 403
    assert env.c.delete(f"/api/topics/{i['water']}", headers=env.fac).status_code == 200

def test_legacy_assignment_rows_grant_nothing(env):
    i = setup(env)
    with Session_() as s: s.add(CourseFaculty(user_id=uid("fac2@x.com"), course_id=i["chem"])); s.commit()
    assert DENIED(edits(env, env.fac2, i))

# 13-17: changing the owner moves the rights, immediately and with old tokens
def test_owner_change_moves_edit_rights(env):
    i = setup(env); own(env, i["chem"], "fac@x.com")
    assert ALLOWED(edits(env, env.fac, i)) and DENIED(edits(env, env.fac2, i))                        # 13-14
    with Session_() as s: before = (s.query(Unit).count(), s.query(Topic).count(), s.query(Quiz).count())
    assert own(env, i["chem"], "fac2@x.com") == 200                                                   # 15
    assert DENIED(edits(env, env.fac, i))                                                             # 16
    assert ALLOWED(edits(env, env.fac2, i))                                                           # 17
    with Session_() as s: assert (s.query(Unit).count(), s.query(Topic).count(), s.query(Quiz).count()) >= before

def test_owner_change_keeps_units_topics_quizzes_and_progress(env):
    i = setup(env); own(env, i["chem"], "fac@x.com"); enrol("stu@x.com", i["prog"]["Mech"], 1)
    q = env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": i["cu"], "title": "Q", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.fac, json={"questions": [{"text": "t", "options": ["a", "b"], "correct": 0}]})
    env.c.post(f"/api/topics/{i['water']}/read", headers=env.stu); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]})
    snap = lambda: (lambda s: (s.query(Unit).filter_by(course_id=i["chem"]).count(), s.query(Topic).filter_by(unit_id=i["cu"]).count(),
                               s.query(Quiz).filter_by(unit_id=i["cu"]).count(), s.query(Progress).count(), s.query(main.Attempt).count()))(Session_())
    before = snap(); own(env, i["chem"], "fac2@x.com"); own(env, i["chem"], None)
    assert snap() == before and env.c.get(f"/api/quizzes/{q}", headers=env.stu).json()["best"] == 100

def test_removing_the_owner_leaves_only_admins_able_to_edit(env):
    i = setup(env); assert own(env, i["chem"], "fac@x.com") == 200 and ALLOWED(edits(env, env.fac, i))
    assert own(env, i["chem"], None) == 200 and owner_of(i["chem"]) is None
    assert DENIED(edits(env, env.fac, i)) and ALLOWED(edits(env, env.admin, i))
    with Session_() as s: assert s.query(User).filter_by(email="fac@x.com").first() is not None

# 18-19 and role changes: the owner stays on record but can't edit
def test_disabled_owner_cannot_edit_and_admin_reassigns(env):
    i = setup(env); own(env, i["chem"], "fac@x.com"); old_token = env.fac
    r = env.c.patch(f"/api/admin/users/{uid('fac@x.com')}", headers=env.admin, json={"active": False})
    assert r.status_code == 200 and r.json()["courses_needing_owner"] == 1
    assert env.c.put(f"/api/topics/{i['water']}/publish", headers=old_token, json={"published": True}).status_code == 401   # 18
    assert env.c.post("/api/login", json={"email": "fac@x.com", "password": "pw"}).status_code == 403
    assert owner_of(i["chem"]) == uid("fac@x.com")                                                   # still identifiable
    chem = lambda: next(c for p in env.c.get("/api/tree", headers=env.admin).json() for sm in p["semesters"] for c in sm["courses"] if c["id"] == i["chem"])
    assert chem()["owner_problem"] == "Owner fac@x.com is disabled"
    assert own(env, i["chem"], "fac2@x.com") == 200 and ALLOWED(edits(env, env.fac2, i))               # 19
    assert chem()["owner_problem"] == "" and chem()["owner"] == "fac2@x.com"

def test_owner_whose_role_changes_cannot_edit(env):
    i = setup(env); own(env, i["chem"], "fac@x.com")
    r = env.c.patch(f"/api/admin/users/{uid('fac@x.com')}", headers=env.admin, json={"role": "student"})
    assert r.json()["courses_needing_owner"] == 1 and owner_of(i["chem"]) == uid("fac@x.com")          # never reassigned automatically
    assert DENIED(edits(env, env.fac, i))
    p = env.c.get(f"/api/admin/programs/{i['prog']['Mech']}", headers=env.admin).json()
    assert {c["name"]: c["owner_problem"] for sm in p["semester_list"] for c in sm["course_list"]}["Chem"] == "Owner fac@x.com is no longer faculty"

# 20-23 and the rest of the structure: faculty never change it, owner or not
def test_faculty_cannot_change_academic_structure(env):
    i = setup(env); own(env, i["chem"], "fac@x.com"); mech, civil = i["prog"]["Mech"], i["prog"]["Civil"]
    sem = i["sem"][(mech, "Semester 1")]; other_sem = i["sem"][(civil, "Semester 1")]
    for h in (env.fac, env.stu):
        c = env.c
        assert c.post("/api/courses", headers=h, json={"name": "New", "semester_id": sem}).status_code == 403                      # 20
        assert c.put(f"/api/courses/{i['chem']}", headers=h, json={"name": "Chem", "semester_id": other_sem}).status_code == 403   # 21 move course
        assert c.put(f"/api/semesters/{sem}", headers=h, json={"name": "S", "program_id": civil}).status_code == 403              # 22
        assert c.put(f"/api/programs/{mech}", headers=h, json={"name": "M"}).status_code == 403                                   # 23
        assert c.post("/api/programs", headers=h, json={"name": "P"}).status_code == 403
        assert c.post("/api/semesters", headers=h, json={"name": "S", "program_id": mech}).status_code == 403
        for kind, rid in (("courses", i["chem"]), ("semesters", sem), ("programs", mech)): assert c.delete(f"/api/{kind}/{rid}", headers=h).status_code == 403
        assert c.put(f"/api/courses/{i['chem']}/links", headers=h, json={"semester_ids": [other_sem]}).status_code == 403
    with Session_() as s: co = s.get(Course, i["chem"]); assert (co.semester_id, co.program_id, co.name) == (sem, mech, "Chem")

# Admin course workflow
def test_admin_creates_course_with_or_without_owner_and_edits_keep_it(env):
    i = setup(env); sem = i["sem"][(i["prog"]["Mech"], "Semester 1")]
    r = env.c.post("/api/courses", headers=env.admin, json={"name": "Physics", "semester_id": sem, "faculty_owner_id": uid("fac@x.com")})
    assert r.status_code == 200 and owner_of(r.json()["id"]) == uid("fac@x.com")
    cid = env.c.post("/api/courses", headers=env.admin, json={"name": "Maths 2", "semester_id": sem}).json()["id"]; assert owner_of(cid) is None
    assert env.c.post("/api/courses", headers=env.admin, json={"name": "Bad", "semester_id": sem, "faculty_owner_id": uid("stu@x.com")}).status_code == 400
    assert env.c.put(f"/api/courses/{r.json()['id']}", headers=env.admin, json={"name": "Physics I", "semester_id": sem}).status_code == 200
    assert owner_of(r.json()["id"]) == uid("fac@x.com")                                                   # leaving the field out keeps the owner
    assert env.c.put(f"/api/courses/{r.json()['id']}", headers=env.admin, json={"name": "Physics I", "semester_id": sem, "faculty_owner_id": None}).status_code == 200
    assert owner_of(r.json()["id"]) is None

def test_users_page_and_course_owner_share_one_source_of_truth(env):
    i = setup(env); fac, fac2 = uid("fac@x.com"), uid("fac2@x.com")
    assert env.c.put(f"/api/admin/users/{fac}/courses", headers=env.admin, json={"course_ids": [i["chem"], i["work"]]}).status_code == 200
    assert owner_of(i["chem"]) == fac and owner_of(i["work"]) == fac
    assert own(env, i["work"], "fac2@x.com") == 200                                                       # taken over from the course side
    assert env.c.get(f"/api/admin/users/{fac}", headers=env.admin).json()["course_ids"] == [i["chem"]]
    assert env.c.get(f"/api/admin/users/{fac2}", headers=env.admin).json()["course_ids"] == [i["work"]]
    assert env.c.put(f"/api/admin/users/{fac}/courses", headers=env.admin, json={"course_ids": []}).status_code == 200 and owner_of(i["chem"]) is None
    assert env.c.put(f"/api/admin/users/{uid('stu@x.com')}/courses", headers=env.admin, json={"course_ids": [i["chem"]]}).status_code == 400
    faculty = env.c.get("/api/admin/users?role=faculty", headers=env.admin).json()["items"]; assert {u["email"] for u in faculty} == {"fac@x.com", "fac2@x.com"}

def test_faculty_tree_marks_my_courses_and_hides_others_drafts(env):
    i = setup(env); own(env, i["chem"], "fac@x.com"); own(env, i["work"], "fac2@x.com")
    env.c.post("/api/topics", headers=env.fac2, json={"title": "WDraft", "unit_id": i["unit"][i["work"]], "published": False})
    cs = {c["name"]: c for p in env.c.get("/api/tree", headers=env.fac).json() for sm in p["semesters"] for c in sm["courses"]}
    assert (cs["Chem"]["mine"], cs["Chem"]["editable"], cs["Workshop"]["mine"], cs["Workshop"]["editable"]) == (True, True, False, False)
    assert cs["Workshop"]["owner"] == "fac2@x.com" and "owner_problem" not in cs["Chem"]
    assert "WDraft" not in titles(env, env.fac) and "WDraft" in titles(env, env.fac2)
    assert [r["course"] for r in env.c.get("/api/reports/courses", headers=env.fac).json()] == ["Chem"]

# Migration 0009 from the old many-to-many assignments
def test_owner_migration_cases(env):
    env.csv(CSV + "Civil,Semester 3,Drawing,U1,Lines,x\n"); i = ids(); c = i["course"]
    env.add_user("fac2@x.com", "faculty"); env.add_user("gone@x.com", "faculty"); env.add_user("was@x.com", "student")
    with Session_() as s: s.query(User).filter_by(email="gone@x.com").update({"active": False}); s.commit()
    pairs = [(c["Chem"], "fac@x.com"),                                    # A: one active faculty member
             (c["Workshop"], "fac@x.com"), (c["Workshop"], "fac2@x.com"),   # B: several
             (c["Maths"], "was@x.com"),                                   # D: no longer faculty
             (c["Drawing"], "gone@x.com")]                                # D: disabled faculty
    with Session_() as s: s.add_all([CourseFaculty(user_id=uid(e), course_id=k) for k, e in pairs]); s.add(Course(name="Owned", faculty_owner_id=uid("fac2@x.com"))); s.commit()
    with main.engine.begin() as cx: assert main.owners_from_assignments(cx) == 1
    with main.engine.connect() as cx: rep = main.ownership_report(cx)[0]
    assert owner_of(c["Chem"]) == uid("fac@x.com") and all(owner_of(k) is None for k in (c["Workshop"], c["Maths"], c["Survey"], c["Drawing"]))
    assert rep["multiple_assigned"] == [c["Workshop"]] and rep["assigned_not_faculty"] == sorted([c["Maths"], c["Drawing"]]) and rep["no_faculty"] == [c["Survey"]]
    assert len(rep["owned"]) == 2 and rep["invalid_owner"] == []
    with Session_() as s: assert s.query(CourseFaculty).count() == len(pairs)                  # legacy rows kept
    with main.engine.begin() as cx: assert main.owners_from_assignments(cx) == 0                 # running again changes nothing
    own(env, c["Chem"], "fac2@x.com")
    with main.engine.begin() as cx: main.owners_from_assignments(cx)
    assert owner_of(c["Chem"]) == uid("fac2@x.com")                                             # an owner chosen by an admin is never overwritten
    assert {"0008_subjects_faculty_owner_id", "0009_course_owners_from_assignments"} <= set(main.applied_migrations())
