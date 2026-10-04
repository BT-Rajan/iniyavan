import datetime as dt, re
import pytest, main
from main import Session_, User, PendingRegistration
from tests.test_ai import FakeClient

GOOD = dict(name="Asha  Devi", institution="Karkathar College", id_number="21CS001", email="Asha@College.edu", phone="+91 98765 43210", password="longenough1")

@pytest.fixture
def reg(env, monkeypatch):
    for k, v in (("SMTP_HOST", "smtp.test"), ("SMTP_FROM", "no@test"), ("APP_URL", "https://app.test")): monkeypatch.setenv(k, v)
    sent = []; monkeypatch.setattr(main, "send_mail", lambda to, subj, body: sent.append((to, subj, body)))
    env.c.put("/api/admin/settings", headers=env.admin, json={"self_registration": True}); env.sent = sent
    env.start = lambda **o: env.c.post("/api/register/start", json={**GOOD, **o})
    env.code = lambda: re.search(r"\b(\d{6})\b", sent[-1][2]).group(1)
    return env

def wait(email, **kw):  # skip the resend cooldown
    with Session_() as s:
        p = s.query(PendingRegistration).filter_by(email=email).first(); p.last_sent_at = dt.datetime.utcnow() - dt.timedelta(minutes=5)
        for k, v in kw.items(): setattr(p, k, v)
        s.commit()

def test_closed_by_default_and_needs_mail(env, monkeypatch):
    for k in ("SMTP_HOST", "SMTP_FROM", "APP_URL"): monkeypatch.delenv(k, raising=False)
    assert env.c.get("/api/register/status").json()["open"] is False and env.c.post("/api/register/start", json=GOOD).status_code == 403
    env.c.put("/api/admin/settings", headers=env.admin, json={"self_registration": True})
    assert env.c.post("/api/register/start", json=GOOD).status_code == 403 and env.c.get("/api/config").json()["self_registration"] is False  # on, but no SMTP
    monkeypatch.setenv("SMTP_HOST", "h"); monkeypatch.setenv("SMTP_FROM", "f@x"); monkeypatch.setenv("APP_URL", "https://a")
    assert env.c.get("/api/register/status").json()["open"] is True
    assert env.c.put("/api/admin/settings", headers=env.stu, json={"self_registration": True}).status_code == 403

def test_validation(reg):
    for bad in (dict(name="A"), dict(institution=""), dict(id_number="!!"), dict(email="nope"), dict(phone="12"), dict(phone="abc12345"), dict(password="short"), dict(password="asha@college.edu")):
        assert reg.start(**bad).status_code == 400, bad
    assert reg.sent == []

def test_register_with_otp_creates_a_student_and_signs_in(reg):
    r = reg.start(); assert r.status_code == 200 and r.json()["email"] == "asha@college.edu" and reg.sent[-1][0] == "asha@college.edu"
    with Session_() as s: assert s.query(User).filter_by(email="asha@college.edu").first() is None  # nothing exists before the code
    code = reg.code(); wrong = "000000" if code != "000000" else "111111"
    assert reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": wrong}).status_code == 400
    r = reg.c.post("/api/register/verify", json={"email": "Asha@College.edu", "code": code}); assert r.status_code == 200
    u = r.json()["user"]; assert u["role"] == "student" and u["self_registered"] is True and u["placed"] is False
    h = {"Authorization": "Bearer " + r.json()["token"]}; assert reg.c.get("/api/me", headers=h).status_code == 200
    with Session_() as s:
        x = s.query(User).filter_by(email="asha@college.edu").one()
        assert (x.name, x.institution, x.id_number, x.phone, x.active, x.must_change) == ("Asha Devi", "Karkathar College", "21CS001", "+91 98765 43210", True, False)
        assert s.query(PendingRegistration).count() == 0
    assert reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": code}).status_code == 400  # a code works once
    assert reg.c.post("/api/login", json={"email": "asha@college.edu", "password": "longenough1"}).status_code == 200

def test_existing_email_looks_the_same_and_gets_a_notice(reg):
    a = reg.start(email="stu@x.com"); b = reg.start(email="new@x.com")
    assert a.status_code == b.status_code == 200 and a.json()["message"].replace("stu@x.com", "") == b.json()["message"].replace("new@x.com", "")
    assert "already has an account" in reg.sent[0][2]
    with Session_() as s: assert s.query(PendingRegistration).filter_by(email="stu@x.com").count() == 0

def test_duplicate_institution_id_is_refused(reg):
    with Session_() as s: s.add(User(name="Old", email="old@x.com", pw="x", role="student", institution="Karkathar College", id_number="21cs001")); s.commit()
    assert reg.start().status_code == 400

def test_wrong_codes_expiry_and_attempt_limit(reg):
    reg.start(); code = reg.code(); wrong = "000000" if code != "000000" else "111111"
    for _ in range(4): assert reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": wrong}).status_code == 400
    r = reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": wrong}); assert "Too many" in r.json()["detail"]
    assert reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": code}).status_code == 400  # locked even with the right code
    wait("asha@college.edu"); assert reg.start().status_code == 200  # a new code resets the tries
    assert reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": reg.code()}).status_code == 200
    reg.start(email="b@college.edu", id_number="22CS002"); wait("b@college.edu", expires_at=dt.datetime.utcnow() - dt.timedelta(seconds=1))
    assert reg.c.post("/api/register/verify", json={"email": "b@college.edu", "code": reg.code()}).status_code == 400

