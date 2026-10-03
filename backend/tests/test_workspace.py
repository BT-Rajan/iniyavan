"""Faculty course workspace: the owner manages units, topics and their content inside one course, in an order they set."""
import main
from main import Session_, User, Unit, Topic, Quiz, Question, Attempt, Progress, Bookmark, AICache
from tests.test_access import CSV, ids, enrol

def uid(email):
    with Session_() as s: return s.query(User).filter_by(email=email).first().id
def setup(env):
    """fac owns Chem, fac2 owns Workshop (both Mech, Semester 1); the student is in Mech semester 1."""
    env.csv(CSV); i = ids(); env.add_user("fac2@x.com", "faculty"); env.fac2 = env.login("fac2@x.com")
    i["chem"], i["work"] = i["course"]["Chem"], i["course"]["Workshop"]; i["cu"], i["wu"] = i["unit"][i["chem"]], i["unit"][i["work"]]
    for cid, who in ((i["chem"], "fac@x.com"), (i["work"], "fac2@x.com")): env.c.put(f"/api/courses/{cid}/owner", headers=env.admin, json={"user_id": uid(who)})
    enrol("stu@x.com", i["prog"]["Mech"], 1); return i
def course_units(env, cid, h=None):
    return next([(n["name"], [t["title"] for t in n["topics"]]) for n in c["units"]] for p in env.c.get("/api/tree", headers=h or env.admin).json() for sm in p["semesters"] for c in sm["courses"] if c["id"] == cid)
def unit_ids(cid):
    with Session_() as s: return [u.id for u in s.query(Unit).filter_by(course_id=cid).order_by(*main.ORDER[Unit])]
def topic_ids(unit):
    with Session_() as s: return [t.id for t in s.query(Topic).filter_by(unit_id=unit).order_by(*main.ORDER[Topic])]
def new_unit(env, h, cid, name): return env.c.post("/api/units", headers=h, json={"name": name, "course_id": cid})
def new_topic(env, h, unit, title, **kw): return env.c.post("/api/topics", headers=h, json={"title": title, "unit_id": unit, **kw})

# 1-8 units
def test_owner_manages_units_and_others_cannot(env):
    i = setup(env)
    r = new_unit(env, env.fac, i["chem"], "U2"); assert r.status_code == 200; u2 = r.json()["id"]                                   # 1
    assert env.c.put(f"/api/units/{u2}", headers=env.fac, json={"name": "Unit 2: Boilers", "course_id": i["chem"]}).status_code == 200  # 2
    u3 = new_unit(env, env.fac, i["chem"], "U3").json()["id"]
    assert env.c.put(f"/api/courses/{i['chem']}/units/order", headers=env.fac, json={"ids": [u3, i["cu"], u2]}).status_code == 200      # 4
    assert [n for n, _ in course_units(env, i["chem"])] == ["U3", "U1", "Unit 2: Boilers"]
    assert new_unit(env, env.fac2, i["chem"], "X").status_code == 403                                                                  # 5
    assert env.c.put(f"/api/units/{u2}", headers=env.fac2, json={"name": "X", "course_id": i["chem"]}).status_code == 403              # 6
    assert env.c.delete(f"/api/units/{u2}", headers=env.fac2).status_code == 403                                                       # 7
    assert env.c.put(f"/api/courses/{i['chem']}/units/order", headers=env.fac2, json={"ids": [u2, u3, i["cu"]]}).status_code == 403
    assert env.c.delete(f"/api/units/{u3}", headers=env.fac).status_code == 200 and unit_ids(i["chem"]) == [i["cu"], u2]                # 3
    assert new_unit(env, env.fac, i["chem"], "  ").status_code == 400

def test_faculty_cannot_move_units_across_courses_but_admin_can(env):  # 8
    i = setup(env); env.c.put(f"/api/courses/{i['work']}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")})  # fac owns both now
    assert env.c.put(f"/api/units/{i['cu']}", headers=env.fac, json={"name": "U1", "course_id": i["work"]}).status_code == 403
    assert i["cu"] in unit_ids(i["chem"])
    assert env.c.put(f"/api/units/{i['cu']}", headers=env.admin, json={"name": "U1", "course_id": i["work"]}).status_code == 200
    assert unit_ids(i["work"])[-1] == i["cu"]  # lands at the end of its new course
    with Session_() as s: assert s.get(Topic, i["topic"]["Water"]).course_id == i["work"]

