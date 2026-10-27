"""Phase 1 of the school/college onboarding: school or college, parents and teachers (role "guardian") linked to students, and children who sign in with a username."""
import main
from main import Session_, User, GuardianLink, Program, hp
from tests.test_access import enrol, ids, CSV

def guardian(email, relation="parent"):
    with Session_() as s:
        g = User(name="Parent", email=email, pw=hp("pw"), role="guardian", relation=relation, self_registered=True, level="school"); s.add(g); s.commit(); return g.id
def child(username, program=None, semester=None):
    with Session_() as s:
        c = User(name="Kid", email=None, username=username, pw=hp("pw"), role="student", self_registered=True, program_id=program, semester=semester); s.add(c); s.commit(); return c.id
def link(gid, sid, status="active"):
    with Session_() as s: s.add(GuardianLink(guardian_id=gid, student_id=sid, status=status)); s.commit()

def test_level_comes_from_the_program_or_the_sign_up_choice(env):
    env.csv(CSV); i = ids()
    with Session_() as s:
        school = Program(name="State Board", pattern="grade"); s.add(school); s.commit()
        assert main.program_level(school) == "school" and main.program_level(s.get(Program, i["prog"]["Mech"])) == "college"
    enrol("stu@x.com", i["prog"]["Mech"], 1); assert env.c.get("/api/me", headers=env.stu).json()["level"] == "college"
    with Session_() as s:
        u = s.query(User).filter_by(email="stu@x.com").one(); u.program_id = None; u.level = "school"; s.commit()
        assert main.stage_of(u) == "school"  # not placed yet: what they chose at sign-up
    assert env.c.get("/api/me", headers=env.admin).json()["level"] is None  # staff have no level

def test_a_child_signs_in_with_a_username(env):
    child("asha.k"); r = env.c.post("/api/login", json={"email": "Asha.K", "password": "pw"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "asha.k"
    assert env.c.post("/api/login", json={"email": "asha.k", "password": "nope"}).status_code == 401
    assert env.c.post("/api/login", json={"email": "nobody", "password": "pw"}).status_code == 401

def test_guardians_link_students_and_are_not_staff(env):
    env.csv(CSV); i = ids(); g = guardian("mum@x.com"); a, b = child("kid.a", i["prog"]["Mech"], 1), child("kid.b")
    link(g, a); link(g, b, "invited")
    with Session_() as s:
        assert [x.id for x in main.guardian_students(s, g)] == [a] and [x.id for x in main.guardian_students(s, g, "invited")] == [b]
        assert [x.id for x in main.guardians_of(s, a)] == [g]
    gh = env.login("mum@x.com"); me = env.c.get("/api/me", headers=gh).json()
    assert (me["role"], me["relation"], me["level"]) == ("guardian", "parent", "school")
    assert env.c.get("/api/tree", headers=gh).json() == []  # no program of their own: they see no content, unlike staff
    for path in ("/api/overview", "/api/reports/courses", "/api/admin/users"): assert env.c.get(path, headers=gh).status_code == 403
    assert env.c.delete(f"/api/admin/users/{g}", headers=env.admin).status_code == 200  # deleting a guardian removes their links
    with Session_() as s: assert s.query(GuardianLink).count() == 0 and s.get(User, a) is not None
