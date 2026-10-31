# Sign in with Google: the token is checked against Google's keys, this site's client ID and Google as issuer; an account is found by its linked
# Google account or its email (then linked); an unknown email may sign up without an emailed code, when sign-up is open.
import datetime as dt
import jwt, pytest
from cryptography.hazmat.primitives.asymmetric import rsa
import main
from main import Session_, User, hp
from tests.test_registration import reg, GOOD  # noqa: F401  (the fixture)
from tests.test_onboarding import places, KID

WEB = "1234567890-abcdef.apps.googleusercontent.com"
def setup(env): assert env.c.put("/api/admin/settings", headers=env.admin, json={"google_client_id": WEB}).status_code == 200
def fake_google(monkeypatch, **claims):  # what Google's checked token says
    base = {"sub": "g-111", "email": "stu@x.com", "email_verified": True, "name": "Stu Dent"}
    def claims_of(token, audiences):
        if token == "bad": raise jwt.InvalidSignatureError("forged")
        if token == "offline": raise jwt.PyJWKClientError("no network")
        assert audiences == [WEB]; return {**base, **claims}
    monkeypatch.setattr(main, "google_claims", claims_of)
def google(env, token="ok"): return env.c.post("/api/login/google", json={"credential": token})

def test_it_is_off_until_an_admin_sets_the_client_id_and_the_button_is_allowed_to_load(env):
    assert env.c.get("/api/config").json()["google_client_id"] is None and google(env).status_code == 404
    assert env.c.put("/api/admin/settings", headers=env.admin, json={"google_client_id": "not-an-id"}).status_code == 400
    assert env.c.put("/api/admin/settings", headers=env.stu, json={"google_client_id": WEB}).status_code == 403
    setup(env); assert env.c.get("/api/config").json()["google_client_id"] == WEB and env.c.get("/api/admin/settings", headers=env.admin).json()["google_client_id"] == WEB
    csp = env.c.get("/api/config").headers["content-security-policy"]
    assert "script-src 'self' https://accounts.google.com/gsi/client" in csp and "frame-src 'self' https://accounts.google.com/gsi/" in csp and "frame-ancestors 'none'" in csp
    env.c.put("/api/admin/settings", headers=env.admin, json={"google_client_id": ""}); assert env.c.get("/api/config").json()["google_client_id"] is None

def test_an_account_is_found_by_its_email_then_by_its_linked_google_account(env, monkeypatch):
    setup(env); fake_google(monkeypatch)
    r = google(env).json(); assert r["user"]["name"] == "stu@x.com" and r["user"]["google"] is True
    assert env.c.get("/api/me", headers={"Authorization": "Bearer " + r["token"]}).status_code == 200
    with Session_() as s: assert s.query(User).filter_by(email="stu@x.com").one().google_sub == "g-111"
    fake_google(monkeypatch, email="new-address@gmail.com"); assert google(env).json()["user"]["name"] == "stu@x.com"  # Google's email changed: the link still finds them
    fake_google(monkeypatch, sub="g-999"); assert google(env).status_code == 409  # the same email, another Google account
    with Session_() as s: s.query(User).filter_by(email="stu@x.com").update({"active": False}); s.commit()
    fake_google(monkeypatch); assert google(env).status_code == 403
    assert env.c.post("/api/login", json={"email": "fac@x.com", "password": "pw"}).status_code == 200  # passwords keep working

def test_bad_tokens_unverified_emails_and_an_unreachable_google_are_refused(env, monkeypatch):
    setup(env); fake_google(monkeypatch, email_verified=False); assert google(env).status_code == 401
    fake_google(monkeypatch); assert google(env, "offline").status_code == 503
    codes = [google(env, "bad").status_code for _ in range(6)]; assert codes[:5] == [401] * 5 and codes[5] == 429  # one network, a few tries, then a wait

def test_with_sign_up_open_a_new_google_email_signs_up_without_a_code(reg, monkeypatch):
    setup(reg); sch, _ = places(); fake_google(monkeypatch, sub="g-new", email="amma@gmail.com", name="Amma")
    r = google(reg).json(); assert r["new"] and r["email"] == "amma@gmail.com" and r["name"] == "Amma" and "token" not in r
    assert reg.c.get("/api/me", headers={"Authorization": "Bearer " + r["ticket"]}).status_code == 401  # a sign-up ticket is never a sign-in
    n = len(reg.sent)
    body = {**GOOD, "ticket": r["ticket"], "who": "parent", "level": "school", "institution": "", "id_number": "", "email": "someone@else.com", "password": "",
            "children": [dict(KID, program_id=sch, semester=6)], "lang": "ta"}
    out = reg.c.post("/api/register/google", json=body); assert out.status_code == 200, out.text
    me = out.json()["user"]; assert (me["role"], me["relation"], me["google"], me["lang"]) == ("guardian", "parent", True, "ta")
    with Session_() as s: u = s.query(User).filter_by(email="amma@gmail.com").one(); assert u.google_sub == "g-new" and s.query(User).filter_by(email="someone@else.com").first() is None
    assert not any("code" in subj.lower() for _, subj, _ in reg.sent[n:])  # no code: Google checked the email
    assert reg.c.post("/api/register/google", json=body).status_code == 409  # once only
    assert google(reg).json()["user"]["name"] == "Asha Devi"  # and from now on Google signs them in
    assert reg.c.post("/api/login", json={"email": "kavin.r", "password": KID["password"]}).status_code == 200  # the child's own sign-in works
    old = jwt.encode({"use": "gsignup", "sub": "g-x", "email": "x@gmail.com", "exp": dt.datetime.utcnow() - dt.timedelta(minutes=1)}, main.SECRET)
    assert reg.c.post("/api/register/google", json={**body, "ticket": old}).status_code == 400
    forged = jwt.encode({"use": "gsignup", "sub": "g-x", "email": "x@gmail.com", "exp": dt.datetime.utcnow() + dt.timedelta(minutes=5)}, "not-the-secret-" * 4)
    assert reg.c.post("/api/register/google", json={**body, "ticket": forged}).status_code == 400