# 9-16 topics
def test_owner_manages_topics_and_others_cannot(env):
    i = setup(env); water = i["topic"]["Water"]
    b = new_topic(env, env.fac, i["cu"], "Boilers", published=False).json()["id"]; c = new_topic(env, env.fac, i["cu"], "Corrosion").json()["id"]  # 9
    assert topic_ids(i["cu"]) == [water, b, c]
    assert env.c.put(f"/api/topics/{b}", headers=env.fac, json={"title": "Boiler troubles", "unit_id": i["cu"], "content": "Scale and sludge"}).status_code == 200  # 10
    assert env.c.put(f"/api/units/{i['cu']}/topics/order", headers=env.fac, json={"ids": [c, water, b]}).status_code == 200           # 12
    assert course_units(env, i["chem"])[0][1] == ["Corrosion", "Water", "Boiler troubles"]
    assert env.c.put(f"/api/topics/{b}/publish", headers=env.fac, json={"published": True}).status_code == 200                        # 13
    assert env.c.put(f"/api/topics/{b}/publish", headers=env.fac, json={"published": False}).status_code == 200
    assert env.c.put(f"/api/topics/{water}", headers=env.fac2, json={"title": "x", "unit_id": i["cu"]}).status_code == 403            # 14
    assert env.c.get(f"/api/topics/{b}", headers=env.fac2).status_code == 404                                                          # 15
    assert new_topic(env, env.fac, i["wu"], "Intruder").status_code == 403                                                             # 16
    assert env.c.put(f"/api/topics/{water}", headers=env.fac, json={"title": "Water", "unit_id": i["wu"]}).status_code == 403         # can't move it into Workshop
    assert env.c.put(f"/api/units/{i['cu']}/topics/order", headers=env.fac2, json={"ids": [b, c, water]}).status_code == 403
    assert env.c.delete(f"/api/topics/{c}", headers=env.fac2).status_code == 403
    assert env.c.delete(f"/api/topics/{c}", headers=env.fac).status_code == 200 and topic_ids(i["cu"]) == [water, b]                  # 11

def test_topics_move_between_units_of_the_same_course_only(env):
    i = setup(env); u2 = new_unit(env, env.fac, i["chem"], "U2").json()["id"]; new_topic(env, env.fac, u2, "Already here")
    assert env.c.put(f"/api/topics/{i['topic']['Water']}", headers=env.fac, json={"title": "Water", "unit_id": u2}).status_code == 200
    assert course_units(env, i["chem"]) == [("U1", []), ("U2", ["Already here", "Water"])]
    env.c.put(f"/api/courses/{i['work']}/owner", headers=env.admin, json={"user_id": uid("fac@x.com")})  # owning both courses is still not enough
    assert env.c.put(f"/api/topics/{i['topic']['Water']}", headers=env.fac, json={"title": "Water", "unit_id": i["wu"]}).status_code == 403

def test_reorder_must_name_every_item_once(env):
    i = setup(env); u2 = new_unit(env, env.fac, i["chem"], "U2").json()["id"]; o = f"/api/courses/{i['chem']}/units/order"
    for bad in ([u2], [u2, u2, i["cu"]], [u2, i["cu"], i["wu"]], []): assert env.c.put(o, headers=env.fac, json={"ids": bad}).status_code == 400
    assert unit_ids(i["chem"]) == [i["cu"], u2]

