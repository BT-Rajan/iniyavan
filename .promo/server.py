# A throwaway Zigora server for the promo (and the Android screen tests): a fresh SQLite database in PROMO_WORK with a program,
# three courses, a student's own course, an MCQ bank, Sign in with Google switched on, demo accounts (password pw123456) and a stand-in AI that answers in the shapes the app asks
# for. Never points at real data or a real AI key.
#   PROMO_WORK=/tmp/w PROMO_PORT=4400 python .promo/server.py
import json, os, sys
WORK = os.environ.get("PROMO_WORK") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
os.makedirs(WORK, exist_ok=True)
db = os.path.join(WORK, "promo.db")
if os.path.exists(db): os.remove(db)
os.environ.update(DATABASE_URL=f"sqlite:///{db}", JWT_SECRET="promo-" + "x" * 40, UPLOAD_DIR=os.path.join(WORK, "uploads"), DEEPSEEK_API_KEY="stand-in",
                  PBKDF2_ITER="1000", ANDROID_REPO="", APP_NAME="Zigora")  # no GitHub look-up: no "new version" card in the shots
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import main, uvicorn
from main import Session_, User, Program, Semester, Course, Unit, Topic, Quiz, Question, hp

NOTES = """## Hardness of water

Water that does not easily form lather with soap is **hard water**. It carries dissolved salts of **calcium** and **magnesium**.

### Types

| Type | Caused by | Removed by |
|---|---|---|
| Temporary | Bicarbonates of Ca and Mg | Boiling |
| Permanent | Chlorides and sulphates of Ca and Mg | Ion exchange, lime-soda |

On boiling, calcium bicarbonate breaks down: Ca(HCO₃)₂ → CaCO₃↓ + H₂O + CO₂.

### Why it matters
- Soap is wasted: it forms scum instead of lather.
- Boilers scale up, which wastes fuel and can make tubes burst.
"""

main.upgrade_schema()
with Session_() as s:
    s.add(User(name="admin", email="admin@mail.com", pw=hp("pw123456"), role="admin")); s.flush()
    p = Program(name="B.E. Civil Engineering", pattern="semester", created_by=1); s.add(p); s.flush()
    sem = Semester(name="Semester 1", program_id=p.id, semester_no=1, created_by=1); s.add(sem); s.flush()
    s.add(User(name="Meena Kumar", email="stu@mail.com", pw=hp("pw123456"), role="student", program_id=p.id, semester=1))
    s.add(User(name="Ravi Shankar", email="ravi@gmail.com", pw=hp("pw123456"), role="student", self_registered=True, program_id=p.id, semester=1,
               institution="Anna University", id_number="AU2291", phone="+91 98400 12345"))
    s.add(User(name="Priya Raman", email="teacher@mail.com", pw=hp("pw123456"), role="faculty"))
    for cn, units in [("Engineering Chemistry", [("Water Technology", ["Hardness of Water", "Softening Methods", "Boiler Troubles", "Desalination"]),
                                                ("Electrochemistry", ["Electrode Potential", "Batteries"])]),
                      ("Engineering Mathematics I", [("Matrices", ["Eigenvalues", "Cayley-Hamilton Theorem"])]),
                      ("Communicative English", [("Listening and Speaking", ["Introducing Yourself"])])]:
        c = Course(name=cn, program_id=p.id, semester_id=sem.id, created_by=1); s.add(c); s.flush()
        for ui, (un, topics) in enumerate(units):
            u = Unit(name=un, course_id=c.id, position=ui, created_by=1); s.add(u); s.flush()
            for ti, t in enumerate(topics):
                s.add(Topic(title=t, course_id=c.id, unit_id=u.id, content=NOTES if t == "Hardness of Water" else f"## {t}\n\nNotes for {t}.", published=True, created_by=1, position=ti))
            if un == "Water Technology":
                q = Quiz(unit_id=u.id, course_id=c.id, title="Water Technology quiz", pass_percent=50, published=True, reveal=True); s.add(q); s.flush()
                s.add(Question(quiz_id=q.id, pos=0, text="Which salts cause temporary hardness?", options=json.dumps(["Chlorides", "Bicarbonates", "Sulphates", "Nitrates"]), correct=1,
                               explanation="Bicarbonates break down on boiling."))
                s.add(Question(quiz_id=q.id, pos=1, text="What does boiling hard water leave in a kettle?", options=json.dumps(["Sodium chloride", "Calcium carbonate", "Magnesium sulphate"]),
                               correct=1, explanation="Calcium carbonate barely dissolves."))
    # MCQ practice: a small published bank on Hardness of Water (option texts are unique, so the capture can tap them by name)
    hw = s.query(Topic).filter_by(title="Hardness of Water").one()
    hw.diagram, hw.diagram_note = True, "Temporary and permanent hardness, and what boiling does to each"  # a diagram for students on Pro
    for q, o, k in [("Water that won't lather easily with soap is", ["Hard water", "Soft water", "Distilled water", "Rain water"], 0),
                    ("Temporary hardness goes away on", ["Freezing", "Heating to a boil", "Filtering", "Stirring"], 1),
                    ("Permanent hardness comes from", ["Bicarbonates", "Chlorides and sulphates", "Dissolved oxygen", "Sodium salts"], 1),
                    ("Scale inside a boiler", ["Saves fuel", "Wastes fuel", "Softens the water", "Adds oxygen"], 1),
                    ("One cause of hard water is", ["Calcium salts", "Plastic", "Sand", "Air"], 0)]:
        s.add(main.McqItem(topic_id=hw.id, course_id=hw.course_id, text=q, options=json.dumps(o), correct=k, explanation="From the notes on hardness of water.",
                           difficulty="easy", keywords="hardness", source="teacher", status="published", version=1, sig=main.q_sig(q + "|", o, k)))
    s.merge(main.Setting(k="google_client_id", v="1234567890-promo.apps.googleusercontent.com"))  # the sign-in screen offers Google (its sheet never opens here)
    meena = s.query(User).filter_by(email="stu@mail.com").one()
    sc = main.StudyCourse(owner_id=meena.id, title="Thermodynamics notes", status="ready"); s.add(sc); s.flush()
    su = main.StudyUnit(course_id=sc.id, title="Laws of thermodynamics", position=0); s.add(su); s.flush()
    for ti, (t, body) in enumerate([("The zeroth law", "Two bodies each in equilibrium with a third are in equilibrium with each other."),
                                    ("The first law", "Energy is conserved: dU = dQ - dW.")]):
        s.add(main.StudyTopic(unit_id=su.id, course_id=sc.id, title=t, summary="", content=body, position=ti))
    s.commit()

