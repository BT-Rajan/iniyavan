"""Topic learning deadlines and each student's learning state (not started, in progress, completed; overdue is worked out)."""
import datetime as dt
import sqlalchemy as sa
import main
from main import Session_, User, Topic, Progress
from tests.test_access import CSV, ids, enrol

def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def setup(env):
    """fac owns Chem, fac2 owns Workshop; stu is in Mech semester 1 (Chem and Workshop); civ is in Civil semester 1."""
    env.csv(CSV); i = ids(); env.add_user("fac2@x.com", "faculty"); env.fac2 = env.login("fac2@x.com")
    env.add_user("civ@x.com", program=i["prog"]["Civil"], semester=1); env.civ = env.login("civ@x.com")
    for cid, who in ((i["course"]["Chem"], "fac@x.com"), (i["course"]["Workshop"], "fac2@x.com")):
        env.c.put(f"/api/courses/{cid}/owner", headers=env.admin, json={"user_id": uid(who)})
    enrol("stu@x.com", i["prog"]["Mech"], 1); i["water"] = i["topic"]["Water"]; i["cu"] = i["unit"][i["course"]["Chem"]]
    return i
def due(env, h, i, tid, value, **extra):  # the deadline is saved with the topic, like its content
    body = {"title": "Water", "unit_id": i["cu"], **extra}
    if value != "omit": body["learning_due_at"] = value
    return env.c.put(f"/api/topics/{tid}", headers=h, json=body)
def stored(tid):
    with Session_() as s: return s.get(Topic, tid).learning_due_at
def state(env, h, tid): return {k: env.c.get(f"/api/topics/{tid}", headers=h).json()[k] for k in ("status", "learning_due_at", "completed_at", "overdue", "late")}
def rows(email, tid):
    with Session_() as s: return s.query(Progress).filter_by(user_id=uid(email), topic_id=tid).count()
FUTURE, PAST = "2099-01-15T17:00:00+05:30", "2001-03-01T09:00:00Z"

# 27: deadlines, set by the owner or an admin only
def test_owner_and_admin_set_change_and_remove_deadlines(env):
    i = setup(env); w = i["water"]
    assert stored(w) is None and state(env, env.stu, w)["learning_due_at"] is None                       # no deadline to start with
    assert due(env, env.fac, i, w, FUTURE).status_code == 200                                            # 1 set
    assert stored(w) == dt.datetime(2099, 1, 15, 11, 30) and state(env, env.stu, w)["learning_due_at"] == "2099-01-15T11:30:00Z"  # one UTC instant
    assert due(env, env.fac, i, w, "2099-02-01T00:00:00Z").status_code == 200 and stored(w) == dt.datetime(2099, 2, 1)  # 2 change
    assert due(env, env.fac, i, w, "omit", content="new notes").status_code == 200 and stored(w) == dt.datetime(2099, 2, 1)  # editing content keeps it
    assert due(env, env.fac, i, w, None).status_code == 200 and stored(w) is None                        # 3 remove
    assert due(env, env.fac2, i, w, FUTURE).status_code == 403                                            # 4 other faculty
    assert due(env, env.stu, i, w, FUTURE).status_code == 403                                             # 5 student
    assert due(env, env.admin, i, w, PAST).status_code == 200 and stored(w) == dt.datetime(2001, 3, 1, 9)  # 6 admin; a past deadline is allowed
    assert stored(w) == dt.datetime(2001, 3, 1, 9)                                                        # and nobody moves it
    new = env.c.post("/api/topics", headers=env.fac, json={"title": "Boilers", "unit_id": i["cu"], "learning_due_at": FUTURE}).json()["id"]
    assert stored(new) == dt.datetime(2099, 1, 15, 11, 30)

def test_deadline_input_is_validated(env):
    i = setup(env); w = i["water"]
    for bad in ("tomorrow", "Monday 5 PM", "2026-13-40T10:00:00Z"): assert due(env, env.fac, i, w, bad).status_code == 422
    assert due(env, env.fac, i, w, 12345678901234).status_code == 400  # read as a Unix time, far past the year 2100
    assert due(env, env.fac, i, w, "2026-10-05T17:00:00").status_code == 400                              # no time zone: ambiguous
    assert due(env, env.fac, i, w, "1890-01-01T00:00:00Z").status_code == 400
    assert stored(w) is None

