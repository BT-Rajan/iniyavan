# Pro for many people at once from a CSV, each until their own last day (or "end" to stop it): checked first, saved only when asked, same rules as one person.
import datetime as dt
import main
from main import Session_, User, Program, Semester, MoreRequest, hp

def people():
    with Session_() as s:
        col = Program(name="B.E.", pattern="semester"); sch = Program(name="State Board", pattern="grade"); s.add_all([col, sch]); s.flush()
        s.add(Semester(name="Grade 6", program_id=sch.id, semester_no=6)); s.flush()
        now = dt.datetime.utcnow()
        s.add_all([User(name="Asha", email="asha@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1),
                   User(name="Bala", email="bala@x.com", pw=hp("pw"), role="student", self_registered=True, program_id=col.id, semester=1, pro_until=now + dt.timedelta(days=5)),
                   User(name="Kavin", username="kavin", pw=hp("pw"), role="student", program_id=sch.id, semester=6),  # a school student the admin added
                   User(name="College", email="col@x.com", pw=hp("pw"), role="student", program_id=col.id, semester=1),  # uses the college's AI: no plan
                   User(name="Off", email="off@x.com", pw=hp("pw"), role="student", self_registered=True, active=False)])
        s.commit()
        s.add(MoreRequest(user_id=s.query(User).filter_by(email="asha@x.com").one().id)); s.commit()
def until(email_or_username):
    with Session_() as s:
        u = s.query(User).filter((User.email == email_or_username) | (User.username == email_or_username)).one()
        return main.local_day(u.pro_until - dt.timedelta(seconds=1)) if u.pro_until else None

def test_a_csv_gives_each_person_their_own_last_day_after_a_preview(env):
    people(); today = main.local_day(dt.datetime.utcnow()); d1, d2 = today + dt.timedelta(days=30), today + dt.timedelta(days=90)
    csv = "Email or username,Pro until\nasha@x.com,%s\nKAVIN,%s\nbala@x.com,end\ncol@x.com,%s\noff@x.com,%s\nnobody@x.com,%s\nasha@x.com,%s\n" % (
        d1.isoformat(), d2.strftime("%d/%m/%Y"), d1, d1, d1, d2)
    r = env.c.post("/api/admin/users/pro-import", headers=env.admin, json={"csv": csv}).json()  # a preview by default: nothing changes
    assert r["dry_run"] and (r["pro"], r["ended"], r["error_count"]) == (2, 1, 4)
    assert [(x["name"], x["until"]) for x in r["rows"]] == [("Asha", d1.isoformat()), ("Kavin", d2.isoformat()), ("Bala", None)]
    assert r["rows"][2]["was"] is not None and r["rows"][0]["was"] is None
    assert [e["row"] for e in r["errors"]] == [5, 6, 7, 8] and "college's AI" in r["errors"][0]["error"] and "already in the file" in r["errors"][3]["error"]
    assert until("asha@x.com") is None and until("bala@x.com") is not None
    r = env.c.post("/api/admin/users/pro-import", headers=env.admin, json={"csv": csv, "dry_run": False}).json(); assert not r["dry_run"]
    assert (until("asha@x.com"), until("kavin"), until("bala@x.com"), until("col@x.com")) == (d1, d2, None, None)
    with Session_() as s: assert s.query(MoreRequest).filter_by(done_at=None).count() == 0  # her request for more AI is answered
    assert env.c.get("/api/me/plan", headers=env.login("asha@x.com")).json()["plan"] == "pro"

def test_bad_files_and_dates_are_refused_and_only_admins_may_upload(env):
    people(); today = main.local_day(dt.datetime.utcnow())
    assert env.c.post("/api/admin/users/pro-import", headers=env.admin, json={"csv": "name,email\nA,asha@x.com\n"}).status_code == 400
    r = env.c.post("/api/admin/users/pro-import", headers=env.admin, json={"csv": "email;until\nasha@x.com;31-02-2027\nkavin;%s\nbala@x.com;%s\n" % (
        (today - dt.timedelta(days=1)).isoformat(), (today + dt.timedelta(days=4000)).isoformat()), "dry_run": False}).json()
    assert r["pro"] == 0 and [e["error"][:12] for e in r["errors"]] == ["Write the la", "The last day", "Choose a las"]  # semicolons work too
    assert until("asha@x.com") is None
    for h in (env.fac, env.stu): assert env.c.post("/api/admin/users/pro-import", headers=h, json={"csv": "email,until\n"}).status_code == 403