def test_with_sign_up_closed_an_unknown_google_email_is_turned_away(env, monkeypatch):
    setup(env); fake_google(monkeypatch, sub="g-new", email="stranger@gmail.com")
    r = google(env); assert r.status_code == 404 and "Ask your admin" in r.json()["detail"]

@pytest.fixture
def keys(monkeypatch):  # a key pair standing in for Google's: tokens signed with it pass only when everything else is right too
    good, other = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
    class Jwks:
        def get_signing_key_from_jwt(self, token): return type("K", (), {"key": good.public_key()})()
    monkeypatch.setattr(main, "_google_jwks", Jwks()); return good, other
def token(key, **over):
    now = dt.datetime.utcnow()
    c = {"iss": "https://accounts.google.com", "aud": WEB, "sub": "g-1", "email": "a@gmail.com", "email_verified": True, "iat": now, "exp": now + dt.timedelta(minutes=5), **over}
    return jwt.encode({k: v for k, v in c.items() if v is not None}, key, algorithm="RS256")
def test_the_token_itself_is_checked_signature_audience_issuer_and_expiry(keys):
    good, other = keys
    assert main.google_claims(token(good), [WEB])["email"] == "a@gmail.com"
    assert main.google_claims(token(good, iss="accounts.google.com"), [WEB])["sub"] == "g-1"
    for bad in (token(other), token(good, aud="999-other.apps.googleusercontent.com"), token(good, iss="https://evil.example"),
                token(good, exp=dt.datetime.utcnow() - dt.timedelta(minutes=10)), token(good, sub=None),
                jwt.encode({"iss": "https://accounts.google.com", "aud": WEB, "sub": "g", "exp": dt.datetime.utcnow() + dt.timedelta(minutes=5), "iat": dt.datetime.utcnow()}, "x" * 40, algorithm="HS256")):
        with pytest.raises(jwt.InvalidTokenError): main.google_claims(bad, [WEB])

def test_the_migration_adds_the_google_column_once(env):
    main.upgrade_schema(); main.upgrade_schema()
    cols = [c["name"] for c in main.inspect(main.engine).get_columns("users")]; assert cols.count("google_sub") == 1
    assert main.applied_migrations().count("0030_users_google") == 1
    with Session_() as s:
        s.add_all([User(name="A", email="a1@x.com", pw=hp("pw"), role="student"), User(name="B", email="b1@x.com", pw=hp("pw"), role="student")]); s.commit()  # many without Google
        s.add(User(name="C", email="c1@x.com", pw=hp("pw"), role="student", google_sub="dup")); s.add(User(name="D", email="d1@x.com", pw=hp("pw"), role="student", google_sub="dup"))
        with pytest.raises(main.IntegrityError): s.commit()  # but one account per Google account

def test_without_email_on_the_server_sign_up_is_with_google_only(env, monkeypatch):
    assert not main.mail_on(main.Session_())  # no email set up here
    env.c.put("/api/admin/settings", headers=env.admin, json={"self_registration": True})
    c = env.c.get("/api/config").json(); assert c["self_registration"] is False  # no email and no Google: nothing to sign up with
    setup(env); c = env.c.get("/api/config").json(); assert c["self_registration"] is True and c["email_signup"] is False
    assert env.c.get("/api/register/status").json() == {"open": True, "email": False, "domains": []}
    assert env.c.post("/api/register/start", json={**GOOD, "who": "student", "level": "college"}).status_code == 403  # a code can't be emailed
    sch, _ = places(); fake_google(monkeypatch, sub="g-solo", email="solo@gmail.com", name="Solo")
    r = google(env).json(); assert r["new"]
    body = {**GOOD, "ticket": r["ticket"], "who": "parent", "level": "school", "institution": "", "id_number": "", "email": "", "password": "", "children": [dict(KID, program_id=sch, semester=6)]}
    out = env.c.post("/api/register/google", json=body); assert out.status_code == 200, out.text
    assert out.json()["user"]["google"] is True and google(env).json()["user"]["name"] == "Asha Devi"
    env.c.put("/api/admin/settings", headers=env.admin, json={"self_registration": False})
    fake_google(monkeypatch, sub="g-late", email="late@gmail.com"); assert google(env).status_code == 404  # the admin's switch still closes it