def test_faculty_can_only_set_deadlines_in_their_own_course(env):  # 29 (faculty part)
    i = setup(env); tools = i["topic"]["Tools"]; wu = i["unit"][i["course"]["Workshop"]]
    assert due(env, env.fac, i, i["water"], FUTURE).status_code == 200
    assert env.c.put(f"/api/topics/{tools}", headers=env.fac, json={"title": "Tools", "unit_id": wu, "learning_due_at": FUTURE}).status_code == 403
    assert env.c.post("/api/topics", headers=env.fac, json={"title": "x", "unit_id": wu, "learning_due_at": FUTURE}).status_code == 403
    assert stored(tools) is None

# 28: learning state
def test_open_then_complete_then_reopen(env):
    i = setup(env); w = i["water"]
    assert state(env, env.stu, w)["status"] == "not_started" and rows("stu@x.com", w) == 0
    r = env.c.post(f"/api/topics/{w}/read", headers=env.stu); assert r.status_code == 200 and r.json()["status"] == "in_progress"  # 1-2
    env.c.post(f"/api/topics/{w}/read", headers=env.stu); assert rows("stu@x.com", w) == 1                                      # visits don't add rows
    before = dt.datetime.utcnow().replace(microsecond=0)
    r = env.c.put(f"/api/topics/{w}/complete", headers=env.stu); assert r.status_code == 200 and r.json()["status"] == "completed"  # 3-4
    with Session_() as s: done_at = s.query(Progress).filter_by(user_id=uid("stu@x.com"), topic_id=w).one().completed_at
    assert done_at is not None and done_at >= before                                                     # 5
    for _ in range(3): env.c.post(f"/api/topics/{w}/read", headers=env.stu)                               # 6 reopening keeps it completed
    assert state(env, env.stu, w)["status"] == "completed"
    for _ in range(3): assert env.c.put(f"/api/topics/{w}/complete", headers=env.stu).status_code == 200  # 7 repeated clicks
    with Session_() as s: p = s.query(Progress).filter_by(user_id=uid("stu@x.com"), topic_id=w).all()
    assert len(p) == 1 and p[0].completed_at == done_at                                                  # first completion time is kept
    assert env.c.delete(f"/api/topics/{w}/complete", headers=env.stu).json()["status"] == "in_progress"  # only an explicit undo reopens it
    assert env.c.put(f"/api/topics/{w}/complete", headers=env.stu).json()["status"] == "completed" and rows("stu@x.com", w) == 1

def test_complete_without_opening_first_and_a_racing_insert_make_one_row(env):
    i = setup(env); w = i["water"]
    assert env.c.put(f"/api/topics/{w}/complete", headers=env.stu).json()["status"] == "completed" and rows("stu@x.com", w) == 1
    tools = i["topic"]["Tools"]; me = uid("stu@x.com")
    class Racing:  # the first lookup misses, as if another request inserted the row just after this one looked
        def __init__(self, s): self.s, self.missed = s, False
        def query(self, m):
            if not self.missed:
                self.missed = True
                with Session_() as other: other.add(Progress(user_id=me, topic_id=tools)); other.commit()
                return self.s.query(m).filter(sa.false())
            return self.s.query(m)
        def __getattr__(self, k): return getattr(self.s, k)
    with Session_() as s: p = main.progress_row(Racing(s), me, tools)
    assert p.topic_id == tools and rows("stu@x.com", tools) == 1                                         # the unique key held, no 500

# 29: who may have progress where
def test_progress_only_for_topics_the_student_may_see(env):
    i = setup(env); w, limits = i["water"], i["topic"]["Limits"]
    for call in ("read", "complete"):
        method = env.c.post if call == "read" else env.c.put
        assert method(f"/api/topics/{w}/{call}", headers=env.stu).status_code == 200                      # own program
        assert method(f"/api/topics/{limits}/{call}", headers=env.stu).status_code == 403                 # another program
    enrol("stu@x.com", None, None)
    assert env.c.put(f"/api/topics/{w}/complete", headers=env.stu).status_code == 403                     # no program
    assert env.c.post(f"/api/topics/{i['topic']['Tools']}/read", headers=env.stu).status_code == 403
    assert env.c.delete(f"/api/topics/{w}/complete", headers=env.stu).status_code == 403
    d = env.c.post("/api/topics", headers=env.fac, json={"title": "Draft", "unit_id": i["cu"], "published": False}).json()["id"]
    enrol("stu@x.com", i["prog"]["Mech"], 1)
    assert env.c.put(f"/api/topics/{d}/complete", headers=env.stu).status_code == 404                     # drafts stay hidden
    assert rows("stu@x.com", limits) == 0 and rows("stu@x.com", d) == 0

