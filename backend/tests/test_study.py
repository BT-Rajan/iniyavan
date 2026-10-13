import io, json, re, zipfile
import main
from main import Session_, Setting, User, StudyCourse, StudyTopic, StudyQuiz, StudyAttempt, StudyAICall

TEXT = """# Hard water

Hard water contains calcium and magnesium salts.

Temporary hardness is removed by boiling.

# Treatment

Lime-soda process softens water.

Ion exchange uses resins.

Reverse osmosis pushes water through a membrane."""

class FakeAI:  # stands in for DeepSeek: answers by what the system prompt asks for
    calls = []
    @classmethod
    async def __call__(cls, key, model, messages, max_tokens=None, timeout=45):
        system, msg = messages[0]["content"], messages[1]["content"]; cls.calls.append((system[:30], msg))
        if system.startswith("You turn a student's study material"):
            n = int(re.search(r"has (\d+) paragraphs", msg).group(1))
            return json.dumps({"units": [{"title": "Hard water", "topics": [{"title": "What hardness is", "summary": "s", "from": 1, "to": 2}, {"title": "Boiling", "from": 3, "to": 3}]},
                                         {"title": "Treatment", "topics": [{"title": "Softening", "from": 4, "to": n - 1}, {"title": "Membranes", "from": n, "to": n}, {"title": "bad", "from": 99}]}]}), 10
        if system.startswith("You write multiple-choice"):
            k = int(re.search(r"Write (\d+) questions", msg).group(1))
            qs = [{"text": f"Q{i}?", "options": ["right", "wrong", "other", "none"], "correct": 0, "explanation": "Because.", "concept": "Softening" if i % 2 else "Hardness"} for i in range(k)]
            qs.append({"text": "broken", "options": ["a"], "correct": 3})
            return "```json\n" + json.dumps({"questions": qs}) + "\n```", 10
        return "Here is an explanation.", 10
fake = FakeAI()

def setup(env, monkeypatch, key="sk-test"):
    monkeypatch.setattr(main, "deepseek", fake); FakeAI.calls = []
    if key:
        with Session_() as s: s.merge(Setting(k="deepseek_key", v=key)); s.commit()
def new(env, h=None, title="Chemistry notes"): r = env.c.post("/api/study/courses", headers=h or env.stu, json={"title": title}); assert r.status_code == 200, r.text; return r.json()["id"]
def docx(paras, table=None):
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f'<w:p><w:pPr>{f"<w:pStyle w:val=\'{st}\'/>" if st else ""}</w:pPr><w:r><w:t>{t}</w:t></w:r></w:p>' for st, t in paras)
    if table: body += "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>" for row in table) + "</w:tbl>"
    b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("word/document.xml", f"<w:document {W}><w:body>{body}</w:body></w:document>"); z.close(); return b.getvalue()
def pdf(lines):  # a tiny one-page PDF with real text
    stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({l}) Tj 0 -16 Td" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1): offs.append(len(out)); out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out); out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
def upload(env, cid, name, data, h=None): return env.c.post(f"/api/study/courses/{cid}/files?name={name}", headers={**(h or env.stu), "Content-Type": "application/octet-stream"}, content=data)

def test_material_from_text_word_and_pdf(env, monkeypatch):
    setup(env, monkeypatch); cid = new(env)
    assert env.c.post(f"/api/study/courses/{cid}/text", headers=env.stu, json={"text": TEXT}).json()["paras"] == 7
    w = upload(env, cid, "notes.docx", docx([("Heading1", "Ions"), ("", "Calcium ions."), ("ListParagraph", "one"), ("ListParagraph", "two")], [["Ion", "Charge"], ["Ca", "2+"]])).json()
    assert (w["kind"], w["paras"]) == ("docx", 4)
    p = upload(env, cid, "scan.pdf", pdf(["CHAPTER 1 WATER", "Water is a solvent.", "It dissolves salts."])).json(); assert p["kind"] == "pdf" and p["paras"] >= 2
    with Session_() as s: paras = json.loads(s.get(StudyCourse, cid).paras)
    assert paras[7] == "# Ions" and paras[9] == "- one\n- two" and paras[10].startswith("| Ion | Charge |") and any("Water is a solvent." in x for x in paras[11:])
    assert upload(env, cid, "empty.pdf", pdf([""])).status_code == 400  # no text layer
    assert upload(env, cid, "old.doc", b"PK\x03\x04junk").status_code == 400 and upload(env, cid, "x.exe", b"MZ").status_code == 400
    d = env.c.get(f"/api/study/courses/{cid}", headers=env.stu).json(); assert [x["name"] for x in d["sources"]] == ["Pasted text", "notes.docx", "scan.pdf"]
    assert env.c.delete(f"/api/study/courses/{cid}/sources/1", headers=env.stu).status_code == 200
    with Session_() as s: assert json.loads(s.get(StudyCourse, cid).paras)[7].startswith("## ") or "Water" in json.loads(s.get(StudyCourse, cid).paras)[7]

