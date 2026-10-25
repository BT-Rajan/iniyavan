# Email delivery: a Gmail sender set up in the app (App Password sealed), the site address for links, send health and the email log
import smtplib
import main

class FakeSMTP:  # stands in for smtp.gmail.com; set FakeSMTP.fail to an exception to make sending fail
    sent, logins, fail = [], [], None
    def __init__(self, host, port, timeout=None): self.host, self.port = host, port
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): pass
    def login(self, user, pw):
        if isinstance(FakeSMTP.fail, smtplib.SMTPAuthenticationError): raise FakeSMTP.fail
        FakeSMTP.logins.append((self.host, self.port, user, pw))
    def send_message(self, m):
        if FakeSMTP.fail and not isinstance(FakeSMTP.fail, smtplib.SMTPAuthenticationError): raise FakeSMTP.fail
        FakeSMTP.sent.append(m)

def setup(env, monkeypatch):
    for k in ("SMTP_HOST", "SMTP_FROM", "APP_URL", "SMTP_USER", "SMTP_PASSWORD"): monkeypatch.delenv(k, raising=False)
    FakeSMTP.sent, FakeSMTP.logins, FakeSMTP.fail = [], [], None
    monkeypatch.setattr(main.smtplib, "SMTP", FakeSMTP)

def test_an_admin_sets_up_gmail_in_the_app_and_the_password_is_sealed(env, monkeypatch):
    setup(env, monkeypatch)
    assert env.c.get("/api/config").json()["email_reset"] is False and env.c.put("/api/admin/mail", headers=env.stu, json={"gmail": "x@gmail.com"}).status_code == 403
    r = env.c.put("/api/admin/mail", headers=env.admin, json={"gmail": " Zigora.College@Gmail.com ", "app_password": "abcd efgh​ ijkl mnop", "app_url": "http://169.58.13.213:5252/app/"})
    assert r.status_code == 200, r.text
    st = r.json(); assert st["on"] and st["via"] == "gmail" and st["gmail"] == "zigora.college@gmail.com" and st["gmail_saved"] and st["app_url"] == "http://169.58.13.213:5252"
    assert "abcdefghijklmnop" not in r.text  # the password never comes back
    with main.Session_() as s: raw = main.setting(s, "mail_gmail_pw")
    assert raw and "abcdefghijklmnop" not in raw and main.unseal(raw) == "abcdefghijklmnop"
    assert env.c.get("/api/config").json()["email_reset"] is True
    for bad in ("my-normal-password", "abcd efgh ijkl"):
        e = env.c.put("/api/admin/mail", headers=env.admin, json={"app_password": bad}); assert e.status_code == 400 and "16 letters" in e.json()["detail"]
    assert env.c.put("/api/admin/mail", headers=env.admin, json={"app_url": "learn.college.edu/x"}).status_code == 400

def test_a_reset_goes_out_through_gmail_with_a_button_and_is_logged_without_its_link(env, monkeypatch):
    setup(env, monkeypatch)
    env.c.put("/api/admin/mail", headers=env.admin, json={"gmail": "zigora.college@gmail.com", "app_password": "abcdefghijklmnop", "app_url": "https://learn.test"})
    assert env.c.post("/api/forgot", json={"email": "stu@x.com"}).status_code == 200
    assert FakeSMTP.logins == [("smtp.gmail.com", 587, "zigora.college@gmail.com", "abcdefghijklmnop")]
    m = FakeSMTP.sent[0]; text = m.get_body(("plain",)).get_content(); html = m.get_body(("html",)).get_content()
    assert m["To"] == "stu@x.com" and "zigora.college@gmail.com" in m["From"] and "https://learn.test/app/#reset=" in text and 'href="https://learn.test/app/#reset=' in html
    lg = env.c.get("/api/admin/mail/log", headers=env.admin).json()
    assert lg["total"] == 1 and lg["items"][0]["kind"] == "reset" and lg["items"][0]["ok"] and "reset=" not in str(lg)  # who and when, never the link
    h = env.c.get("/api/admin/mail", headers=env.admin).json()["health"]; assert h["ok_at"] and h["fails_in_a_row"] == 0

def test_a_gmail_login_failure_is_explained_to_the_admin_and_counted(env, monkeypatch):
    setup(env, monkeypatch)
    env.c.put("/api/admin/mail", headers=env.admin, json={"gmail": "z@gmail.com", "app_password": "abcdefghijklmnop", "app_url": "https://learn.test"})
    FakeSMTP.fail = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    r = env.c.post("/api/admin/mail/test", headers=env.admin).json(); assert r["ok"] is False and "App Password" in r["message"] and "not accepted" in r["message"]
    assert env.c.post("/api/forgot", json={"email": "stu@x.com"}).json()["ok"] is True  # the person asking sees the usual answer
    st = env.c.get("/api/admin/mail", headers=env.admin).json(); assert st["health"]["fails_in_a_row"] == 2 and "App Password" in st["health"]["fail_message"]
    fl = env.c.get("/api/admin/mail/log?failed=true", headers=env.admin).json(); assert fl["total"] == 2 and not fl["items"][0]["ok"]
    env.c.put("/api/admin/mail", headers=env.admin, json={"app_password": "ponmlkjihgfedcba"})  # a new password starts clean
    assert env.c.get("/api/admin/mail", headers=env.admin).json()["health"]["fails_in_a_row"] == 0
    FakeSMTP.fail = OSError("no route")
    assert "Could not reach smtp.gmail.com:587" in env.c.post("/api/admin/mail/test", headers=env.admin).json()["message"]

def test_the_env_server_still_works_and_a_saved_gmail_takes_over(env, monkeypatch):
    setup(env, monkeypatch)
    for k, v in dict(SMTP_HOST="smtp.college.test", SMTP_FROM="noreply@college.test", APP_URL="https://env.test").items(): monkeypatch.setenv(k, v)
    st = env.c.get("/api/admin/mail", headers=env.admin).json(); assert st["on"] and st["via"] == "server" and st["app_url"] == "https://env.test"
    assert env.c.post("/api/admin/mail/test", headers=env.admin).json()["ok"] and FakeSMTP.sent[-1]["From"] == "noreply@college.test"
    env.c.put("/api/admin/mail", headers=env.admin, json={"gmail": "z@gmail.com", "app_password": "abcdefghijklmnop"})
    assert env.c.get("/api/admin/mail", headers=env.admin).json()["via"] == "gmail"
    env.c.put("/api/admin/mail", headers=env.admin, json={"remove_gmail": True})
    assert env.c.get("/api/admin/mail", headers=env.admin).json()["via"] == "server"  # back to .env
