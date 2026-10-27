"""A student's own material for an official course: filed under the university's syllabus topics, private to the student."""
import json, re
import main
from main import Session_, User, Topic, TopicNote, CourseMaterial, Progress, StudyAICall
from tests.test_access import enrol, ids
from tests.test_study import FakeAI, pdf

SYLLABUS = ("program,semester,course,unit,topic\nMech,Semester 1,Chem,Water,Hardness of water\n,,,,Softening methods\n,,,Corrosion,Rusting\n"
            ",,,,Galvanising\nMech,Semester 1,Workshop,Tools,Fitting\nCivil,Semester 1,Maths,Limits,Limits\n")  # titles only: the university's framework, no content
NOTES = """# Introduction

These are my class notes for chemistry.

# 1. Hardness of Water

Hard water has calcium and magnesium salts.

## Temporary hardness

Boiling removes temporary hardness.

# Softening Methods

Lime-soda and ion exchange soften water.

# Rusting

Iron rusts in moist air.

# Something else entirely

A page about cricket."""

class MatchAI(FakeAI):  # also answers the matching prompt, by topic titles in the listing
    calls = []
    @classmethod
    async def __call__(cls, key, model, messages, max_tokens=None, timeout=45):
        system, msg = messages[0]["content"], messages[1]["content"]
        if system.startswith("You file a student's own"):
            cls.calls.append(msg); ref = {t: r for r, t in re.findall(r"^(T\d+): (.+?) \(", msg, re.M)}
            return json.dumps({"sections": [{"from": 1, "to": 2, "topic": None}, {"from": 3, "to": 6, "topic": ref["Hardness of water"]},
                                            {"from": 7, "to": 8, "topic": ref["Softening methods"]}, {"from": 9, "to": 10, "topic": "T99"},
                                            {"from": 11, "to": 12, "topic": None}]}), 10
        return await FakeAI.__call__(key, model, messages, max_tokens, timeout)

def setup(env, monkeypatch):
    monkeypatch.setattr(main, "deepseek", MatchAI()); MatchAI.calls = []; FakeAI.calls = []
    with Session_() as s: s.merge(main.Setting(k="deepseek_key", v="sk-test")); s.commit()
    env.csv(SYLLABUS); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1)
    with Session_() as s: i["t"] = {t.title: t.id for t in s.query(Topic)}
    i["chem"] = i["course"]["Chem"]; return i
def url(i, tail=""): return f"/api/courses/{i['chem']}/my-material" + tail
def filed(view): return [(x["heading"], next((t["title"] for un in view["syllabus"] for t in un["topics"] if t["id"] == x["topic_id"]), None)) for x in view["sections"]]
def note(email, tid):
    with Session_() as s:
        n = s.query(TopicNote).join(User, User.id == TopicNote.user_id).filter(User.email == email, TopicNote.topic_id == tid).first(); return n.content if n else None

def test_headings_file_material_under_the_syllabus(env, monkeypatch):
    i = setup(env, monkeypatch)
    v = env.c.get(url(i), headers=env.stu).json()
    assert [(u["name"], [t["title"] for t in u["topics"]]) for u in v["syllabus"]] == [("Water", ["Hardness of water", "Softening methods"]), ("Corrosion", ["Rusting", "Galvanising"])]
    assert env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}).status_code == 200
    v = env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}).json()
    assert filed(v) == [("Introduction", None), ("1. Hardness of Water", "Hardness of water"), ("Softening Methods", "Softening methods"), ("Rusting", "Rusting"), ("Something else entirely", None)]
    assert (v["topics"], v["covered"], v["with_notes"]) == (4, 3, 0)  # the sub-heading stayed with its topic; nothing saved yet
    assert not MatchAI.calls  # no AI used
    v = env.c.post(url(i, "/save"), headers=env.stu).json(); assert v["with_notes"] == 3 and v["saved_at"]
    assert note("stu@x.com", i["t"]["Hardness of water"]).startswith("# 1. Hardness of Water") and "Boiling removes" in note("stu@x.com", i["t"]["Hardness of water"])
    assert note("stu@x.com", i["t"]["Galvanising"]) is None and "cricket" not in json.dumps([note("stu@x.com", t) for t in i["t"].values()])
    tp = env.c.get(f"/api/topics/{i['t']['Rusting']}", headers=env.stu).json(); assert tp["my_notes"] == "# Rusting\n\nIron rusts in moist air."
    assert tp["content"] in (None, "")  # the official topic itself stays as the university set it

