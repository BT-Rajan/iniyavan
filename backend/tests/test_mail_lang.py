# Emails in the reader's language (Tamil and Arabic from the app's own locale files), the Pro-ended email, welcome emails for a CSV import,
# and the admin's Lite filter matching the plan rules exactly.
import datetime as dt, json, os, re
import main
from main import Session_, User, Program, Semester, GuardianLink, MailLog, hp
from tests.test_registration import reg, GOOD  # noqa: F401  (the fixture)
from tests.test_onboarding import places, finish, KID

TA_WORDS, _ = main.mail_words("ta")
def mailbox(reg, monkeypatch):  # every email as {to, subject, body, kind, lang}; a thread's email goes out at once
    box = []; monkeypatch.setattr(main, "send_mail", lambda to, subj, body, kind="mail", link=None, lang="en": box.append(dict(to=to, subject=subj, body=body, kind=kind, lang=lang)))
    monkeypatch.setattr(main, "spawn", lambda fn, *a: fn(*a)); reg.box = box; return box
def misses(monkeypatch):  # every English wording an email asked for in Tamil or Arabic that has no translation
    found, real = [], main.mt
    def mt(lang, text, **v):
        if lang in ("ta", "ar") and not v and text not in main.mail_words(lang)[0] and not any(p.fullmatch(text) for p, _ in main.mail_words(lang)[1]): found.append(text)
        elif lang in ("ta", "ar") and v and text not in main.mail_words(lang)[0]: found.append(text)
        return real(lang, text, **v)
    monkeypatch.setattr(main, "mt", mt); return found
def lang_of(email, lang):
    with Session_() as s: s.query(User).filter_by(email=email).update({"lang": lang}); s.commit()
def last(box, who): return [m for m in box if m["to"] == who][-1]