def test_wizard_slices_previews_adjusts_and_finishes(env, monkeypatch):
    setup(env, monkeypatch); cid = new(env)
    assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={}).status_code == 400  # no material yet
    env.c.post(f"/api/study/courses/{cid}/text", headers=env.stu, json={"text": TEXT})
    r = env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={"notes": "One topic per method"}).json()
    plan = r["plan"]; assert r["sliced_by"] == "ai" and [u["title"] for u in plan["units"]] == ["Hard water", "Treatment"]
    tops = [t for u in plan["units"] for t in u["topics"]]
    assert [(t["from"], t["to"]) for t in tops] == [(1, 2), (3, 3), (4, 6), (7, 7)] and tops[0]["words"] > 0 and tops[0]["excerpt"].startswith("Hard water Hard water contains")  # the bad topic was dropped, coverage is complete
    assert "One topic per method" in FakeAI.calls[-1][1] and "[7] Reverse osmosis" in FakeAI.calls[-1][1]
    assert env.c.get(f"/api/study/courses/{cid}/preview?start=4&end=6", headers=env.stu).json()["content"].startswith("# Treatment")
    # the student merges Boiling into the first topic and renames it
    edited = [{"title": "Hard water", "topics": [{"title": "Hardness and boiling", "from": 1, "to": 3}]}, plan["units"][1]]
    assert env.c.put(f"/api/study/courses/{cid}/plan", headers=env.stu, json={"units": edited}).status_code == 200
    assert env.c.put(f"/api/study/courses/{cid}/plan", headers=env.stu, json={"units": [{"title": "x", "topics": [{"from": 2, "to": 5}, {"from": 4, "to": 7}]}]}).status_code == 400
    h = env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={"method": "headings"}).json()["plan"]
    assert [u["title"] for u in h["units"]] == ["Hard water", "Treatment"]
    env.c.put(f"/api/study/courses/{cid}/plan", headers=env.stu, json={"units": edited})
    assert env.c.post(f"/api/study/courses/{cid}/finish", headers=env.stu, json={}).json()["topics"] == 3
    d = env.c.get(f"/api/study/courses/{cid}", headers=env.stu).json()
    assert d["status"] == "ready" and [[t["title"] for t in u["topics"]] for u in d["units"]] == [["Hardness and boiling"], ["Softening", "Membranes"]]
    with Session_() as s: t = s.query(StudyTopic).filter_by(title="Hardness and boiling").one(); assert "Temporary hardness" in t.content
    assert env.c.post(f"/api/study/courses/{cid}/finish", headers=env.stu, json={}).status_code == 409  # finishing again must be asked for
    assert env.c.post(f"/api/study/courses/{cid}/finish", headers=env.stu, json={"replace": True}).status_code == 200

def ready(env, monkeypatch, h=None):
    setup(env, monkeypatch); cid = new(env, h); h = h or env.stu
    env.c.post(f"/api/study/courses/{cid}/text", headers=h, json={"text": TEXT}); env.c.post(f"/api/study/courses/{cid}/slice", headers=h, json={})
    env.c.post(f"/api/study/courses/{cid}/finish", headers=h, json={})
    return cid, [t["id"] for u in env.c.get(f"/api/study/courses/{cid}", headers=h).json()["units"] for t in u["topics"]]

def test_topics_progress_explain_mcqs_and_quizzes(env, monkeypatch):
    cid, tids = ready(env, monkeypatch); t0 = tids[0]
    t = env.c.get(f"/api/study/topics/{t0}", headers=env.stu).json(); assert (t["position"], t["total"], t["next"]["id"], t["prev"]) == (1, 4, tids[1], None)
    env.c.put(f"/api/study/topics/{t0}/progress", headers=env.stu, json={"completed": True})
    e = env.c.get(f"/api/study/topics/{t0}/explain", headers=env.stu).json(); assert e == {"text": "Here is an explanation.", "cached": False}
    assert env.c.get(f"/api/study/topics/{t0}/explain", headers=env.stu).json()["cached"] is True
    m = env.c.post(f"/api/study/topics/{t0}/quizzes", headers=env.stu, json={"kind": "mcq"}).json()
    assert m["kind"] == "mcq" and len(m["questions"]) == 5 and "correct" not in m["questions"][0]  # the broken question was dropped; answers stay on the server
    ck = env.c.post(f"/api/study/quizzes/{m['id']}/check", headers=env.stu, json={"index": 0, "answer": 1}).json(); assert ck == {"ok": False, "correct": 0, "explanation": "Because."}
    q = env.c.post(f"/api/study/topics/{t0}/quizzes", headers=env.stu, json={"kind": "quiz"}).json(); assert len(q["questions"]) == 10
    assert env.c.post(f"/api/study/quizzes/{q['id']}/check", headers=env.stu, json={"index": 0, "answer": 0}).status_code == 400  # no peeking in a quiz
    assert "Q0?" in FakeAI.calls[-1][1]  # the second set is asked to differ from the first
    ans = [0] * 7 + [1, 1, None]
    r = env.c.post(f"/api/study/quizzes/{q['id']}/attempt", headers=env.stu, json={"answers": ans}).json()
    assert (r["score"], r["percent"], r["passed"]) == (7, 70, True) and r["results"][9]["correct"] == 0
    assert {a["title"]: a["percent"] for a in r["areas"]} == {"Softening": 60, "Hardness": 80} and r["summary"].startswith("Good at Hardness")
    p = env.c.get(f"/api/study/courses/{cid}/progress", headers=env.stu).json(); assert (p["completed"], p["quizzed"], p["average"]) == (1, 1, 70)
    d = env.c.get(f"/api/study/courses/{cid}", headers=env.stu).json(); assert d["units"][0]["topics"][0]["best"] == 70 and d["units"][0]["topics"][0]["status"] == "completed"
    assert env.c.post(f"/api/study/quizzes/{q['id']}/attempt", headers=env.stu, json={"answers": [9] * 10}).status_code == 400

