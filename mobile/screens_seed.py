"""A Zigora server for the onboarding screen tests (app/src/test/.../screens/OnboardingTest.kt), on a fresh SQLite file:
a school program with a topic, a parent with a child who has no AI key, a teacher, a student the teacher has invited, and three MCQs.
Every password is pw123456. Run from the repository root:  python mobile/screens_seed.py  (it serves on 127.0.0.1:5299)."""
import os, sys, tempfile, datetime as dt
here = os.path.dirname(os.path.abspath(__file__)); tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/screens.db", JWT_SECRET="s" * 40, PBKDF2_ITER="1000", UPLOAD_DIR=tmp,
                  SMTP_HOST="smtp.invalid", SMTP_FROM="no@invalid", APP_URL="http://127.0.0.1:5299")  # mail is "set up" so sign-up is open; nothing is sent
sys.path.insert(0, os.path.join(here, "..", "backend"))
import main, uvicorn  # noqa: E402

main.upgrade_schema()
with main.Session_() as s:
    s.merge(main.Setting(k="self_registration", v="1")); s.merge(main.Setting(k="deepseek_key", v="sk-college-key-not-for-school-children"))
    sch = main.Program(name="State Board", pattern="grade"); s.add(sch); s.flush()
    g6 = main.Semester(name="Grade 6", program_id=sch.id, semester_no=6); s.add(g6); s.flush()
    co = main.Course(name="Science", semester_id=g6.id, program_id=sch.id); s.add(co); s.flush()
    un = main.Unit(name="Water", course_id=co.id, position=1); s.add(un); s.flush()
    ts = [main.Topic(title=x, content=f"Notes on {x.lower()}.", unit_id=un.id, course_id=co.id, position=k, published=True) for k, x in enumerate(("Hard water", "Soft water"), 1)]
    s.add_all(ts); s.flush()
    pw = main.hp("pw123456")
    mum = main.User(name="Lakshmi R", email="mum@x.com", pw=pw, role="guardian", relation="parent", self_registered=True, level="school")
    kid = main.User(name="Kavin", username="kavin", pw=pw, role="student", self_registered=True, program_id=sch.id, semester=6)
    rani = main.User(name="Ms Rani", email="rani@school.in", pw=pw, role="guardian", relation="teacher", self_registered=True, level="school", institution="GHSS Madurai")
    divya = main.User(name="Divya", email="divya@x.com", pw=pw, role="student", self_registered=True, program_id=sch.id, semester=6)
    s.add_all([mum, kid, rani, divya]); s.flush()
    now = dt.datetime.utcnow()
    s.add_all([main.GuardianLink(guardian_id=mum.id, student_id=kid.id), main.GuardianLink(guardian_id=rani.id, student_id=divya.id, status="invited"),
               main.Progress(user_id=kid.id, topic_id=ts[0].id, completed_at=now, last_read=now)])
    import json  # MCQ practice: three published questions on Soft water, one with maths
    for k, (q, o, c) in enumerate((("Soft water lathers", ["easily with soap", "never", "only when boiled", "only with detergents"], 0),
                                   ("Hardness is given as ppm of", ["$NaCl$", "$CaCO_3$", "$H_2O$", "$MgSO_4$"], 1),
                                   ("Boiling removes", ["permanent hardness", "temporary hardness", "all salts", "nothing"], 1))):
        s.add(main.McqItem(topic_id=ts[1].id, course_id=co.id, text=q, options=json.dumps(o), correct=c, explanation="From the notes.", difficulty="easy",
                           keywords="water", source="admin", status="published", version=1, sig=main.q_sig(q + "|", o, c)))
    s.commit()
uvicorn.run(main.app, host="127.0.0.1", port=5299, log_level="warning")