def test_ai_matching_and_the_students_corrections(env, monkeypatch):
    i = setup(env, monkeypatch); env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES})
    v = env.c.post(url(i, "/match"), headers=env.stu, json={"method": "ai"}).json()
    assert "Hardness of water (Water)" in MatchAI.calls[0] and "Fitting" not in MatchAI.calls[0]  # only this course's syllabus is sent
    assert filed(v) == [("Introduction", None), ("1. Hardness of Water", "Hardness of water"), ("Softening Methods", "Softening methods"), ("Rusting", None)]  # unknown T99 -> none; neighbours merged
    with Session_() as s: assert s.query(StudyAICall).filter_by(kind="match").count() == 1  # counts toward the daily AI limit
    secs = v["sections"]; secs[3]["topic_id"] = i["t"]["Rusting"]  # the student files the last section themselves
    v = env.c.put(url(i, "/sections"), headers=env.stu, json={"sections": secs}).json(); assert ("Rusting", "Rusting") in filed(v)
    bad = [dict(secs[0], to=secs[1]["to"])] + secs[1:]
    assert env.c.put(url(i, "/sections"), headers=env.stu, json={"sections": bad}).status_code == 400                     # overlap
    assert env.c.put(url(i, "/sections"), headers=env.stu, json={"sections": [dict(secs[0], topic_id=i["t"]["Fitting"])]}).status_code == 400  # another course's topic
    full = env.c.get(url(i, f"/preview?start={secs[1]['from']}&end={secs[1]['to']}"), headers=env.stu).json()["content"]; assert "Boiling removes" in full

def test_saving_again_rebuilds_notes_and_removing_keeps_progress(env, monkeypatch):
    i = setup(env, monkeypatch); h = i["t"]["Hardness of water"]
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    env.c.post(f"/api/topics/{h}/read", headers=env.stu); env.c.put(f"/api/topics/{h}/complete", headers=env.stu)
    secs = env.c.get(url(i), headers=env.stu).json()["sections"]
    for x in secs: x["topic_id"] = None
    secs[3]["topic_id"] = i["t"]["Galvanising"]
    env.c.put(url(i, "/sections"), headers=env.stu, json={"sections": secs}); v = env.c.post(url(i, "/save"), headers=env.stu).json()
    assert v["with_notes"] == 1 and note("stu@x.com", h) is None and note("stu@x.com", i["t"]["Galvanising"]).startswith("# Rusting")
    assert env.c.delete(url(i), headers=env.stu).status_code == 200
    assert note("stu@x.com", i["t"]["Galvanising"]) is None and env.c.get(f"/api/topics/{h}", headers=env.stu).json()["status"] == "completed"
    with Session_() as s: assert s.query(CourseMaterial).count() == 0 and s.query(Progress).count() == 1

def test_pdf_and_files_list(env, monkeypatch):
    i = setup(env, monkeypatch)
    r = env.c.post(url(i, "/files?name=chem.pdf"), headers={**env.stu, "Content-Type": "application/octet-stream"}, content=pdf(["1. Hardness of water", "Hard water has calcium salts.", "Rusting", "Iron rusts in moist air."]))
    assert r.status_code == 200 and r.json()["kind"] == "pdf"
    v = env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}).json()
    assert [b for _, b in filed(v)] == ["Hardness of water", "Rusting"]  # "Rusting" lost its heading in the PDF and is still found by its title
    assert "Iron rusts" in v["sections"][1]["excerpt"]
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": "Extra page"}); v = env.c.get(url(i), headers=env.stu).json()
    assert [x["name"] for x in v["sources"]] == ["chem.pdf", "Pasted text"] and v["sections"] == []  # new material means matching again
    v = env.c.delete(url(i, "/sources/1"), headers=env.stu).json(); assert [x["name"] for x in v["sources"]] == ["chem.pdf"]

def test_private_and_limited_to_students_of_the_course(env, monkeypatch):
    i = setup(env, monkeypatch); env.add_user("stu2@x.com", program=i["prog"]["Mech"], semester=1); s2 = env.login("stu2@x.com")
    env.add_user("civ@x.com", program=i["prog"]["Civil"], semester=1); civ = env.login("civ@x.com")
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    h = i["t"]["Hardness of water"]
    assert env.c.get(f"/api/topics/{h}", headers=s2).json()["my_notes"] is None and env.c.get(url(i), headers=s2).json()["sections"] == []  # classmates see nothing of it
    assert env.c.get(f"/api/topics/{h}", headers=env.admin).json()["my_notes"] is None
    for who in (env.fac, env.admin): assert env.c.post(url(i, "/text"), headers=who, json={"text": "x"}).status_code == 403
    assert env.c.post(url(i, "/text"), headers=civ, json={"text": "x"}).status_code == 403  # another program's course
    enrol("stu@x.com", None, None); assert env.c.get(url(i), headers=env.stu).status_code == 403
    assert env.c.get("/api/courses/99999/my-material", headers=s2).status_code == 404

