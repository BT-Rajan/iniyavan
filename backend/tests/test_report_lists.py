import datetime as dt
from main import Session_, AuditLog, AICache, User

def setup(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\nMech,Semester 1,Chem,U1,Steam,s\nMech,Semester 1,Chem,U1,Fuel,f\n")
    p = env.c.get("/api/tree", headers=env.admin).json()[0]; tids = {t["title"]: t["id"] for t in p["semesters"][0]["courses"][0]["units"][0]["topics"]}
    with Session_() as s:
        for u in s.query(User).filter_by(role="student"): u.program_id, u.semester = p["id"], 1
        s.add(User(name="Zara Never", email="zara@x.com", pw="x", role="student", program_id=p["id"], semester=1, active=False)); s.commit()
    for t in ("Water", "Water", "Steam"): assert env.c.post(f"/api/topics/{tids[t]}/read", headers=env.stu).status_code == 200
    return tids

def test_report_lists_search_filter_sort_and_page(env):
    tids = setup(env); get = lambda u: env.c.get("/api/admin/reports/" + u, headers=env.admin).json()
    r = get("topics"); assert [x["title"] for x in r["items"]] == ["Water", "Steam"] and r["items"][0]["course"] == "Chem"
    assert [x["title"] for x in get("topics?sort=title")["items"]] == ["Steam", "Water"]
    assert get("topics?q=ste")["total"] == 1 and get("topics?limit=1&offset=1")["items"][0]["title"] == "Steam"
    assert get("students")["items"][0]["email"] == "stu@x.com"  # most recently active first, never-active last
    assert [x["email"] for x in get("students?show=never")["items"]] == ["zara@x.com"]
    assert [x["email"] for x in get("students?show=disabled")["items"]] == ["zara@x.com"] and get("students?q=zara")["total"] == 1
    assert get("students?sort=quiet")["items"][0]["email"] == "zara@x.com" and get("students?sort=most")["items"][0]["topics_read"] == 2
    with Session_() as s: s.add_all([AICache(topic_id=tids["Water"], kind="explain", chash="a", text="x", tokens=100, hits=3), AICache(topic_id=tids["Fuel"], kind="answer", chash="b", text="y", tokens=10, hits=9)]); s.commit()
    assert [x["title"] for x in get("ai")["items"]] == ["Water", "Fuel"] and [x["title"] for x in get("ai?sort=hits")["items"]] == ["Fuel", "Water"]
    assert get("ai?show=answer")["total"] == 1 and get("ai")["items"][0]["saved"] == 300
    assert env.c.get("/api/admin/reports/nope", headers=env.admin).status_code == 404
    assert env.c.get("/api/admin/reports/students", headers=env.fac).status_code == 403

def test_activity_log_filters_sort_and_csv(env):
    with Session_() as s:
        old = dt.datetime.utcnow() - dt.timedelta(days=40)
        s.add_all([AuditLog(user_id=1, method="POST", path="/api/courses", status=200, at=old), AuditLog(user_id=1, method="DELETE", path="/api/courses/4", status=403),
                   AuditLog(user_id=1, method="PATCH", path="/api/topics/2", status=200)]); s.commit()
    get = lambda u: env.c.get("/api/admin/audit" + u, headers=env.admin).json()
    assert get("?action=changed")["items"][0]["path"] == "/api/topics/2" and get("?action=deleted")["total"] == 1
    assert get("?result=failed")["total"] == 1 and get("?days=7")["total"] == 2
    assert get("?sort=oldest")["items"][0]["path"] == "/api/courses"
    r = env.c.get("/api/admin/audit?format=csv&action=deleted", headers=env.admin); assert r.status_code == 200 and "/api/courses/4" in r.text and "/api/topics/2" not in r.text

def test_a_language_choice_is_not_in_the_activity_log(env):
    env.c.put("/api/me/lang", headers=env.stu, json={"lang": "ar"})
    assert env.c.get("/api/admin/audit?q=lang", headers=env.admin).json()["total"] == 0