# 30: overdue is worked out, never stored
def test_overdue_is_derived_and_the_deadline_never_changes(env):
    i = setup(env); w = i["water"]
    due(env, env.fac, i, w, FUTURE); assert state(env, env.stu, w)["overdue"] is False
    due(env, env.fac, i, w, PAST); env.c.post(f"/api/topics/{w}/read", headers=env.stu)
    s1 = state(env, env.stu, w); assert (s1["status"], s1["overdue"]) == ("in_progress", True)
    assert env.c.get(f"/api/topics/{w}", headers=env.stu).status_code == 200  # an overdue topic stays open to read
    s2 = env.c.put(f"/api/topics/{w}/complete", headers=env.stu).json()
    assert (s2["status"], s2["overdue"], s2["late"]) == ("completed", False, True)
    assert stored(w) == dt.datetime(2001, 3, 1, 9)
    due(env, env.fac, i, w, FUTURE); assert state(env, env.stu, w)["late"] is False                     # on time against the new deadline
    tree = {t["title"]: t for p in env.c.get("/api/tree", headers=env.stu).json() for sm in p["semesters"] for c in sm["courses"] for n in c["units"] for t in n["topics"]}
    assert (tree["Water"]["status"], tree["Tools"]["status"], tree["Tools"]["overdue"]) == ("completed", "not_started", False)

# 31: course and unit progress are counted from progress rows
def test_course_progress_is_counted_from_completions(env):
    i = setup(env); topics = [i["water"]] + [env.c.post("/api/topics", headers=env.fac, json={"title": f"T{k}", "unit_id": i["cu"]}).json()["id"] for k in range(4)]
    def mine():
        cs = {c["name"]: c for p in env.c.get("/api/tree", headers=env.stu).json() for sm in p["semesters"] for c in sm["courses"]}
        ts = [t for n in cs["Chem"]["units"] for t in n["topics"]]
        return sum(t["status"] == "completed" for t in ts), len(ts)
    for t in topics[:2]: env.c.put(f"/api/topics/{t}/complete", headers=env.stu)
    assert mine() == (2, 5)
    env.c.put(f"/api/topics/{topics[2]}/complete", headers=env.stu); assert mine() == (3, 5)
    env.c.post(f"/api/topics/{topics[3]}/read", headers=env.stu); assert mine() == (3, 5)                # opened is not completed
    due(env, env.fac, i, topics[4], PAST, title="T3")
    env.add_user("stu2@x.com", program=i["prog"]["Mech"], semester=1)
    r = env.c.get(f"/api/courses/{i['course']['Chem']}/progress", headers=env.fac).json()
    assert r["students"] == 2 and r["topics"][str(topics[0])] == {"completed": 1, "overdue": 0} and r["topics"][str(topics[4])] == {"completed": 0, "overdue": 2}
    assert env.c.get(f"/api/courses/{i['course']['Chem']}/progress", headers=env.fac2).status_code == 403
    assert env.c.get(f"/api/courses/{i['course']['Chem']}/progress", headers=env.stu).status_code == 403
    assert env.c.get(f"/api/courses/{i['course']['Chem']}/progress", headers=env.admin).status_code == 200

# J: migration 0012 adds the columns and invents nothing
def test_migration_adds_no_deadlines_or_completions(env):
    i = setup(env); env.c.post(f"/api/topics/{i['water']}/read", headers=env.stu)
    with main.engine.begin() as c: main.learning_state_columns(c)
    with Session_() as s:
        assert all(t.learning_due_at is None for t in s.query(Topic)) and all(p.completed_at is None for p in s.query(Progress))
    assert state(env, env.stu, i["water"])["status"] == "in_progress" and "0012_learning_deadlines" in main.applied_migrations()