def test_drafts_and_archived_topics_are_not_in_the_syllabus_and_deletes_clean_up(env, monkeypatch):
    i = setup(env, monkeypatch); g = i["t"]["Galvanising"]
    with Session_() as s: s.get(Topic, g).published = False; s.commit()
    names = [t["title"] for u in env.c.get(url(i), headers=env.stu).json()["syllabus"] for t in u["topics"]]; assert "Galvanising" not in names and len(names) == 3
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    assert env.c.delete(f"/api/topics/{i['t']['Rusting']}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.query(TopicNote).filter_by(topic_id=i["t"]["Rusting"]).count() == 0
    assert env.c.delete(f"/api/courses/{i['chem']}", headers=env.admin).status_code == 200
    with Session_() as s: assert s.query(TopicNote).count() == 0 and s.query(CourseMaterial).count() == 0

def test_checks_on_a_topic_also_use_the_students_notes(env, monkeypatch):
    i = setup(env, monkeypatch); h = i["t"]["Hardness of water"]
    assert env.c.post(f"/api/topics/{h}/practice", headers=env.stu, json={"kind": "mcq"}).status_code == 400  # nothing to ask about yet
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    r = env.c.post(f"/api/topics/{h}/practice", headers=env.stu, json={"kind": "mcq"}); assert r.status_code == 200
    assert any("Boiling removes temporary hardness" in m for _, m in FakeAI.calls)

def test_explain_uses_the_students_own_notes_privately(env, monkeypatch):
    i = setup(env, monkeypatch); h = i["t"]["Hardness of water"]; env.add_user("stu2@x.com", program=i["prog"]["Mech"], semester=1); s2 = env.login("stu2@x.com")
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    r = env.c.get(f"/api/topics/{h}/ai/explain", headers=env.stu).json(); assert r["own_notes"] and not r["cached"]
    assert "Boiling removes temporary hardness" in FakeAI.calls[-1][1]  # the student's notes went with the question
    with Session_() as s: assert s.query(main.AICache).count() == 0 and s.query(StudyAICall).filter_by(kind="t_explain").count() == 1  # never shared; counts toward their daily limit (kind is short enough for its 10-character column)
    n = len(FakeAI.calls); again = env.c.get(f"/api/topics/{h}/ai/explain", headers=env.stu).json()  # the second look shows the kept copy: nothing is sent, nothing is counted
    assert again["own_notes"] and again["cached"] and again["text"] == r["text"] and len(FakeAI.calls) == n
    with Session_() as s: assert s.query(StudyAICall).filter_by(kind="t_explain").count() == 1 and s.query(main.PrivateAnswer).count() == 1
    r = env.c.get(f"/api/topics/{h}/ai/explain", headers=s2).json(); assert "own_notes" not in r and "Boiling removes" not in FakeAI.calls[-1][1]  # a classmate without notes gets the shared answer
    with Session_() as s: assert s.query(main.AICache).count() == 1

def test_a_topic_moved_to_another_course_leaves_the_old_filing_and_keeps_its_note(env, monkeypatch):
    i = setup(env, monkeypatch); r = i["t"]["Rusting"]
    env.c.post(url(i, "/text"), headers=env.stu, json={"text": NOTES}); env.c.post(url(i, "/match"), headers=env.stu, json={"method": "headings"}); env.c.post(url(i, "/save"), headers=env.stu)
    tools = env.c.get(f"/api/topics/{i['t']['Fitting']}", headers=env.admin).json()["unit_id"]
    assert env.c.put(f"/api/topics/{r}", headers=env.admin, json={"title": "Rusting", "unit_id": tools}).status_code == 200  # the admin moves it to Workshop
    v = env.c.get(url(i), headers=env.stu).json()
    assert r not in [x["topic_id"] for x in v["sections"]] and (v["topics"], v["covered"]) == (3, 2)  # it is no longer this course's topic
    secs = v["sections"]; secs[0]["topic_id"] = i["t"]["Galvanising"]
    assert env.c.put(url(i, "/sections"), headers=env.stu, json={"sections": secs}).status_code == 200  # changing a part and saving again still works
    assert env.c.post(url(i, "/save"), headers=env.stu).status_code == 200
    assert env.c.get(f"/api/topics/{r}", headers=env.stu).json()["my_notes"].startswith("# Rusting")  # the note stays with its topic in the new course