def test_every_email_reaches_tamil_and_arabic_readers_in_their_language(reg, monkeypatch):
    box = mailbox(reg, monkeypatch); missing = misses(monkeypatch); sch, _ = places()
    # sign-up in Tamil: the code, then the welcome with the children's usernames; the screen's language becomes the account's
    assert reg.start(who="parent", level="school", institution="", id_number="", email="amma@home.in", children=[dict(KID, program_id=sch, semester=6)], lang="ta").status_code == 200
    m = last(box, "amma@home.in"); assert m["lang"] == "ta" and "சரிபார்ப்புக் குறியீடு" in m["subject"] and m["body"].startswith("வணக்கம்")
    code = re.search(r"\b(\d{6})\b", m["body"]).group(1)
    tok = reg.c.post("/api/register/verify", json={"email": "amma@home.in", "code": code, "lang": "ta"}).json()["token"]; h = {"Authorization": "Bearer " + tok}
    assert reg.c.get("/api/me", headers=h).json()["lang"] == "ta" and "kavin.r" in last(box, "amma@home.in")["body"] and "வரவேற்கிறோம்" in last(box, "amma@home.in")["subject"]
    reg.c.post("/api/guardian/students", headers=h, json={"students": [dict(name="Meera", username="meera", password="kidpass456")]})
    assert "meera" in last(box, "amma@home.in")["body"] and "1 கணக்கை" in last(box, "amma@home.in")["body"]
    reg.start(email="amma@home.in", lang="ar"); assert last(box, "amma@home.in")["lang"] == "ar"  # an account that exists: told in the screen's language
    # the student's own account in Arabic: password, reset, status, role, invitation, Pro
    lang_of("stu@x.com", "ar"); uid = Session_().query(User).filter_by(email="stu@x.com").one().id
    reg.c.post("/api/me/password", headers=reg.stu, json={"current": "pw", "new_password": "newpass123"}); m = last(box, "stu@x.com")
    assert m["lang"] == "ar" and "تم تغيير كلمة مرور" in m["subject"] and "Forgot your password?" in m["body"]
    reg.c.post("/api/forgot", json={"email": "stu@x.com"}); assert "أعد تعيين" in last(box, "stu@x.com")["subject"] and "#reset=" in last(box, "stu@x.com")["body"]
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"active": False}); assert "إيقاف" in last(box, "stu@x.com")["subject"]
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"active": True}); assert "تفعيل" in last(box, "stu@x.com")["subject"]
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"role": "faculty"}); assert "عضوَ هيئة تدريس" in last(box, "stu@x.com")["body"]
    reg.c.patch(f"/api/admin/users/{uid}", headers=reg.admin, json={"role": "student"})
    with Session_() as s: s.add(User(name="Ms Rani", email="rani@x.com", pw=hp("pw"), role="guardian", relation="teacher", self_registered=True, level="school", lang="ta")); s.commit()
    rani = reg.login("rani@x.com"); reg.c.post("/api/guardian/invite", headers=rani, json={"login": "stu@x.com"}); assert "دعاك Ms Rani" in last(box, "stu@x.com")["subject"]
    stu = reg.login("stu@x.com", "newpass123")  # the password changed above, which ends old sign-ins
    lid = reg.c.get("/api/me/invitations", headers=stu).json()["invitations"][0]["id"]; reg.c.post(f"/api/me/invitations/{lid}/decline", headers=stu)
    assert last(box, "rani@x.com")["lang"] == "ta" and "மறுத்தார்" in last(box, "rani@x.com")["subject"]
    with Session_() as s: s.query(User).filter_by(id=uid).update({"self_registered": True}); s.commit()
    reg.c.put(f"/api/admin/users/{uid}/pro", headers=reg.admin, json={"days": 7}); m = last(box, "stu@x.com"); assert m["kind"] == "pro" and "حتى" in m["body"] and re.search(r"\d+/\d+/\d{4}", m["body"])
    reg.c.put(f"/api/admin/users/{uid}/pro", headers=reg.admin, json={"end": True}); assert last(box, "stu@x.com")["kind"] == "pro_end" and "أنهى المشرف" in last(box, "stu@x.com")["body"]
    # an admin in Tamil: the test email, and accounts the admin makes
    lang_of("admin@x.com", "ta"); monkeypatch.setattr(main, "mail_conf", lambda s: {"via": "server"})
    reg.c.post("/api/admin/mail/test", headers=reg.admin); assert last(box, "admin@x.com")["lang"] == "ta" and "சோதனை" in last(box, "admin@x.com")["subject"]
    assert missing == [], missing  # every wording asked for along the way has both translations
    assert all(m["lang"] == "en" for m in box if m["to"] in ("fac@x.com",))  # English stays English

def test_every_wording_in_the_code_has_both_translations():
    src = open(os.path.join(os.path.dirname(main.__file__), "main.py"), encoding="utf-8").read()
    keys = {json.loads('"' + k + '"') for k in re.findall(r'mt\((?:lang|l), "((?:[^"\\]|\\.)*)"', src)}
    keys |= set(main.ROLE_NOTE.values()) | set(main.NEW_ACCOUNT.values()) | {x for pair in main.LITE_WARN.values() for x in pair} | {main.PRO_AFTER}
    keys |= {main.lite_more(type("U", (), {"self_registered": b})).strip() for b in (True, False)}
    assert len(keys) > 30
    for lang in ("ta", "ar"):
        words = main.mail_words(lang)[0]; assert not [k for k in keys if k not in words], lang

