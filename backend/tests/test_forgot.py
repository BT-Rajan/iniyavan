import datetime as dt, re, main
from main import Session_, User, PasswordReset, LoginFail

class Mailbox(list): pass
def setup(env, monkeypatch, on=True):
    box = Mailbox(); monkeypatch.setattr(main, "send_mail", lambda to, subject, body: box.append((to, subject, body)))
    for k, v in dict(SMTP_HOST="smtp.test", SMTP_FROM="noreply@test", APP_URL="https://learn.test").items():
        monkeypatch.setenv(k, v) if on else monkeypatch.delenv(k, raising=False)
    return box
def forgot(env, email, **kw): return env.c.post("/api/forgot", json={"email": email}, **kw)
def token_from(box): return re.search(r"#reset=([\w-]+)", box[-1][2]).group(1)

def test_off_until_smtp_is_configured(env, monkeypatch):
    setup(env, monkeypatch, on=False)
    assert env.c.get("/api/config").json()["email_reset"] is False and forgot(env, "stu@x.com").status_code == 503
    setup(env, monkeypatch); assert env.c.get("/api/config").json()["email_reset"] is True

def test_same_answer_for_known_and_unknown_and_only_known_gets_mail(env, monkeypatch):
    box = setup(env, monkeypatch)
    a, b = forgot(env, "stu@x.com"), forgot(env, "nobody@x.com"); assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert [m[0] for m in box] == ["stu@x.com"] and box[0][2].count("https://learn.test/#reset=") == 1
    with Session_() as s: assert all(len(r.token_hash) == 64 for r in s.query(PasswordReset)) and token_from(box) not in str([r.token_hash for r in s.query(PasswordReset)])
    with Session_() as s: s.query(User).filter_by(email="fac@x.com").update({"active": False}); s.commit()
    forgot(env, "fac@x.com"); assert len(box) == 1

def test_link_always_uses_app_url_not_the_host_header(env, monkeypatch):
    box = setup(env, monkeypatch); forgot(env, "stu@x.com", headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"})
    assert "evil.example" not in box[0][2] and "https://learn.test/#reset=" in box[0][2]

def test_reset_changes_password_signs_out_old_sessions_and_link_is_single_use(env, monkeypatch):
    box = setup(env, monkeypatch); forgot(env, "stu@x.com"); forgot(env, "stu@x.com"); t2 = token_from(box)
    for _ in range(6): env.c.post("/api/login", json={"email": "stu@x.com", "password": "bad"})  # locked out
    assert env.c.post("/api/reset/check", json={"token": t2}).json() == {"valid": True} and env.c.post("/api/reset/check", json={"token": "nope"}).json() == {"valid": False}
    assert env.c.post("/api/reset", json={"token": t2, "new_password": "short"}).status_code == 400
    assert env.c.post("/api/reset", json={"token": t2, "new_password": "stu@x.com"}).status_code == 400
    r = env.c.post("/api/reset", json={"token": t2, "new_password": "brandnew123"}); assert r.status_code == 200 and r.json()["user"]["must_change"] is False
    assert env.c.get("/api/tree", headers={"Authorization": "Bearer " + r.json()["token"]}).status_code == 200
    assert env.c.get("/api/me", headers=env.stu).status_code == 401  # the old session ended
    assert env.c.post("/api/login", json={"email": "stu@x.com", "password": "brandnew123"}).status_code == 200  # lockout cleared too
    assert env.c.post("/api/reset", json={"token": t2, "new_password": "another1234"}).status_code == 400
    assert env.c.post("/api/reset", json={"token": token_from(box[:1]) if False else "x" * 40, "new_password": "another1234"}).status_code == 400

def test_older_links_die_when_one_is_used(env, monkeypatch):
    box = setup(env, monkeypatch); forgot(env, "stu@x.com"); first = token_from(box); forgot(env, "stu@x.com"); second = token_from(box)
    assert env.c.post("/api/reset", json={"token": second, "new_password": "brandnew123"}).status_code == 200
    assert env.c.post("/api/reset", json={"token": first, "new_password": "brandnew456"}).status_code == 400

def test_expired_link_is_refused(env, monkeypatch):
    box = setup(env, monkeypatch); forgot(env, "stu@x.com"); t = token_from(box)
    with Session_() as s: s.query(PasswordReset).update({"expires_at": dt.datetime.utcnow() - dt.timedelta(minutes=1)}); s.commit()
    assert env.c.post("/api/reset/check", json={"token": t}).json() == {"valid": False} and env.c.post("/api/reset", json={"token": t, "new_password": "brandnew123"}).status_code == 400

def test_rate_limits_per_account_and_per_address(env, monkeypatch):
    box = setup(env, monkeypatch); [forgot(env, "stu@x.com") for _ in range(5)]; assert len(box) == 3  # 3 mails an hour per account, same answer every time
    with Session_() as s: s.query(PasswordReset).delete(); s.commit()
    codes = [forgot(env, f"ghost{i}@x.com").status_code for i in range(22)]; assert codes[:20] == [200] * 20 and codes[20:] == [429, 429]

def test_admin_can_test_the_mailbox(env, monkeypatch):
    box = setup(env, monkeypatch, on=False); assert env.c.post("/api/admin/mail/test", headers=env.admin).json()["ok"] is False
    box = setup(env, monkeypatch); r = env.c.post("/api/admin/mail/test", headers=env.admin).json(); assert r["ok"] is True and box[-1][0] == "admin@x.com"
    assert env.c.get("/api/admin/settings", headers=env.admin).json()["mail_on"] is True and env.c.post("/api/admin/mail/test", headers=env.stu).status_code == 403