# the stand-in AI: each kind of request gets an answer in the shape the app asks for
R = {
    "highlighted passage": {"text": "It says hardness comes from calcium and magnesium salts dissolved in the water. *Temporary* means boiling can remove it; *permanent* means it stays after boiling."},
    "tests understanding": {"question": "A sample still forms scum with soap after boiling. What kind of hardness does it have?", "answer": "Permanent hardness: boiling removed the bicarbonates, so what is left must be chlorides or sulphates."},
    "plainest": {"text": "Think of hard water as water carrying tiny bits of chalk. Boiling makes some of that chalk drop out, like sugar that will not stay dissolved. The rest stays hidden in the water.", "hook": "Which kind drops out: temporary or permanent?"},
    "skeleton": {"points": ["Define hardness of water (1 line).", "Causes: list the Ca and Mg salts.", "Types: temporary vs permanent, as a small table.", "Equation for removing temporary hardness by boiling.",
                            "Disadvantages in daily life and industry.", "Units: ppm and mg/L."], "marks": "2 for definition and types, 3 for equation, 3 for effects"},
    "reason": {"text": "On heating, calcium bicarbonate breaks down: Ca(HCO₃)₂ → CaCO₃↓ + H₂O + CO₂. Calcium carbonate barely dissolves, so it settles out and the hardness goes with it. Calcium chloride has nothing that heat can break off, so it stays dissolved.",
               "hook": "So what is the white crust inside a kettle?"},
    "concrete": {"text": "A boiler running on hard water builds up scale. Just 1 mm of scale can raise fuel use by about 5%, because scale conducts heat poorly. That is why power plants soften water before it reaches the boiler.",
                 "hook": "Why can scale make a boiler tube burst?"},
    "typical short exam": {"question": "Distinguish between temporary and permanent hardness. (2 marks)", "answer": "- **Temporary:** caused by bicarbonates of Ca and Mg; removed by boiling.\n- **Permanent:** caused by chlorides and sulphates of Ca and Mg; not removed by boiling.",
                           "tip": "Name the salts and the removal method for each."},
    "points": {"points": ["Hard water carries dissolved calcium and magnesium salts.", "Temporary hardness (bicarbonates) goes on boiling; permanent hardness (chlorides, sulphates) doesn't.",
                          "It wastes soap and scales boilers, so industry treats it."],
               "hook": "Why would boiling remove one kind of hardness and not the other?", "hook_answer": "Heat breaks bicarbonates into carbonates that don't dissolve and settle out; chlorides and sulphates stay dissolved."},
}
# a topic's diagram (Pro): the kind of page the AI draws, an inline SVG with parts to tap and a step-through
DIAGRAM = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;font:16px system-ui,sans-serif;color:#1e1626;background:#fff}h1{font-size:20px;margin:14px 16px 2px}p{margin:0 16px 8px;color:#655b6e}
svg{width:100%;height:auto;max-height:70vh}.part{cursor:pointer}.part:hover rect,.part.on rect{stroke:#722f99;stroke-width:4}
#info{margin:8px 16px;padding:12px 14px;border-radius:12px;background:#f3eef6;min-height:48px}.steps{display:flex;gap:8px;margin:8px 16px}
button{font:inherit;padding:10px 14px;border-radius:999px;border:1px solid #c49be0;background:#fff;color:#722f99}button.on{background:#722f99;color:#fff}</style></head><body>
<h1>Hard water: two kinds</h1><p>Tap a box, or step through what boiling does.</p>
<svg viewBox="0 0 360 260" role="img" aria-label="Hard water splits into temporary and permanent hardness">
<g class="part" data-i="0"><rect x="110" y="10" width="140" height="50" rx="12" fill="#fee7c8"/><text x="180" y="41" text-anchor="middle" font-size="16" font-weight="700">Hard water</text></g>
<path d="M150 60 L80 110 M210 60 L280 110" stroke="#722f99" stroke-width="3" fill="none"/>
<g class="part" data-i="1"><rect x="10" y="110" width="150" height="60" rx="12" fill="#e8f5ee"/><text x="85" y="135" text-anchor="middle" font-size="15" font-weight="700">Temporary</text><text x="85" y="156" text-anchor="middle" font-size="13">Ca, Mg bicarbonates</text></g>
<g class="part" data-i="2"><rect x="200" y="110" width="150" height="60" rx="12" fill="#ffe1e1"/><text x="275" y="135" text-anchor="middle" font-size="15" font-weight="700">Permanent</text><text x="275" y="156" text-anchor="middle" font-size="13">chlorides, sulphates</text></g>
<g id="boil" opacity="0.25"><path d="M85 170 L85 205" stroke="#2e7d5b" stroke-width="3"/><text x="85" y="225" text-anchor="middle" font-size="14" fill="#2e7d5b">boiling removes it</text>
<path d="M275 170 L275 205" stroke="#c0392b" stroke-width="3"/><text x="275" y="225" text-anchor="middle" font-size="14" fill="#c0392b">boiling leaves it</text></g></svg>
<div class="steps"><button data-s="0" class="on">1 · The water</button><button data-s="1">2 · Boil it</button></div><div id="info">Hard water carries dissolved calcium and magnesium salts.</div>
<script>var I=["Hard water carries dissolved calcium and magnesium salts, so soap forms scum instead of lather.","Temporary hardness: bicarbonates break down on boiling, Ca(HCO3)2 -> CaCO3 + H2O + CO2, and the hardness settles out.","Permanent hardness: chlorides and sulphates stay dissolved after boiling; it needs ion exchange or the lime-soda process."]
var info=document.getElementById("info");document.querySelectorAll(".part").forEach(function(g){g.addEventListener("click",function(){document.querySelectorAll(".part").forEach(function(x){x.classList.remove("on")});g.classList.add("on");info.textContent=I[g.dataset.i]})})
document.querySelectorAll("[data-s]").forEach(function(b){b.addEventListener("click",function(){document.querySelectorAll("[data-s]").forEach(function(x){x.classList.toggle("on",x===b)});document.getElementById("boil").setAttribute("opacity",b.dataset.s==="1"?"1":"0.25");info.textContent=b.dataset.s==="1"?"Boil it: the temporary side loses its hardness, the permanent side keeps it.":I[0]})})</script></body></html>"""

async def stand_in(key, messages, max_tokens=None, timeout=45):  # in place of main.chat: the same messages in, (text, tokens) out
    sysmsg = messages[0]["content"]
    if "Reply with the HTML only" in sysmsg: return DIAGRAM, 900
    for k, v in R.items():
        if k in sysmsg: return json.dumps(v), 50
    return ("**Why it matters:** hard water wastes soap and damages boilers.\n\n1. Calcium and magnesium salts dissolve from rocks.\n2. Bicarbonates cause *temporary* hardness, which boiling removes.\n"
            "3. Chlorides and sulphates cause *permanent* hardness.\n\n*Example:* a kettle's white crust is calcium carbonate from temporary hardness."), 80
main.chat = stand_in

uvicorn.run(main.app, host="127.0.0.1", port=int(os.environ.get("PROMO_PORT", "4400")), log_level="warning")