def test_pro_that_runs_out_is_told_once_and_old_endings_are_left_alone(reg, monkeypatch):
    box = mailbox(reg, monkeypatch); monkeypatch.setattr(main, "send_mail", lambda to, subj, body, kind="mail", link=None, lang="en": (box.append(dict(to=to, subject=subj, body=body, kind=kind, lang=lang)),
                                                                                                                  _log(to, kind)))
    now = dt.datetime.utcnow()
    with Session_() as s:
        s.add_all([User(name="Ran Out", email="out@x.com", pw=hp("pw"), role="student", self_registered=True, pro_until=now - dt.timedelta(hours=3), lang="ta"),
                   User(name="Long Ago", email="old@x.com", pw=hp("pw"), role="student", self_registered=True, pro_until=now - dt.timedelta(days=5)),
                   User(name="Still Pro", email="pro@x.com", pw=hp("pw"), role="student", self_registered=True, pro_until=now + dt.timedelta(days=3))]); s.commit()
    assert main.pro_endings(now) == 1 and [m["to"] for m in box] == ["out@x.com"] and "முடிந்தது" in box[0]["subject"] and "Lite" in box[0]["body"]
    assert main.pro_endings(now + dt.timedelta(minutes=30)) == 0 and len(box) == 1  # once only
def _log(to, kind):  # what send_mail records, so the once-only check sees it
    with Session_() as s: s.add(MailLog(kind=kind, to=to, ok=True)); s.commit()

def test_people_imported_from_a_file_get_a_welcome_without_their_password(reg, monkeypatch):
    box = mailbox(reg, monkeypatch)
    csv = "name,email,password,role\nNew One,new1@x.com,secretpass1,student\nNew Two,new2@x.com,,faculty\nStu Again,stu@x.com,,student\n"
    assert reg.c.post("/api/admin/users/import", headers=reg.admin, json={"csv": csv, "dry_run": True}).status_code == 200 and box == []  # a preview sends nothing
    r = reg.c.post("/api/admin/users/import", headers=reg.admin, json={"csv": csv, "dry_run": False}).json(); assert r["created"] == 2
    got = {m["to"]: m for m in box if m["kind"] == "welcome"}; assert set(got) == {"new1@x.com", "new2@x.com"}  # not the account that was only updated
    assert "as a student" in got["new1@x.com"]["body"] and "as a faculty member" in got["new2@x.com"]["body"]
    assert not any(p in m["body"] for m in box for p in ["secretpass1"] + [c["password"] for c in r.get("credentials", [])])

def test_the_lite_filter_lists_exactly_the_people_on_lite(env):
    with Session_() as s:
        col, sch = Program(name="B.E.", pattern="semester"), Program(name="Board", pattern="grade"); s.add_all([col, sch]); s.flush()
        future = dt.datetime.utcnow() + dt.timedelta(days=5)
        people = [User(name="Lite college", email="a@x.com", role="student", self_registered=True, program_id=col.id, semester=1),
                  User(name="Lite unplaced", email="b@x.com", role="student", self_registered=True),
                  User(name="Own key", email="c@x.com", role="student", self_registered=True, ai_key=main.seal("sk-own-000000000000"), program_id=col.id),
                  User(name="Pro", email="d@x.com", role="student", self_registered=True, pro_until=future, program_id=col.id),
                  User(name="School signed up", email="e@x.com", role="student", self_registered=True, program_id=sch.id, semester=6),
                  User(name="School unplaced", email="f@x.com", role="student", self_registered=True, level="school"),
                  User(name="School added", email="g@x.com", role="student", program_id=sch.id, semester=6),
                  User(name="School added pro", email="h@x.com", role="student", program_id=sch.id, semester=6, pro_until=future),
                  User(name="College added", email="i@x.com", role="student", program_id=col.id, semester=1),
                  User(name="Parent", email="j@x.com", role="guardian", relation="parent", self_registered=True, level="school"),
                  User(name="Teacher", email="k@x.com", role="guardian", relation="teacher", self_registered=True, level="college")]
        for u in people: u.pw = hp("pw")
        s.add_all(people); s.commit()
        want = {u.name for u in s.query(User) if main.ai_plan(u) == "lite"}
    got = {x["name"] for x in env.c.get("/api/admin/users?plan=lite&limit=100", headers=env.admin).json()["items"]}
    assert got == want == {"Lite college", "Lite unplaced", "School added"}
    assert {x["name"] for x in env.c.get("/api/admin/users?plan=pro&limit=100", headers=env.admin).json()["items"]} == {"Pro", "School added pro"}
