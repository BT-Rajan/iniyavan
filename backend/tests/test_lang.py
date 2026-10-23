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
