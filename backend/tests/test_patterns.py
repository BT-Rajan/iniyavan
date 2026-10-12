import pytest, main
from main import Session_, Semester, Program

def terms(env, pid): return [(x["number"], x["name"]) for x in env.c.get(f"/api/admin/programs/{pid}", headers=env.admin).json()["semester_list"]]
def make(env, **b): return env.c.post("/api/programs", headers=env.admin, json=b)

def test_a_new_program_gets_its_terms_straight_away_by_pattern(env):
    a = make(env, name="B.E. Mech").json(); assert a["pattern"] == "semester" and a["terms"] == 8
    assert terms(env, a["id"]) == [(i, f"Semester {i}") for i in range(1, 9)]
    m = make(env, name="M.B.B.S", pattern="year", terms=5).json(); assert terms(env, m["id"]) == [(i, f"Year {i}") for i in range(1, 6)]
    assert len(terms(env, make(env, name="B.Sc", pattern="year").json()["id"])) == 4  # a year program starts with four by default
    assert terms(env, make(env, name="Empty", terms=0).json()["id"]) == []
    for bad in ({"pattern": "quarter"}, {"terms": 9}, {"terms": -1}): assert make(env, name="X" + str(bad), **bad).status_code == 400
    assert main.term_label(Program(pattern=None)) == "Semester"
    for h in (env.fac, env.stu): assert env.c.post("/api/programs", headers=h, json={"name": "Z"}).status_code == 403

def test_pattern_shows_in_the_program_list_detail_and_tree(env):
    m = make(env, name="M.B.B.S", pattern="year", terms=2).json()["id"]; make(env, name="B.E.")
    items = {p["name"]: p for p in env.c.get("/api/admin/programs", headers=env.admin).json()["items"]}
    assert (items["M.B.B.S"]["pattern"], items["M.B.B.S"]["term"], items["B.E."]["term"]) == ("year", "Year", "Semester")
    d = env.c.get(f"/api/admin/programs/{m}", headers=env.admin).json(); assert d["pattern"] == "year" and d["term"] == "Year"
    t = {p["name"]: p for p in env.c.get("/api/tree", headers=env.admin).json()}; assert t["M.B.B.S"]["term"] == "Year" and t["B.E."]["pattern"] == "semester"

def test_changing_the_pattern_renames_standard_terms_only(env):
    p = make(env, name="Prog", terms=3).json()["id"]
    first = env.c.get(f"/api/admin/programs/{p}", headers=env.admin).json()["semester_list"][0]["id"]
    env.c.put(f"/api/semesters/{first}", headers=env.admin, json={"name": "Foundation term", "program_id": p})
    assert env.c.put(f"/api/programs/{p}", headers=env.admin, json={"name": "Prog", "pattern": "year"}).status_code == 200
    assert terms(env, p) == [(1, "Foundation term"), (2, "Year 2"), (3, "Year 3")]
    assert env.c.put(f"/api/programs/{p}", headers=env.admin, json={"name": "Prog 2"}).status_code == 200  # a rename alone keeps the pattern
    assert env.c.get(f"/api/admin/programs/{p}", headers=env.admin).json()["pattern"] == "year"
    assert env.c.put(f"/api/programs/{p}", headers=env.admin, json={"name": "Prog 2", "pattern": "x"}).status_code == 400

def test_messages_use_the_programs_word_and_years_are_accepted_as_numbers(env):
    p = make(env, name="M.B.B.S", pattern="year", terms=1).json()["id"]
    r = env.c.post(f"/api/programs/{p}/semesters", headers=env.admin, json={"name": "Year 1 again", "semester_no": 1}); assert r.status_code == 400 and "year 1" in r.json()["detail"]
    assert env.c.post(f"/api/programs/{p}/semesters", headers=env.admin, json={"name": "Year 9", "semester_no": 9}).json()["detail"].startswith("The year number")
    assert [main.to_sem(v) for v in ("Year 3", "y2", "yr 5", "S4", "6", "")] == [3, 2, 5, 4, 6, None]

def test_csv_import_makes_a_year_program_when_the_terms_are_called_years(env):
    env.csv("program,semester,course,unit,topic,content\nM.B.B.S,Year 1,Anatomy,U1,Bones,b\nB.E.,Semester 1,Chem,U1,Water,w\n")
    with Session_() as s: got = {p.name: p.pattern for p in s.query(Program)}; n = {x.name: x.semester_no for x in s.query(Semester)}
    assert got["M.B.B.S"] == "year" and got["B.E."] == "semester" and n["Year 1"] == 1