def test_resend_cooldown_and_caps(reg):
    reg.start(); assert reg.start().status_code == 429
    assert reg.c.post("/api/register/resend", json={"email": "asha@college.edu"}).status_code == 429
    wait("asha@college.edu"); n = len(reg.sent); assert reg.c.post("/api/register/resend", json={"email": "asha@college.edu"}).status_code == 200 and len(reg.sent) == n + 1
    wait("asha@college.edu", sends=main.OTP_MAX_SENDS); assert reg.c.post("/api/register/resend", json={"email": "asha@college.edu"}).status_code == 429
    assert reg.c.post("/api/register/resend", json={"email": "ghost@x.com"}).status_code == 200  # no hint whether anything is waiting

def test_allowed_domains(reg):
    assert reg.c.put("/api/admin/settings", headers=reg.admin, json={"allowed_domains": "college.edu, @uni.ac.in"}).status_code == 200
    assert reg.c.get("/api/register/status").json()["domains"] == ["college.edu", "uni.ac.in"]
    assert reg.start(email="a@gmail.com").status_code == 400 and reg.start(email="a@evil-college.edu").status_code == 400
    assert reg.start(email="a@cs.college.edu").status_code == 200
    assert reg.c.put("/api/admin/settings", headers=reg.admin, json={"allowed_domains": "not a domain!"}).status_code == 400
    s = reg.c.get("/api/admin/settings", headers=reg.admin).json(); assert s["self_registration"] is True and s["allowed_domains"] == "college.edu,uni.ac.in" or "college.edu" in s["allowed_domains"]

def signed_up(reg):
    reg.start(); t = reg.c.post("/api/register/verify", json={"email": "asha@college.edu", "code": reg.code()}).json()["token"]; return {"Authorization": "Bearer " + t}

def test_self_registered_users_need_their_own_ai_key_and_never_use_the_shared_one(reg, monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient); FakeClient.mode, FakeClient.calls = "ok", 0
    with Session_() as s: s.merge(main.Setting(k="deepseek_key", v="sk-shared-admin-key-123456")); s.commit()
    h = signed_up(reg)
    assert reg.c.get("/api/ai/status", headers=h).json() == {"available": False, "own_key": True}
    assert reg.c.get("/api/ai/status", headers=reg.stu).json()["available"] is True  # staff-added users still use the shared key
    assert reg.c.put("/api/me/ai-key", headers=reg.stu, json={"key": "sk-" + "a" * 30}).status_code == 403
    for bad in ("short", "sk-" + "a b" * 12): assert reg.c.put("/api/me/ai-key", headers=h, json={"key": bad}).status_code == 400
    FakeClient.mode = "401"; assert reg.c.put("/api/me/ai-key", headers=h, json={"key": "sk-" + "a" * 30}).status_code == 400
    FakeClient.mode = "boom"; assert reg.c.put("/api/me/ai-key", headers=h, json={"key": "sk-" + "a" * 30}).status_code == 400
    assert reg.c.get("/api/me/ai-key", headers=h).json()["key_set"] is False
    FakeClient.mode = "ok"; key = "sk-" + "z" * 30; r = reg.c.put("/api/me/ai-key", headers=h, json={"key": f" {key} "}); assert r.status_code == 200 and r.json()["key_hint"] == "…zzzz"
    with Session_() as s: raw = s.query(User).filter_by(email="asha@college.edu").one().ai_key
    assert raw and key not in raw and main.unseal(raw) == key  # stored encrypted
    g = reg.c.get("/api/me/ai-key", headers=h).json(); assert g == {"own_key": True, "key_set": True, "key_hint": "…zzzz"} and key not in str(g)
    assert reg.c.get("/api/ai/status", headers=h).json()["available"] is True
    assert reg.c.delete("/api/me/ai-key", headers=h).status_code == 200 and reg.c.get("/api/ai/status", headers=h).json()["available"] is False

def test_ai_endpoint_uses_the_users_own_key(reg, monkeypatch):
    from tests.test_access import CSV, ids, enrol
    seen = []
    class Spy(FakeClient):
        async def post(self, url, headers=None, json=None): seen.append(headers["Authorization"]); return await super().post(url, headers=headers, json=json)
    monkeypatch.setattr(main.httpx, "AsyncClient", Spy); FakeClient.mode = "ok"
    reg.csv(CSV); i = ids(); t = i["topic"]["Water"]
    with Session_() as s: s.merge(main.Setting(k="deepseek_key", v="sk-shared-admin-key-123456")); s.commit()
    h = signed_up(reg)
    with Session_() as s: uid = s.query(User).filter_by(email="asha@college.edu").one().id
    enrol("asha@college.edu", i["prog"]["Mech"], 1)
    r = reg.c.get(f"/api/topics/{t}/ai/explain", headers=h); assert r.status_code == 503 and r.json()["detail"] == main.NEEDS_OWN_KEY and seen == []
    reg.c.put("/api/me/ai-key", headers=h, json={"key": "sk-" + "q" * 30}); seen.clear()
    r = reg.c.get(f"/api/topics/{t}/ai/explain", headers=h); assert r.status_code == 200 and seen == ["Bearer sk-" + "q" * 30]

def test_admin_sees_registration_details_and_migration_adds_columns(reg, tmp_path):
    signed_up(reg); rows = reg.c.get("/api/admin/users?q=21CS001", headers=reg.admin).json()
    rows = rows["items"] if isinstance(rows, dict) else rows
    assert rows[0]["self_registered"] is True and rows[0]["institution"] == "Karkathar College" and rows[0]["phone"] and "own_ai_key" in rows[0]
    from sqlalchemy import create_engine, text, inspect
    e = create_engine(f"sqlite:///{tmp_path}/o.db")
    with e.begin() as c: c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, pw TEXT, role TEXT, active BOOLEAN)"))
    old = main.engine; main.engine = e
    try:
        main.upgrade_schema(); assert {"institution", "id_number", "phone", "self_registered", "ai_key"} <= {x["name"] for x in inspect(e).get_columns("users")}
    finally: main.engine = old
