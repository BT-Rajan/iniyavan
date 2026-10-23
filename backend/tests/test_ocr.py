"""Scanned PDFs: pages without text are read with text recognition in the background, for course material and student-built courses."""
import io, json, pytest
import main
from main import Session_, CourseMaterial, StudyCourse
from tests.test_access import enrol, ids
from tests.test_material import SYLLABUS
from tests.test_study import pdf

def scanned(pages):  # an image-only PDF, like a scanner makes: one picture per page and no text layer
    from PIL import Image, ImageDraw, ImageFont
    ims = []
    for lines in pages:
        im = Image.new("L", (1240, 1754), 255); d = ImageDraw.Draw(im); f = ImageFont.load_default(size=40)
        for k, l in enumerate(lines): d.text((100, 120 + k * 80), l, fill=0, font=f)
        ims.append(im)
    b = io.BytesIO(); ims[0].save(b, "PDF", save_all=True, append_images=ims[1:], resolution=150); return b.getvalue()
PAGES = [["Hardness of water", "Hard water has calcium salts."], ["Rusting", "Iron rusts in moist air."]]
FAKE = ["Hardness of water\nHard water has calcium salts.", "Rusting\nIron rusts in moist air."]

@pytest.fixture
def ocr(monkeypatch):
    """Text recognition stands in by page order; jobs run at once unless a test holds them."""
    st = {"calls": 0, "held": None, "fail": False}
    def page(p):
        st["calls"] += 1
        if st["fail"]: raise RuntimeError("tesseract crashed")
        return FAKE[(st["calls"] - 1) % len(FAKE)]
    def spawn(fn, *args):
        if st["held"] is not None: st["held"].append((fn, args))
        else: fn(*args)
    monkeypatch.setattr(main, "ocr_ready", lambda: True); monkeypatch.setattr(main, "ocr_page", page); monkeypatch.setattr(main, "spawn", spawn)
    return st
def setup(env):
    env.csv(SYLLABUS); i = ids(); enrol("stu@x.com", i["prog"]["Mech"], 1); return f"/api/courses/{i['course']['Chem']}/my-material"
def up(env, url, name, data): return env.c.post(f"{url}/files?name={name}", headers={**env.stu, "Content-Type": "application/octet-stream"}, content=data)
def paras_of(model):
    with Session_() as s: return json.loads(s.query(model).one().paras)

def test_a_scanned_pdf_is_read_and_filed_under_the_syllabus(env, ocr):
    url = setup(env); r = up(env, url, "scan.pdf", scanned(PAGES))
    assert r.status_code == 200 and (r.json()["kind"], r.json()["status"], r.json()["pages"]) == ("scan", "reading", 2)
    v = env.c.get(url, headers=env.stu).json(); src = v["sources"][0]
    assert (src["status"], src["done"]) == ("done", 2) and src["paras"] >= 2 and src["words"] > 5 and v["reading"] is False and ocr["calls"] == 2
    v = env.c.post(f"{url}/match", headers=env.stu, json={"method": "headings"}).json()
    titles = {t["id"]: t["title"] for un in v["syllabus"] for t in un["topics"]}
    assert [titles.get(x["topic_id"]) for x in v["sections"]] == ["Hardness of water", "Rusting"]

def test_only_pages_without_text_are_recognised(env, ocr):
    url = setup(env)
    text_pages = pdf(["Softening methods", "Lime soda softens water in a big tank today."])
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for part in (text_pages, scanned([PAGES[1]])):
        for pg in PdfReader(io.BytesIO(part)).pages: w.add_page(pg)
    b = io.BytesIO(); w.write(b)
    assert up(env, url, "mixed.pdf", b.getvalue()).json()["status"] == "reading"
    assert ocr["calls"] == 1  # the text page kept its own text
    got = " ".join(paras_of(CourseMaterial)); assert "Lime soda softens water" in got and "Hard water has calcium" in got  # page 2 came from the recogniser