# 17-20 ordering
def test_order_persists_across_restart_and_keeps_ids_progress_and_quizzes(env):
    i = setup(env); water = i["topic"]["Water"]
    u2 = new_unit(env, env.fac, i["chem"], "U2").json()["id"]; u3 = new_unit(env, env.fac, i["chem"], "U3").json()["id"]
    b = new_topic(env, env.fac, i["cu"], "B").json()["id"]; c = new_topic(env, env.fac, i["cu"], "C", published=False).json()["id"]
    q = env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": i["cu"], "title": "Q", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.fac, json={"questions": [{"text": "t", "options": ["a", "b"], "correct": 0}]})
    env.c.post(f"/api/topics/{water}/read", headers=env.stu); env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]})
    before = env.c.get(f"/api/topics/{water}", headers=env.admin).json()
    env.c.put(f"/api/courses/{i['chem']}/units/order", headers=env.fac, json={"ids": [u3, i["cu"], u2]})
    env.c.put(f"/api/units/{i['cu']}/topics/order", headers=env.fac, json={"ids": [c, water, b]})
    main.upgrade_schema(); main.boot()  # what a restart runs; migrations must not reset the order
    assert unit_ids(i["chem"]) == [u3, i["cu"], u2] and topic_ids(i["cu"]) == [c, water, b]                                            # 17-19
    assert sorted([u3, i["cu"], u2]) == sorted(unit_ids(i["chem"])) and {water, b, c} == set(topic_ids(i["cu"]))                        # 20
    after = env.c.get(f"/api/topics/{water}", headers=env.admin).json(); assert {k: v for k, v in after.items() if k != "nav"} == {k: v for k, v in before.items() if k != "nav"}  # only its place among its neighbours changes
    with Session_() as s: assert s.query(Progress).filter_by(topic_id=water).count() == 1 and s.query(Attempt).filter_by(quiz_id=q).count() == 1 and s.get(Topic, c).published is False
    assert course_units(env, i["chem"], env.stu)[1] == ("U1", ["Water", "B"])  # students see the owner's order, without the draft

# 21-24 content
def test_content_saves_without_publishing_and_students_see_only_published(env):
    i = setup(env); md = "Hardness: $\\ce{Ca^2+}$ and $x^2$\n\n![scale](/api/uploads/" + "a" * 32 + ".png)"
    t = new_topic(env, env.fac, i["cu"], "Hardness", content=md, published=False).json()["id"]                                       # 21
    assert env.c.get(f"/api/topics/{t}", headers=env.fac).json()["content"] == md
    assert env.c.put(f"/api/topics/{t}", headers=env.fac, json={"title": "Hardness", "unit_id": i["cu"], "content": md + "\n\nMore."}).status_code == 200  # 22
    got = env.c.get(f"/api/topics/{t}", headers=env.fac).json(); assert got["content"].endswith("More.") and got["published"] is False and got["can_edit"] is True
    assert env.c.get(f"/api/topics/{t}", headers=env.stu).status_code == 404                                                           # 24
    env.c.put(f"/api/topics/{t}/publish", headers=env.fac, json={"published": True})
    st = env.c.get(f"/api/topics/{t}", headers=env.stu); assert st.status_code == 200 and st.json()["content"].endswith("More.") and st.json()["can_edit"] is False  # 23
    assert env.c.put(f"/api/topics/{t}", headers=env.fac, json={"title": "Hardness", "unit_id": i["cu"], "content": "v3"}).status_code == 200
    assert env.c.get(f"/api/topics/{t}", headers=env.stu).json()["published"] is True  # editing keeps it published, too
    assert env.c.put(f"/api/topics/{t}", headers=env.fac, json={"title": "", "unit_id": i["cu"]}).status_code == 400

# 25-28 who may do what, plus the owner change of Prompt 03
def test_admin_owner_other_faculty_and_student(env):
    i = setup(env)
    def ops(h, tag):
        u = new_unit(env, h, i["chem"], "U-" + tag); t = new_topic(env, h, i["cu"], "T-" + tag, published=False)
        codes = [u.status_code, t.status_code]
        if t.status_code == 200:
            tid = t.json()["id"]
            codes += [env.c.put(f"/api/topics/{tid}", headers=h, json={"title": "T2-" + tag, "unit_id": i["cu"], "content": "c"}).status_code,
                      env.c.put(f"/api/topics/{tid}/publish", headers=h, json={"published": True}).status_code,
                      env.c.put(f"/api/units/{i['cu']}/topics/order", headers=h, json={"ids": list(reversed(topic_ids(i["cu"])))}).status_code,
                      env.c.delete(f"/api/topics/{tid}", headers=h).status_code]
        else:
            codes += [env.c.put(f"/api/topics/{i['topic']['Water']}", headers=h, json={"title": "x", "unit_id": i["cu"]}).status_code,
                      env.c.put(f"/api/units/{i['cu']}/publish", headers=h, json={"published": True}).status_code,
                      env.c.put(f"/api/units/{i['cu']}/topics/order", headers=h, json={"ids": topic_ids(i["cu"])}).status_code,
                      env.c.delete(f"/api/topics/{i['topic']['Water']}", headers=h).status_code]
        return set(codes)
    assert ops(env.admin, "a") == {200}            # 25
    assert ops(env.fac, "f") == {200}              # 26
    assert ops(env.fac2, "x") == {403}             # 27
    assert ops(env.stu, "s") == {403}              # 28
    env.c.put(f"/api/courses/{i['chem']}/owner", headers=env.admin, json={"user_id": uid("fac2@x.com")})  # owner change takes effect at once
    assert ops(env.fac, "f2") == {403} and ops(env.fac2, "x2") == {200}