def test_rollover_reports_the_word_for_the_program(env):
    p = make(env, name="M.B.B.S", pattern="year", terms=3).json()["id"]
    r = env.c.post(f"/api/admin/programs/{p}/rollover", headers=env.admin, json={"dry_run": True, "finishing": "keep"}); assert r.status_code == 200 and r.json()["term"] == "Year" and r.json()["last_semester"] == 3

def test_old_programs_become_semester_programs_on_upgrade(tmp_path):
    from sqlalchemy import create_engine, text
    e = create_engine(f"sqlite:///{tmp_path}/o.db")
    with e.begin() as c: c.execute(text("CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT)")); c.execute(text("INSERT INTO courses (id, name) VALUES (1, 'Mech')"))
    old = main.engine; main.engine = e
    try:
        main.upgrade_schema()
        with e.connect() as c: assert c.execute(text("SELECT pattern FROM courses WHERE id = 1")).scalar() == "semester"
    finally: main.engine = old

def test_a_school_program_runs_grade_1_to_12(env):
    g = make(env, name="School", pattern="grade").json(); assert g["pattern"] == "grade" and g["terms"] == 12
    assert terms(env, g["id"]) == [(i, f"Grade {i}") for i in range(1, 13)]
    assert make(env, name="School 2", pattern="grade", terms=13).status_code == 400
    assert make(env, name="B.E. 2", terms=12).status_code == 400  # semesters still stop at 8
    assert env.c.get(f"/api/admin/programs/{g['id']}", headers=env.admin).json()["term"] == "Grade"
    assert [main.to_sem(v) for v in ("Grade 12", "g10", "11", "std 9")] == [12, 10, 11, 9]
    assert env.c.put(f"/api/programs/{g['id']}", headers=env.admin, json={"name": "School", "pattern": "semester"}).status_code == 400  # grades 9 to 12 do not fit
    r = env.c.post(f"/api/admin/programs/{g['id']}/rollover", headers=env.admin, json={"dry_run": True, "finishing": "keep"}); assert r.json()["term"] == "Grade" and r.json()["last_semester"] == 12

def test_csv_import_makes_a_grade_program_and_reads_grade_numbers(env):
    env.csv("program,semester,course,unit,topic,content\nSchool,Grade 10,Maths,U1,Algebra,a\nSchool,Grade XII,Physics,U1,Motion,m\n")
    with Session_() as s: got = {p.name: p.pattern for p in s.query(Program)}; n = {x.name: x.semester_no for x in s.query(Semester)}
    assert got["School"] == "grade" and n["Grade 10"] == 10 and n["Grade XII"] == 12

def test_a_students_number_must_exist_in_their_program(env):
    be = make(env, name="B.E. X").json()["id"]; sch = make(env, name="School X", pattern="grade").json()["id"]
    add = lambda e, p, n: env.c.post("/api/admin/users", headers=env.admin, json={"name": "S", "email": e, "password": "password1", "program_id": p, "semester": n})
    r = add("a@x.com", be, 12); assert r.status_code == 400 and "semester 8" in r.json()["detail"]
    assert add("b@x.com", sch, 12).status_code == 200
    uid = next(u["id"] for u in env.c.get("/api/admin/users?q=b@x.com", headers=env.admin).json()["items"])
    assert env.c.patch(f"/api/admin/users/{uid}", headers=env.admin, json={"program_id": be}).status_code == 400  # grade 12 does not fit a semester program
    assert env.c.patch(f"/api/admin/users/{uid}", headers=env.admin, json={"program_id": be, "semester": 3}).status_code == 200
    assert env.c.post("/api/admin/users/bulk", headers=env.admin, json={"ids": [uid], "action": "set_placement", "program_id": be, "semester": 9}).status_code == 400
    r = env.c.post("/api/admin/users/import", headers=env.admin, json={"csv": "name,email,program,semester\nC,c@x.com,B.E. X,10\nD,d@x.com,School X,10\n", "dry_run": True}).json()
    assert r["created"] == 1 and r["errors"][0]["row"] == 2

def test_switching_a_program_to_grades_fills_in_grade_1_to_12(env):
    p = make(env, name="School Y", pattern="year", terms=8).json()["id"]
    assert env.c.put(f"/api/programs/{p}", headers=env.admin, json={"name": "School Y", "pattern": "grade"}).status_code == 200
    assert terms(env, p) == [(i, f"Grade {i}") for i in range(1, 13)]
    e = make(env, name="Empty Y", pattern="year", terms=0).json()["id"]  # a program the admin is setting up by hand is left empty
    env.c.put(f"/api/programs/{e}", headers=env.admin, json={"name": "Empty Y", "pattern": "grade"}); assert terms(env, e) == []
