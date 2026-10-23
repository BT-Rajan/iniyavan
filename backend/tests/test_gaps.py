import datetime as dt
import main
from main import Session_, Topic, User
from tests.test_access import CSV

def unit_id(env, n=0):
    env.csv(CSV); return env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][n]["units"][0]["id"]
def topic(env, fmt="markdown", content="Hard water has calcium. Soft water has none.", title="T"):
    u = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    return env.c.post("/api/topics", headers=env.admin, json={"unit_id": u, "title": title, "content": content, "content_format": fmt, "published": True}).json()["id"]

def test_bulk_upload_makes_one_topic_per_file_in_file_name_order(env):
    uid = unit_id(env)
    files = [{"name": "lesson/10 Summary.md", "text": "# Summary\n\nAll of it."},
             {"name": "lesson/2 Intro.html", "text": "<html><head><title>Intro page</title></head><body><p>Hello</p><img src='img/fig.png'><script>x()</script></body></html>"},
             {"name": "lesson/3 Config.md", "text": "---\ntitle: Configured\npublished: yes\n---\n## Topic content\nBody text\n## Question pattern\n- 2 marks"},
             {"name": "lesson/notes.pdf", "text": "%PDF"}]
    post = lambda **kw: env.c.post(f"/api/units/{uid}/topics/bulk", headers=env.admin, json={"files": files, **kw})
    pv = post().json(); rows = pv["topics"]
    assert pv["dry_run"] and pv["ready"] == 3 and [r["file"] for r in rows] == ["lesson/2 Intro.html", "lesson/3 Config.md", "lesson/10 Summary.md", "lesson/notes.pdf"]
    assert [r["title"] for r in rows[:3]] == ["Intro page", "Configured", "Summary"] and [r["format"] for r in rows[:3]] == ["html", "markdown", "markdown"]
    assert any("fig.png" in w for w in rows[0]["warnings"]) and any("JavaScript is removed" in w for w in rows[0]["warnings"]) and not rows[3]["ok"]
    with Session_() as s: assert s.query(Topic).filter_by(unit_id=uid).count() == 1  # a dry run makes nothing
    done = post(dry_run=False, scripts=True, images={"fig.png": "/api/uploads/" + "a" * 32 + ".png"}).json()
    assert done["created"] == 3
    with Session_() as s:
        made = s.query(Topic).filter_by(unit_id=uid).order_by(Topic.position).all()[1:]
        assert [t.title for t in made] == ["Intro page", "Configured", "Summary"] and made[0].content_format == "interactive" and "<script>x()</script>" in made[0].content
        assert "/api/uploads/" + "a" * 32 + ".png" in made[0].content and made[1].published is True and made[2].published is False and made[1].question_pattern == "- 2 marks"
    assert env.c.post(f"/api/units/{uid}/topics/bulk", headers=env.fac, json={"files": files}).status_code == 403  # not their course
    assert env.c.post(f"/api/units/{uid}/topics/bulk", headers=env.admin, json={"files": []}).status_code == 400

def test_interactive_pages_keep_their_local_storage_per_person(env):
    unit_id(env); tid = topic(env, "interactive", "<html><head><title>x</title></head><body><script>localStorage.setItem('n', '1')</script></body></html>")
    url = env.c.get(f"/api/topics/{tid}", headers=env.fac).json()["frame_url"]
    page = env.c.get(url).text
    assert page.index("window.zigora") < page.index("localStorage.setItem")  # the stand-in comes before the page's own scripts
    assert env.c.put(f"/api/topics/{tid}/store", headers=env.fac, json={"data": {"score": "7", "evil": "</script><b>"}}).json() == {"ok": True}
    page = env.c.get(env.c.get(f"/api/topics/{tid}", headers=env.fac).json()["frame_url"]).text
    assert '"score": "7"' in page and "</script><b>" not in page.split("window.zigora")[0]  # saved data comes back, safely escaped
    other = env.c.get(env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["frame_url"]).text
    assert '"score"' not in other  # each person has their own
    assert env.c.put(f"/api/topics/{tid}/store", headers=env.fac, json={"data": {"big": "x" * 100_001}}).status_code == 413
    md = topic(env, title="Plain"); assert env.c.put(f"/api/topics/{md}/store", headers=env.fac, json={"data": {}}).status_code == 404

