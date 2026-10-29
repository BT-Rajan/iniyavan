# The site under a folder of its address (BASE_PATH=/zigora): the proxy passes /zigora/... through, the app answers as if at the root,
# and what it hands back to a browser (redirects, the install manifest, pictures inside an interactive page) points back under /zigora.
import main
from main import Session_, User, hp

def under(monkeypatch, base="/zigora"): monkeypatch.setattr(main, "BASE_PATH", base)

def test_everything_answers_under_the_folder_and_still_at_the_root(env, monkeypatch):
    under(monkeypatch)
    assert env.c.get("/zigora/api/config").status_code == 200 and env.c.get("/api/config").status_code == 200  # the server itself can still be asked directly
    r = env.c.post("/zigora/api/login", json={"email": "stu@x.com", "password": "pw"}); assert r.status_code == 200
    assert env.c.get("/zigora/api/me", headers={"Authorization": "Bearer " + r.json()["token"]}).json()["name"] == "stu@x.com"
    assert "content-security-policy" in env.c.get("/zigora/api/config").headers  # the security headers see the same paths as before
    r = env.c.get("/zigora", follow_redirects=False); assert r.status_code == 308 and r.headers["location"] == "/zigora/"
    assert env.c.get("/zigora?x=1", follow_redirects=False).headers["location"] == "/zigora/?x=1"
    assert env.c.get("/zigora/").status_code == 200  # the home page
    assert env.c.get("/zigorax/api/config").status_code == 404  # only the folder itself, not a name that starts the same way

def test_a_password_that_must_change_is_still_enforced_under_the_folder(env, monkeypatch):
    under(monkeypatch)
    with Session_() as s: s.add(User(name="New", email="new@x.com", pw=hp("pw"), role="student", must_change=True)); s.commit()
    t = env.c.post("/zigora/api/login", json={"email": "new@x.com", "password": "pw"}).json()["token"]; h = {"Authorization": "Bearer " + t}
    assert env.c.get("/zigora/api/me", headers=h).status_code == 200 and env.c.get("/zigora/api/tree", headers=h).status_code == 403

def test_the_apps_own_redirects_go_back_under_the_folder():
    b, host = "/zigora", "apps.perennia.org"
    assert main.back_under("/app/", b, host) == "/zigora/app/"
    assert main.back_under("https://apps.perennia.org/app/?a=1#x", b, host) == "https://apps.perennia.org/zigora/app/?a=1#x"
    assert main.back_under("/zigora/app/", b, host) == "/zigora/app/"  # already under it
    assert main.back_under("https://accounts.google.com/x", b, host) == "https://accounts.google.com/x"  # another site
    assert main.back_under("app/", b, host) == "app/"

def test_the_install_manifest_and_an_interactive_pages_pictures_point_under_the_folder(env, monkeypatch):
    m = env.c.get("/app/manifest.json").json(); assert m["start_url"] == "/app/" and m["icons"][0]["src"] == "/app/icon-192.png"
    under(monkeypatch)
    m = env.c.get("/zigora/app/manifest.json").json(); assert m["start_url"] == m["scope"] == "/zigora/app/" and all(i["src"].startswith("/zigora/app/") for i in m["icons"])
    page = '<html><head></head><body><img src="/api/uploads/ab.png"><div style="background:url(\'/api/uploads/cd.png\')"></div><a href=/api/uploads/ef.png>x</a><img src="https://x.org/api/uploads/no.png"></body></html>'
    out = main.frame_page(page).body.decode()
    assert 'src="/zigora/api/uploads/ab.png"' in out and "url('/zigora/api/uploads/cd.png')" in out and "href=/zigora/api/uploads/ef.png" in out and "https://x.org/api/uploads/no.png" in out
    under(monkeypatch, ""); assert 'src="/api/uploads/ab.png"' in main.frame_page(page).body.decode()  # at the root: untouched

def test_the_saved_site_address_may_include_the_folder(env):
    r = env.c.put("/api/admin/mail", headers=env.admin, json={"app_url": "https://apps.perennia.org/zigora/app/"}); assert r.status_code == 200, r.text
    assert r.json()["app_url"] == "https://apps.perennia.org/zigora"
    assert env.c.put("/api/admin/mail", headers=env.admin, json={"app_url": "https://apps.perennia.org/zig ora"}).status_code == 400