def test_sharing_with_classmates_and_privacy(env, monkeypatch):
    with Session_() as s:
        from main import Program
        p = Program(name="Mech"); s.add(p); s.flush(); pid = p.id
        s.query(User).filter_by(email="stu@x.com").update({"program_id": pid}); s.commit()
    env.add_user("mate@x.com", program=pid); env.add_user("other@x.com"); mate, other = env.login("mate@x.com"), env.login("other@x.com")
    cid, tids = ready(env, monkeypatch)
    assert env.c.get(f"/api/study/courses/{cid}", headers=mate).status_code == 404  # private by default
    assert env.c.put(f"/api/study/courses/{cid}", headers=env.stu, json={"share": "program"}).status_code == 200
    assert [c["id"] for c in env.c.get("/api/study/courses", headers=mate).json()["shared"]] == [cid]
    assert env.c.get(f"/api/study/topics/{tids[0]}", headers=mate).status_code == 200 and env.c.get(f"/api/study/courses/{cid}", headers=other).status_code == 404
    d = env.c.get(f"/api/study/courses/{cid}", headers=mate).json(); assert d["can_edit"] is False and "sources" not in d and "plan" not in d
    assert env.c.put(f"/api/study/courses/{cid}", headers=mate, json={"title": "Mine now"}).status_code == 403 and env.c.delete(f"/api/study/courses/{cid}", headers=other).status_code == 404
    q = env.c.post(f"/api/study/topics/{tids[0]}/quizzes", headers=mate, json={"kind": "mcq"}).json()["id"]
    assert env.c.get(f"/api/study/quizzes/{q}", headers=env.stu).status_code == 404  # a set belongs to whoever asked for it
    env.add_user("lone@x.com"); lone = env.login("lone@x.com"); lc = new(env, lone)
    assert env.c.put(f"/api/study/courses/{lc}", headers=lone, json={"share": "program"}).status_code == 400  # no program, nobody to share with
    assert env.c.delete(f"/api/study/courses/{cid}", headers=env.stu).status_code == 200
    with Session_() as s: assert s.query(StudyTopic).filter_by(course_id=cid).count() == 0 and s.query(StudyQuiz).count() == 0

def test_ai_rules_keys_and_daily_limit(env, monkeypatch):
    setup(env, monkeypatch, key=None); cid = new(env)
    env.c.post(f"/api/study/courses/{cid}/text", headers=env.stu, json={"text": TEXT})
    assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={}).status_code == 503  # no AI key
    assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={"method": "headings"}).status_code == 200  # still possible without AI
    with Session_() as s: s.merge(Setting(k="deepseek_key", v="sk")); s.commit()
    monkeypatch.setattr(main, "STUDY_AI_DAILY", 2)
    for _ in range(2): assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={}).status_code == 200
    assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={}).status_code == 429
    with Session_() as s: assert s.query(StudyAICall).count() == 2

def test_slicing_survives_messy_ai_answers(env):
    assert main.normalise_plan({"units": [{"title": "A", "topics": [{"title": "t", "from": 3}, {"title": "u", "from": "1"}, {"title": "dup", "from": 3}, {"from": "x"}]}]}, 5) == \
        {"units": [{"title": "A", "topics": [{"title": "u", "summary": "", "from": 1, "to": 2}, {"title": "t", "summary": "", "from": 3, "to": 5}]}]}
    assert main.normalise_plan({"units": []}, 3) is None and main.ai_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    assert main.headings_plan(["one two"] * 3)["units"][0]["topics"][0] == {"title": "one two", "summary": "", "from": 1, "to": 3}

def test_headings_slicer_skips_a_lone_title_and_excerpts_are_plain(env):
    paras = ["# Lesson 1", "intro", "## Part A", "a1", "### Detail", "a2", "## Part B", "| x | y |\n|---|---|\n| 1 | 2 |"]
    plan = main.headings_plan(paras)
    assert [u["title"] for u in plan["units"]] == ["Lesson 1", "Part A", "Part B"] and [t["title"] for t in plan["units"][1]["topics"]] == ["Part A", "Detail"]
    assert main.plain_excerpt(["### Detail", "| x | y |\n|---|---|"]) == "Detail x y"
