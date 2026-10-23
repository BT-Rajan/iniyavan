import main
from main import Session_, Topic
from tests.test_access import CSV

PAGE = """<!doctype html><html><head><title>Bernoulli lab</title><style>body{font-family:serif}</style></head>
<body><h1>Bernoulli lab</h1><p id="out">Pressure falls where the fluid speeds up.</p>
<script>document.getElementById('out').textContent += ' secretscriptword';</script></body></html>"""

def unit_of(env):
    env.csv(CSV)
def make(env, fmt, content, title="Lab"):
    unit = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    r = env.c.post("/api/topics", headers=env.admin, json={"unit_id": unit, "title": title, "content": content, "content_format": fmt, "published": True}); assert r.status_code == 200, r.text
    return r.json()["id"]

def test_html_with_scripts_is_kept_only_when_asked_and_plain_markdown_files_are_content(env):
    unit_of(env); unit = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["id"]
    kept = env.c.post("/api/topics/from-files", headers=env.admin, json={"unit_id": unit, "html": PAGE, "scripts": True}).json()
    assert kept["content_format"] == "interactive" and "<script>" in kept["content"] and kept["title"] == "Bernoulli lab"
    cleaned = env.c.post("/api/topics/from-files", headers=env.admin, json={"unit_id": unit, "html": PAGE}).json()
    assert cleaned["content_format"] == "html" and "<script" not in cleaned["content"] and any("JavaScript was removed" in w for w in cleaned["warnings"])
    md = env.c.post("/api/topics/from-files", headers=env.admin, json={"unit_id": unit, "config": "# Hardness of water\n\nHard water has **calcium**.\n\n- boiling\n- lime soda\n"}).json()
    assert md["title"] == "Hardness of water" and md["content_format"] == "markdown" and "Hard water has **calcium**." in md["content"] and not md["warnings"]

def test_interactive_pages_run_only_in_a_sandboxed_frame(env):
    unit_of(env); tid = make(env, "interactive", PAGE)
    with Session_() as s: assert "<script>" in s.get(Topic, tid).content  # kept as uploaded
    t = env.c.get(f"/api/topics/{tid}", headers=env.admin).json(); assert t["content_format"] == "interactive" and t["frame_url"].startswith(f"/api/topics/{tid}/frame?t=")
    r = env.c.get(t["frame_url"])
    csp = r.headers["content-security-policy"]
    assert r.status_code == 200 and "secretscriptword" in r.text and "zgHighlighter" in r.text and r.text.index("zgHighlighter") > r.text.index("secretscriptword")
    assert csp.startswith("sandbox allow-scripts") and "allow-same-origin" not in csp and "frame-ancestors 'self'" in csp and r.headers["x-frame-options"] == "SAMEORIGIN"
    token = t["frame_url"].split("t=")[1]
    assert env.c.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401  # a frame pass is never a sign-in
    other = make(env, "interactive", PAGE, "Other")
    assert env.c.get(f"/api/topics/{other}/frame?t={token}").status_code == 401 and env.c.get(f"/api/topics/{tid}/frame?t=junk").status_code == 401
    md = make(env, "markdown", "Plain notes", "Notes"); assert "frame_url" not in env.c.get(f"/api/topics/{md}", headers=env.admin).json()
    assert "secretscriptword" not in str(env.c.get("/api/search", headers=env.admin, params={"q": "secretscriptword"}).json().get("results"))  # search reads the words, not the scripts
    pv = env.c.post("/api/topics/frame-preview", headers=env.admin, json={"html": PAGE}).json()
    assert env.c.get(pv["url"]).status_code == 200 and env.c.get(pv["url"]).headers["content-security-policy"].startswith("sandbox")
    assert env.c.post("/api/topics/frame-preview", headers=env.stu, json={"html": PAGE}).status_code == 403 and env.c.get("/api/frame-preview/nope").status_code == 404

def test_highlights_are_saved_per_person(env):
    unit_of(env); tid = make(env, "markdown", "Hard water has calcium. Soft water has none.")
    h = env.c.post(f"/api/topics/{tid}/highlights", headers=env.fac, json={"text": " Soft water has none. ", "prefix": "calcium. "}).json()
    assert h["text"] == "Soft water has none." and h["prefix"] == "calcium. "
    assert [x["id"] for x in env.c.get(f"/api/topics/{tid}/highlights", headers=env.fac).json()["items"]] == [h["id"]]
    assert env.c.get(f"/api/topics/{tid}/highlights", headers=env.admin).json()["items"] == []  # each person sees only their own
    assert env.c.delete(f"/api/me/highlights/{h['id']}", headers=env.admin).status_code == 404
    assert env.c.post(f"/api/topics/{tid}/highlights", headers=env.fac, json={"text": "   "}).status_code == 400
    assert env.c.post(f"/api/topics/{tid}/highlights", headers=env.fac, json={"text": "x" * 5001}).status_code == 400
    assert env.c.delete(f"/api/me/highlights/{h['id']}", headers=env.fac).json() == {"ok": True}
    assert env.c.get(f"/api/topics/{tid}/highlights", headers=env.fac).json()["items"] == []
    assert env.c.post("/api/topics/9999/highlights", headers=env.fac, json={"text": "a"}).status_code == 404
