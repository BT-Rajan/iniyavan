# A school student the admin added: the school's key within the Lite allowance. And the account emails: sign-up, password changes,
# switched on or off, role changes, a teacher's invitation and its answer, and a Lite allowance nearly used up. Never a password in them.
import main
from main import Session_, Setting, User, GuardianLink, Program, Semester, hp
from tests.test_registration import reg, GOOD  # noqa: F401  (the fixture)
from tests.test_onboarding import places, finish, KID
from tests.test_search import ai_env, ask

def inline(monkeypatch): monkeypatch.setattr(main, "spawn", lambda fn, *a: fn(*a))  # mail sent from a thread goes out at once in a test
def to(reg, who): return [(subj, body) for t, subj, body in reg.sent if t == who]
def school_pupil(env, email="pupil@school.in"):  # added by the admin, placed in a school program
    with Session_() as s:
        sch = Program(name="State Board", pattern="grade"); s.add(sch); s.flush(); s.add(Semester(name="Grade 6", program_id=sch.id, semester_no=6))
        s.add(User(name="Pupil", email=email, pw=hp("pw1234567"), role="student", program_id=sch.id, semester=6)); s.commit()
        uid = s.query(User).filter_by(email=email).one().id
    return env.login(email, "pw1234567"), uid
def limits(searches, minutes):
    with Session_() as s: s.merge(Setting(k="lite_searches", v=str(searches))); s.merge(Setting(k="lite_minutes", v=str(minutes))); s.commit()

def test_a_school_student_the_admin_added_gets_the_lite_allowance_and_can_be_made_pro(env, monkeypatch):
    ai_env(env, monkeypatch); h, uid = school_pupil(env); limits(1, 20)
    p = env.c.get("/api/me/plan", headers=h).json(); assert (p["plan"], p["own_key"], p["searches_limit"]) == ("lite", False, 1)
    assert env.c.get("/api/ai/status", headers=h).json()["vision"] is False  # diagrams in photos are not part of Lite
    assert ask(env, "first question", h=h).status_code == 200  # on the school's key
    r = ask(env, "second question", h=h); assert r.status_code == 429 and "ask your admin for more" in r.json()["detail"] and "DeepSeek" not in r.json()["detail"]
    assert env.c.put("/api/me/ai-key", headers=h, json={"key": "sk-" + "x" * 30}).status_code == 403  # no key of their own
    assert uid in [x["id"] for x in env.c.get("/api/admin/users?plan=lite", headers=env.admin).json()["items"]]
    assert env.c.put(f"/api/admin/users/{uid}/pro", headers=env.admin, json={"days": 7}).json()["plan"] == "pro"
    assert ask(env, "second question", h=h).status_code == 200 and uid in [x["id"] for x in env.c.get("/api/admin/users?plan=pro", headers=env.admin).json()["items"]]
    assert env.c.get("/api/me/plan", headers=env.stu).json()["plan"] == "college"  # a college student the admin added: as before

def test_sign_up_and_a_parents_new_children_are_confirmed_by_email(reg):
    sch, _ = places(); kids = [dict(KID, program_id=sch, semester=6)]
    assert reg.start(who="parent", level="school", institution="", id_number="", email="mum@home.in", children=kids).status_code == 200
    tok = finish(reg, "mum@home.in").json()["token"]
    subj, body = to(reg, "mum@home.in")[-1]; assert subj.startswith("Welcome") and "kavin.r" in body and KID["password"] not in body
    r = reg.c.post("/api/guardian/students", headers={"Authorization": "Bearer " + tok}, json={"students": [dict(name="Meera", username="meera", password="kidpass456")]})
    assert r.status_code == 200; subj, body = to(reg, "mum@home.in")[-1]; assert "meera" in body and "kidpass456" not in body

def test_password_changes_are_told_without_the_password(reg, monkeypatch):
    inline(monkeypatch)
    assert reg.c.post("/api/me/password", headers=reg.stu, json={"current": "pw", "new_password": "newpass123"}).status_code == 200
    subj, body = to(reg, "stu@x.com")[-1]; assert "password was changed" in subj and "Forgot your password?" in body and "newpass123" not in body
    with Session_() as s: uid = s.query(User).filter_by(email="stu@x.com").one().id
    pw = reg.c.post(f"/api/admin/users/{uid}/reset-password", headers=reg.admin).json()["password"]
    subj, body = to(reg, "stu@x.com")[-1]; assert "admin set a new password" in body and pw not in body
    n = len(to(reg, "stu@x.com")); reg.c.post("/api/admin/users/bulk", headers=reg.admin, json={"ids": [uid], "action": "reset_passwords"})
    assert len(to(reg, "stu@x.com")) == n + 1

