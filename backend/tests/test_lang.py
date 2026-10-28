import main
from main import Session_, User

def test_each_person_picks_a_language_and_ai_answers_follow_it(env):
    assert env.c.get("/api/me", headers=env.stu).json()["lang"] == "en"
    assert env.c.put("/api/me/lang", headers=env.stu, json={"lang": "ar"}).json()["lang"] == "ar"
    assert env.c.get("/api/me", headers=env.stu).json()["lang"] == "ar" and env.c.get("/api/me", headers=env.fac).json()["lang"] == "en"
    assert env.c.put("/api/me/lang", headers=env.stu, json={"lang": "fr"}).status_code == 400
    with Session_() as s:
        u = s.query(User).filter_by(email="stu@x.com").one()
        assert "in Arabic" in main.in_lang(u, "Explain it.") and main.in_lang(u, "Explain it.").startswith("Explain it.")
        u.lang = "ta"; assert "in Tamil" in main.in_lang(u, "P")
        u.lang = None; assert main.in_lang(u, "P") == "P"  # English: the prompt, and so the saved answers, are as before
    assert env.c.put("/api/me/lang", headers=env.stu, json={"lang": "en"}).json()["lang"] == "en"
    with Session_() as s: assert s.query(User).filter_by(email="stu@x.com").one().lang is None

def test_every_daily_limit_message_reaches_tamil_and_arabic():
    """The server says these in English with a number in them; the apps turn them into the reader's language through locales/srv.json."""
    import json, os, re
    here = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "locales")
    shapes = [(re.compile(p.replace("(?<", "(?P<")), k) for p, k in json.load(open(os.path.join(here, "srv.json"), encoding="utf-8"))]
    langs = [json.load(open(os.path.join(here, f"{l}.json"), encoding="utf-8")) for l in ("ta", "ar")]
    class U: self_registered = True
    class V: self_registered = False
    msgs = [f"You have used today's 10 free AI searches.{main.lite_more(U)}", f"You have used today's 10 free AI searches.{main.lite_more(V)}",
            f"You have used today's 20 free minutes of learning with AI.{main.lite_more(U)}", f"You have used today's 20 free minutes of learning with AI.{main.lite_more(V)}",
            f"You have used today's {main.LINE_DAILY} highlight explanations. Your highlight is saved; ask again tomorrow.",
            f"You have used today's {main.DOUBT_DAILY} AI doubts. Try again tomorrow, or reread the passage above.", f"You have used today's {main.PHOTO_DAILY} photo questions. Try again tomorrow.",
            f"You have used today's {main.SEARCH_DAILY} AI searches. Try again tomorrow, or browse your courses.",
            f"You have used today's {main.STUDY_AI_DAILY} AI requests for your own courses. Try again tomorrow.",
            "You have used today's 4 MCQ sets. More from tomorrow.", "Lite includes one MCQ set every 48 hours. Your next set is free in 5 hours."]
    for m in msgs:
        key = next((k for p, k in shapes if p.fullmatch(m)), None)
        assert key and all(key in d for d in langs), m