def test_highlights_have_colours_notes_and_one_list(env):
    unit_id(env); a = topic(env, title="Water"); b = topic(env, content="Steam turns turbines.", title="Steam")
    h1 = env.c.post(f"/api/topics/{a}/highlights", headers=env.fac, json={"text": "Hard water", "color": "yellow"}).json()
    h2 = env.c.post(f"/api/topics/{b}/highlights", headers=env.fac, json={"text": "turns turbines"}).json()
    assert h1["color"] == "yellow" and h2["color"] == "coral" and h2["note"] == ""
    assert env.c.post(f"/api/topics/{a}/highlights", headers=env.fac, json={"text": "x", "color": "pink"}).status_code == 400
    e = env.c.patch(f"/api/me/highlights/{h2['id']}", headers=env.fac, json={"note": "  Exam favourite ", "color": "green"}).json()
    assert e["note"] == "Exam favourite" and e["color"] == "green"
    assert env.c.patch(f"/api/me/highlights/{h2['id']}", headers=env.admin, json={"note": "x"}).status_code == 404
    mine = env.c.get("/api/me/highlights", headers=env.fac).json()
    assert mine["total"] == 2 and [i["topic"] for i in mine["items"]] == ["Steam", "Water"] and mine["items"][0]["note"] == "Exam favourite"
    assert [i["id"] for i in env.c.get("/api/me/highlights", headers=env.fac, params={"q": "favourite"}).json()["items"]] == [h2["id"]]
    assert [i["id"] for i in env.c.get("/api/me/highlights", headers=env.fac, params={"color": "yellow"}).json()["items"]] == [h1["id"]]
    assert env.c.get("/api/me/highlights", headers=env.admin).json()["total"] == 0

def test_notifications_remember_what_was_seen_and_send_a_daily_summary(env, monkeypatch):
    env.csv(CSV); env.add_user("new@x.com")  # an unplaced student: something for the admin's attention
    n = env.c.get("/api/me/notifications", headers=env.admin).json()
    assert n["items"] and all(i["unread"] for i in n["items"]) and n["mail"] is False and n["digest"] is False
    env.c.post("/api/me/notifications/seen", headers=env.admin, json={"keys": [i["key"] for i in n["items"]]})
    assert not any(i["unread"] for i in env.c.get("/api/me/notifications", headers=env.admin).json()["items"])
    env.add_user("new2@x.com")  # the count changes, so it is new again
    assert any(i["unread"] for i in env.c.get("/api/me/notifications", headers=env.admin).json()["items"])
    assert env.c.put("/api/me/notifications/settings", headers=env.admin, json={"digest": True}).status_code == 400  # no email set up
    monkeypatch.setattr(main, "mail_on", lambda: True); sent = []
    monkeypatch.setattr(main, "send_mail", lambda to, subj, body: sent.append((to, subj, body)))
    assert env.c.put("/api/me/notifications/settings", headers=env.admin, json={"digest": True}).json() == {"digest": True}
    morning = dt.datetime(2026, 10, 24, 3, 0)  # 08:30 in India
    assert main.send_digests(morning) == 1 and sent[0][0] == "admin@x.com" and "new" in sent[0][1]
    assert main.send_digests(morning + dt.timedelta(hours=2)) == 0  # once a day
    assert main.send_digests(dt.datetime(2026, 10, 25, 0, 0)) == 0  # 05:30 local: too early
    env.c.put("/api/me/notifications/settings", headers=env.admin, json={"digest": False})
    assert main.send_digests(dt.datetime(2026, 10, 26, 3, 0)) == 0
    stu = env.c.get("/api/me/notifications", headers=env.stu).json(); assert stu["items"] == [] or all("key" in i for i in stu["items"])