def test_a_childs_new_password_is_told_to_their_other_parent_or_teacher_not_the_one_who_set_it(reg):
    with Session_() as s:
        kid = User(name="Kavin", username="kavin", pw=hp("pw"), role="student", self_registered=True, level="school")
        mum = User(name="Mum", email="mum@x.com", pw=hp("pw"), role="guardian", relation="parent", self_registered=True, level="school")
        tch = User(name="Rani", email="rani@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="school")
        s.add_all([kid, mum, tch]); s.flush(); s.add_all([GuardianLink(guardian_id=mum.id, student_id=kid.id), GuardianLink(guardian_id=tch.id, student_id=kid.id)]); s.commit(); kid_id = kid.id
    assert reg.c.put(f"/api/guardian/students/{kid_id}/password", headers=reg.login("mum@x.com"), json={"password": "newkidpw1"}).status_code == 200
    assert to(reg, "mum@x.com") == [] and "Kavin" in to(reg, "rani@x.com")[-1][1] and "newkidpw1" not in str(reg.sent)

def test_switching_an_account_off_or_on_and_a_new_role_are_told(reg):
    with Session_() as s: uid = s.query(User).filter_by(email="stu@x.com").one().id
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"active": False}); assert "switched off" in to(reg, "stu@x.com")[-1][0]
    reg.c.post("/api/admin/users/bulk", headers=reg.admin, json={"ids": [uid], "action": "enable"}); assert "switched on" in to(reg, "stu@x.com")[-1][0]
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"role": "faculty"}); assert "a faculty member" in to(reg, "stu@x.com")[-1][1]
    n = len(reg.sent); reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"name": "New Name"}); assert len(reg.sent) == n  # a new name alone: no email
    reg.c.post("/api/admin/users", headers=reg.admin, json={"name": "Newbie", "email": "new@x.com", "password": "longenough1", "role": "student"})
    assert "made a" in to(reg, "new@x.com")[-1][1] and "longenough1" not in to(reg, "new@x.com")[-1][1]

def test_a_teachers_invitation_and_the_answer_go_by_email(reg):
    with Session_() as s: s.add(User(name="Ms Rani", email="rani@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="school", institution="GHSS")); s.commit()
    t = reg.login("rani@x.com"); reg.c.post("/api/guardian/invite", headers=t, json={"login": "stu@x.com"})
    subj, body = to(reg, "stu@x.com")[-1]; assert "Ms Rani" in subj and "GHSS" in body
    n = len(reg.sent); reg.c.post("/api/guardian/invite", headers=t, json={"login": "nobody@x.com"}); assert len(reg.sent) == n  # no account, no email
    lid = reg.c.get("/api/me/invitations", headers=reg.stu).json()["invitations"][0]["id"]
    reg.c.post(f"/api/me/invitations/{lid}/accept", headers=reg.stu); assert "accepted" in to(reg, "rani@x.com")[-1][0]

def test_a_lite_allowance_nearly_used_up_is_told_once(reg, monkeypatch):
    ai_env(reg, monkeypatch); inline(monkeypatch); h, uid = school_pupil(reg); limits(5, 20)
    for q in ("one", "two", "three"): assert ask(reg, q, h=h).status_code == 200
    assert to(reg, "pupil@school.in") == []
    assert ask(reg, "four", h=h).status_code == 200; subj, body = to(reg, "pupil@school.in")[-1]  # 4 of 5
    assert "AI searches are nearly used up" in subj and "4 of today's 5" in body
    assert ask(reg, "five", h=h).status_code == 200 and len(to(reg, "pupil@school.in")) == 1

def test_a_child_with_no_email_sees_their_username_and_family_plan_on_their_profile(env):
    with Session_() as s: s.add(User(name="Kavin", username="kavin", pw=hp("pw"), role="student", self_registered=True, level="school")); s.commit()
    p = env.c.get("/api/me/profile", headers=env.login("kavin")).json()
    assert (p["email"], p["username"], p["ai"]["plan"], p["ai"]["own_key"]) == (None, "kavin", "off", False)
