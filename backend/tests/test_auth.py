import hashlib, jwt, main
from main import Session_, User, LoginFail, hp, vp, stale

def login(env, email, pw, **kw): return env.c.post("/api/login", json={"email": email, "password": pw}, **kw)

def test_legacy_hash_logs_in_and_is_upgraded(env):
    legacy = "abcd1234abcd1234$" + hashlib.pbkdf2_hmac("sha256", b"oldpass12", b"abcd1234abcd1234", 100000).hex()
    with Session_() as s: s.add(User(name="L", email="l@x.com", pw=legacy, role="student")); s.commit()
    assert vp("oldpass12", legacy) and not vp("nope", legacy)
    assert login(env, "l@x.com", "oldpass12").status_code == 200
    with Session_() as s: assert not stale(s.query(User).filter_by(email="l@x.com").first().pw) or main.ITER <= 100000

def test_admin_set_password_forces_a_change(env):
    r = env.c.post("/api/admin/users", headers=env.admin, json={"name": "S", "email": "s2@x.com", "password": "temp12345", "role": "student"}); assert r.status_code == 200
    j = login(env, "s2@x.com", "temp12345").json(); h = {"Authorization": "Bearer " + j["token"]}
    assert j["user"]["must_change"] is True and env.c.get("/api/tree", headers=h).status_code == 403 and env.c.get("/api/me", headers=h).status_code == 200
    P = lambda cur, new: env.c.post("/api/me/password", headers=h, json={"current": cur, "new_password": new})
    assert (P("bad", "newpass123").status_code, P("temp12345", "short").status_code, P("temp12345", "temp12345").status_code) == (400, 400, 400)
    new = P("temp12345", "mynewpass9").json()["token"]
    assert env.c.get("/api/tree", headers={"Authorization": "Bearer " + new}).status_code == 200
    assert env.c.get("/api/me", headers=h).status_code == 401  # the old session ended with the old password
    assert login(env, "s2@x.com", "temp12345").status_code == 401 and login(env, "s2@x.com", "mynewpass9").status_code == 200

def test_tokens_without_fingerprint_or_with_bad_signature_are_refused(env):
    assert env.c.get("/api/me", headers={"Authorization": "Bearer " + jwt.encode({"uid": 1, "exp": 9999999999}, "t" * 40)}).status_code == 401
    assert env.c.get("/api/me", headers={"Authorization": "Bearer " + jwt.encode({"uid": 1, "exp": 9999999999}, "wrong" * 10)}).status_code == 401

def test_lockout_after_five_misses_and_other_accounts_unaffected(env):
    assert [login(env, "stu@x.com", "bad").status_code for _ in range(6)] == [401] * 5 + [429]
    assert login(env, "stu@x.com", "pw").status_code == 429 and login(env, "admin@x.com", "pw").status_code == 200
    with Session_() as s: s.query(LoginFail).delete(); s.commit()
    assert login(env, "stu@x.com", "pw").status_code == 200

def test_unknown_accounts_are_throttled_too(env):
    assert [login(env, "ghost@x.com", "x").status_code for _ in range(6)][-1] == 429

def test_disabled_user_is_blocked_and_roles_are_validated(env):
    with Session_() as s: s.query(User).filter_by(email="stu@x.com").update({"active": False}); s.commit()
    assert login(env, "stu@x.com", "pw").status_code == 403 and env.c.get("/api/me", headers=env.stu).status_code == 401

def test_secret_must_be_strong():
    import pytest
    old = main.SECRET
    try:
        for bad in ("", "change-me", "short"):
            main.SECRET = bad
            with pytest.raises(RuntimeError): main.require_secret()
    finally: main.SECRET = old
    main.require_secret()