def test_text_goes_where_the_file_sits_and_removal_stops_reading(env, ocr):
    url = setup(env); ocr["held"] = []
    env.c.post(f"{url}/text", headers=env.stu, json={"text": "First file."})
    up(env, url, "scan.pdf", scanned(PAGES)); env.c.post(f"{url}/text", headers=env.stu, json={"text": "Third file."})
    v = env.c.get(url, headers=env.stu).json(); assert v["reading"] is True and v["sources"][1]["status"] == "reading"
    assert env.c.post(f"{url}/match", headers=env.stu, json={"method": "headings"}).status_code == 409  # waits for the pages
    fn, args = ocr["held"].pop(); fn(*args)
    ps = paras_of(CourseMaterial); assert ps[0] == "First file." and ps[-1] == "Third file." and any("Iron rusts" in p for p in ps[1:-1])
    up(env, url, "again.pdf", scanned(PAGES)); n = len(paras_of(CourseMaterial))
    assert env.c.delete(f"{url}/sources/3", headers=env.stu).status_code == 200
    fn, args = ocr["held"].pop(); fn(*args)  # the job finds its file gone and adds nothing
    assert len(paras_of(CourseMaterial)) == n and [x["name"] for x in env.c.get(url, headers=env.stu).json()["sources"]] == ["Pasted text", "scan.pdf", "Pasted text"]

def test_failures_restarts_and_missing_tesseract_are_reported(env, ocr, monkeypatch):
    url = setup(env); ocr["fail"] = True
    up(env, url, "bad.pdf", scanned(PAGES)); src = env.c.get(url, headers=env.stu).json()["sources"][0]
    assert src["status"] == "failed" and "could not be read" in src["error"] and paras_of(CourseMaterial) == []
    ocr["fail"] = False; ocr["held"] = []; up(env, url, "cut.pdf", scanned(PAGES)); main.OCR_JOBS.clear()  # as if the server restarted mid-way
    src = env.c.get(url, headers=env.stu).json()["sources"][1]; assert src["status"] == "failed" and "restarted" in src["error"]
    assert env.c.get(url, headers=env.stu).json()["reading"] is False
    monkeypatch.setattr(main, "ocr_ready", lambda: False)
    r = up(env, url, "scan.pdf", scanned(PAGES)); assert r.status_code == 400 and "text recognition isn't set up" in r.json()["detail"]
    assert up(env, url, "text.pdf", pdf(["Rusting", "Iron rusts in moist air and water, slowly."])).json()["kind"] == "pdf"  # ordinary PDFs never need it

def test_student_built_courses_read_scans_too(env, ocr):
    cid = env.c.post("/api/study/courses", headers=env.stu, json={"title": "My chemistry"}).json()["id"]
    r = env.c.post(f"/api/study/courses/{cid}/files?name=scan.pdf", headers={**env.stu, "Content-Type": "application/octet-stream"}, content=scanned(PAGES))
    assert r.json()["status"] == "reading"
    c = env.c.get(f"/api/study/courses/{cid}", headers=env.stu).json(); assert c["sources"][0]["status"] == "done" and c["paragraphs"] >= 2 and c["reading"] is False
    assert env.c.post(f"/api/study/courses/{cid}/slice", headers=env.stu, json={"method": "headings"}).status_code == 200
    with Session_() as s: assert "Iron rusts" in s.get(StudyCourse, cid).paras

@pytest.mark.skipif(not main.ocr_ready(), reason="Tesseract is not installed here")
def test_real_text_recognition(env, monkeypatch):
    monkeypatch.setattr(main, "spawn", lambda fn, *a: fn(*a))  # the real recogniser, run at once
    url = setup(env); assert up(env, url, "scan.pdf", scanned(PAGES)).status_code == 200
    got = " ".join(paras_of(CourseMaterial)); assert "Hardness of water" in got and "rusts in moist air" in got  # small print can read I as l