def test_drafts_visible_to_admin_and_owner_only(env):
    i = setup(env); d = new_topic(env, env.fac, i["cu"], "Draft", published=False).json()["id"]
    assert [env.c.get(f"/api/topics/{d}", headers=h).status_code for h in (env.admin, env.fac, env.fac2, env.stu)] == [200, 200, 404, 404]
    assert ["Draft" in course_units(env, i["chem"], h)[0][1] for h in (env.admin, env.fac, env.fac2, env.stu)] == [True, True, False, False]

# delete safety
def test_deleting_topics_and_units_removes_their_dependents_and_nothing_else(env):
    i = setup(env); water, tools = i["topic"]["Water"], i["topic"]["Tools"]
    q = env.c.post("/api/quizzes", headers=env.fac, json={"unit_id": i["cu"], "title": "Q", "published": True}).json()["id"]
    env.c.put(f"/api/quizzes/{q}/questions", headers=env.fac, json={"questions": [{"text": "t", "options": ["a", "b"], "correct": 0}]})
    extra = new_topic(env, env.fac, i["cu"], "Extra").json()["id"]
    for t in (water, extra, tools): env.c.post(f"/api/topics/{t}/read", headers=env.stu); env.c.put(f"/api/topics/{t}/bookmark", headers=env.stu)
    env.c.post(f"/api/quizzes/{q}/attempt", headers=env.stu, json={"answers": [0]})
    with Session_() as s: s.add_all([AICache(topic_id=t, kind="explain", chash=str(t), text="x") for t in (water, tools)]); s.commit()
    def left(t):
        with Session_() as s: return tuple(s.query(m).filter_by(topic_id=t).count() for m in (Progress, Bookmark, AICache))
    assert env.c.delete(f"/api/topics/{extra}", headers=env.fac).status_code == 200 and left(extra) == (0, 0, 0) and left(water) == (1, 1, 1)
    assert env.c.delete(f"/api/units/{i['cu']}", headers=env.fac).status_code == 200
    with Session_() as s:
        assert s.get(Topic, water) is None and (s.query(Quiz).count(), s.query(Question).count(), s.query(Attempt).count()) == (0, 0, 0)
    assert left(water) == (0, 0, 0) and left(tools) == (1, 1, 1)  # another course's records are untouched

def test_position_migration_fills_today_order_and_keeps_set_positions(env):
    i = setup(env)
    with Session_() as s:
        for u in s.query(Unit): u.position = None
        for t in s.query(Topic): t.position = None
        s.flush(); extra = Unit(name="Late", course_id=i["chem"]); s.add(extra); s.flush(); late = extra.id; s.commit()
    with main.engine.begin() as c: main.positions(c)
    assert unit_ids(i["chem"]) == [i["cu"], late]
    with Session_() as s: assert all(x.position is not None for x in s.query(Unit)) and all(x.position is not None for x in s.query(Topic))
    env.c.put(f"/api/courses/{i['chem']}/units/order", headers=env.admin, json={"ids": [late, i["cu"]]})
    with main.engine.begin() as c: main.positions(c)
    assert unit_ids(i["chem"]) == [late, i["cu"]] and "0011_unit_topic_positions" in main.applied_migrations()
