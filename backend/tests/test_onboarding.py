"""Phase 2 of the school/college onboarding: school or college, then program and grade or semester, then a student, a parent with children, or a teacher."""
import main
from main import Session_, User, GuardianLink, Program, Semester
from tests.test_registration import reg, GOOD  # noqa: F401  (the fixture)

def places():  # a school program with grades 6 and 7 (7 archived), and a college program with semester 1
    with Session_() as s:
        sch = Program(name="State Board", pattern="grade"); col = Program(name="B.E. Mechanical", pattern="semester"); s.add_all([sch, col]); s.flush()
        s.add_all([Semester(name="Grade 6", program_id=sch.id, semester_no=6), Semester(name="Grade 7", program_id=sch.id, semester_no=7, archived_at=main.dt.datetime.utcnow()),
                   Semester(name="Semester 1", program_id=col.id, semester_no=1)])
        s.commit(); return sch.id, col.id
def finish(reg, email):
    return reg.c.post("/api/register/verify", json={"email": email, "code": reg.code()})
KID = dict(name="Kavin", username="kavin.r", password="kidpass123")

def test_options_list_programs_by_school_or_college_with_open_terms(reg):
    sch, col = places(); o = reg.c.get("/api/register/options").json()
    assert o["school"] == [{"id": sch, "name": "State Board", "term": "Grade", "terms": [6]}]  # the archived grade is not offered
    assert o["college"] == [{"id": col, "name": "B.E. Mechanical", "term": "Semester", "terms": [1]}]

def test_a_college_student_picks_program_and_semester_and_is_placed(reg):
    sch, col = places()
    assert reg.start(level="college", program_id=sch, semester=6).status_code == 400  # a school program for a college student
    assert reg.start(level="college", program_id=col, semester=2).status_code == 400  # no semester 2
    assert reg.start(level="college", program_id=col, semester=1).status_code == 200
    u = finish(reg, "asha@college.edu").json()["user"]; assert (u["role"], u["level"], u["placed"]) == ("student", "college", True)
    with Session_() as s: x = s.query(User).filter_by(email="asha@college.edu").one(); assert (x.program_id, x.semester) == (col, 1)

def test_a_school_student_needs_no_roll_number_and_may_leave_the_program_for_later(reg):
    places(); assert reg.start(level="school", id_number="").status_code == 200
    u = finish(reg, "asha@college.edu").json()["user"]; assert (u["level"], u["placed"]) == ("school", False)
    assert reg.start(email="b@college.edu", level="college", id_number="").status_code == 400  # a college student still gives one

def test_a_parent_signs_up_with_children_who_sign_in_with_their_username(reg):
    sch, col = places(); parent = dict(who="parent", level="school", institution="", id_number="", email="mum@home.in")
    assert reg.start(**parent).status_code == 400  # at least one child
    assert reg.start(**parent, children=[dict(KID, username="Has Space")]).status_code == 400
    assert reg.start(**parent, children=[dict(KID, program_id=col, semester=1)]).status_code == 400  # a college program for a school child
    assert reg.start(**parent, children=[KID, dict(KID, name="Twin")]).status_code == 400  # the same username twice
    kids = [dict(KID, program_id=sch, semester=6), dict(name="Meera", username="meera", password="kidpass456")]
    assert reg.start(**parent, children=kids).status_code == 200
    with Session_() as s: assert s.query(User).filter_by(username="kavin.r").first() is None  # nothing exists before the code
    me = finish(reg, "mum@home.in").json()["user"]; assert (me["role"], me["relation"], me["level"]) == ("guardian", "parent", "school")
    r = reg.c.post("/api/login", json={"email": "kavin.r", "password": "kidpass123"}).json()["user"]
    assert (r["role"], r["username"], r["level"], r["placed"]) == ("student", "kavin.r", "school", True)
    tok = reg.c.post("/api/login", json={"email": "mum@home.in", "password": GOOD["password"]}).json()["token"]
    kids = reg.c.get("/api/guardian/students", headers={"Authorization": "Bearer " + tok}).json()["students"]
    assert [(k["name"], k["username"], k["place"], k["status"]) for k in kids] == [("Kavin", "kavin.r", "State Board · Grade 6", "active"), ("Meera", "meera", "", "active")]
    assert reg.c.get("/api/guardian/students", headers=reg.stu).status_code == 403

def test_a_username_taken_before_the_code_is_entered_stops_the_sign_up(reg):
    places(); assert reg.start(who="parent", level="school", email="mum@home.in", children=[KID]).status_code == 200
    with Session_() as s: s.add(User(name="Other", username="kavin.r", pw=main.hp("x" * 8), role="student")); s.commit()
    r = finish(reg, "mum@home.in"); assert r.status_code == 400 and "taken" in r.json()["detail"]
    with Session_() as s: assert s.query(User).filter_by(email="mum@home.in").first() is None and s.query(GuardianLink).count() == 0

def test_a_teacher_signs_up_as_a_guardian_and_admins_keep_the_role(reg):
    places(); assert reg.start(who="teacher", level="school", email="t@school.in", id_number="").status_code == 200
    me = finish(reg, "t@school.in").json()["user"]; assert (me["role"], me["relation"]) == ("guardian", "teacher")
    with Session_() as s: tid = s.query(User).filter_by(email="t@school.in").one().id
    assert reg.c.patch(f"/api/admin/users/{tid}", headers=reg.admin, json={"name": "T. Rani", "role": "guardian"}).status_code == 200
    with Session_() as s: assert s.get(User, tid).role == "guardian"

def test_an_older_app_still_signs_up_a_student_without_the_new_fields(reg):
    assert reg.start().status_code == 200; u = finish(reg, "asha@college.edu").json()["user"]
    assert (u["role"], u["level"], u["placed"]) == ("student", None, False)
