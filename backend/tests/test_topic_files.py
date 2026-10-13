import base64, os
import main
from main import Session_, Topic, TopicVersion
from tests.test_access import CSV, ids

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
HTML = f"""<!doctype html><html><head><title>Water treatment</title><style>p{{color:red}}</style><script>alert(1)</script></head>
<body><h1 style="color:blue">Water treatment</h1><p onclick="steal()">Hard water has <b>calcium</b>.</p>
<p dir="rtl">وَزِينَتَهَا</p><img src="data:image/png;base64,{base64.b64encode(PNG).decode()}" alt="tank"><img src="figs/boiler.png" alt="boiler"><img src="lost.png">
<a href="javascript:alert(1)">bad</a> <a href="https://example.org">good</a><iframe src="https://evil.example"></iframe></body></html>"""
CONFIG = """---
title: 1. Water treatment
published: no
deadline: 2026-11-01 17:30
colour: blue
---
## Question pattern
- 2 marks: define hardness

## Sample content
**Q:** What causes hardness?
## Answer (not a section of its own)
Calcium and magnesium salts.

## How an answer should be
Start with the definition.
"""

def setup(env):
    env.csv(CSV); i = ids(); return i, i["unit"][i["course"]["Chem"]]
def parse(env, unit, h=None, **b): return env.c.post("/api/topics/from-files", headers=h or env.admin, json={"unit_id": unit, **b})

def test_html_and_config_fill_a_topic_with_safe_content(env):
    i, unit = setup(env)
    pngs = lambda: {n for n in os.listdir(main.UPLOADS) if n.endswith(".png")} if os.path.isdir(main.UPLOADS) else set()
    up = env.c.post("/api/uploads", headers={**env.admin, "Content-Type": "image/png"}, content=PNG); before = pngs()
    boiler = up.json()["url"]
    r = parse(env, unit, html=HTML, config=CONFIG, images={"boiler.png": boiler}).json()
    assert (r["title"], r["published"], r["learning_due_at"], r["content_format"], r["images_saved"]) == ("1. Water treatment", False, "2026-11-01T17:30", "html", 1)
    c = r["content"]
    for bad in ("<script", "alert(", "onclick", "style=", "<iframe", "javascript:", "<title", "<style"): assert bad not in c, bad
    assert '<p dir="rtl">' in c and "<b>calcium</b>" in c and 'href="https://example.org"' in c and f'src="{boiler}"' in c and c.count("<img") == 2 and "lost.png" not in c
    assert r["question_pattern"] == "- 2 marks: define hardness" and r["guideline"] == "Start with the definition."
    assert r["sample_content"].startswith("**Q:** What causes hardness?") and "## Answer (not a section of its own)" in r["sample_content"]  # unknown headings stay in their section
    assert any("colour" in w for w in r["warnings"]) and any("lost.png" in w for w in r["warnings"])
    assert len(pngs() - before) == 1  # the embedded image became an upload
    # saving it the way the editor does keeps it HTML, and the topic shows it cleaned
    tid = env.c.post("/api/topics", headers=env.admin, json={"unit_id": unit, "title": r["title"], "content": r["content"], "content_format": "html", "published": True}).json()["id"]
    t = env.c.get(f"/api/topics/{tid}", headers=env.admin).json(); assert t["content_format"] == "html" and t["content"] == c

def test_html_is_cleaned_on_every_save_and_on_the_way_out(env):
    i, unit = setup(env)
    tid = env.c.post("/api/topics", headers=env.admin, json={"unit_id": unit, "title": "T", "content": "<p>x</p><script>bad()</script><img src=x onerror=bad()>", "content_format": "html"}).json()["id"]
    with Session_() as s: stored = s.get(Topic, tid).content
    assert "script" not in stored and "onerror" not in stored
    with Session_() as s: s.get(Topic, tid).content = "<p>y</p><script>bad()</script>"; s.commit()  # whatever got into the database
    assert "script" not in env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["content"]
    assert env.c.post("/api/topics", headers=env.admin, json={"unit_id": unit, "title": "T2", "content": "x", "content_format": "pdf"}).status_code == 400
    # content sent without a format keeps the topic's format; markdown topics stay markdown
    env.c.put(f"/api/topics/{tid}", headers=env.admin, json={"unit_id": unit, "title": "T", "content": "<p>z</p>"})
    assert env.c.get(f"/api/topics/{tid}", headers=env.admin).json()["content_format"] == "html"
    md = env.c.get(f"/api/topics/{i['topic']['Water']}", headers=env.admin).json(); assert md["content_format"] == "markdown" and md["content"] == "w"

def test_versions_copies_search_and_csv_follow_the_format(env):
    i, unit = setup(env); w = i["topic"]["Water"]
    env.c.put(f"/api/topics/{w}", headers=env.admin, json={"unit_id": unit, "title": "Water", "content": "<p>Hardness of <b>water</b> &amp; salts</p>", "content_format": "html"})
    vs = env.c.get(f"/api/topics/{w}/versions", headers=env.admin).json(); first = vs[-1]["id"]
    assert env.c.get(f"/api/topic-versions/{first}", headers=env.admin).json()["content_format"] == "markdown"
    env.c.post(f"/api/topic-versions/{first}/restore", headers=env.admin)
    assert env.c.get(f"/api/topics/{w}", headers=env.admin).json()["content_format"] == "markdown"  # restoring brings the old format back
    env.c.put(f"/api/topics/{w}", headers=env.admin, json={"unit_id": unit, "title": "Water", "content": "<p>Hardness of <b>water</b> &amp; salts</p>", "content_format": "html"})
    hit = env.c.get("/api/search?q=hardness", headers=env.admin).json()["results"][0]; assert "<b>" not in hit["snippet"] and "&amp;" not in hit["snippet"]
    other = i["unit"][i["course"]["Workshop"]]
    cp = env.c.post(f"/api/topics/{w}/copy", headers=env.admin, json={"unit_id": other}).json()["id"]
    assert env.c.get(f"/api/topics/{cp}", headers=env.admin).json()["content_format"] == "html"
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,plain *markdown*\n")
    assert env.c.get(f"/api/topics/{w}", headers=env.admin).json()["content_format"] == "markdown"

def test_config_only_permissions_and_limits(env):
    i, unit = setup(env)
    r = parse(env, unit, config="# My topic\n\n## Topic content\nSome *notes*\n\n## Question pattern\nQ\n").json()
    assert (r["title"], r["content"], r["content_format"], r["question_pattern"]) == ("My topic", "Some *notes*", "markdown", "Q")
    assert parse(env, unit).status_code == 400
    assert parse(env, unit, h=env.stu, config="x").status_code == 403 and parse(env, unit, h=env.fac, config="x").status_code == 403  # not the course owner
    r = parse(env, unit, html="<html><body><h1>From the heading</h1><p>t</p></body></html>").json(); assert r["title"] == "From the heading" and "published" not in r
    bad = parse(env, unit, config="---\npublished: maybe\ndeadline: next week\n---\n## Sample content\nx").json()
    assert "published" not in bad and "learning_due_at" not in bad and len(bad["warnings"]) == 2

def test_preview_cleaning_is_for_staff(env):
    r = env.c.post("/api/topics/clean-html", headers=env.fac, json={"html": "<p>ok</p><img src=x onerror=bad()><script>x()</script>"}).json()["html"]
    assert r == '<p>ok</p><img src="x">' and env.c.post("/api/topics/clean-html", headers=env.stu, json={"html": "x"}).status_code == 403
