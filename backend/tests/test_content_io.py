PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100

def test_image_upload_rules(env):
    r = env.c.post("/api/uploads", headers=env.admin, content=PNG); assert r.status_code == 200
    g = env.c.get(r.json()["url"]); assert g.status_code == 200 and g.content == PNG and g.headers["x-content-type-options"] == "nosniff"
    assert env.c.post("/api/uploads", headers=env.fac, content=b"\xff\xd8\xff" + b"0" * 20).status_code == 200
    assert env.c.post("/api/uploads", headers=env.stu, content=PNG).status_code == 403
    assert env.c.post("/api/uploads", content=PNG).status_code == 401
    for bad in (b"<svg onload=alert(1)>", b"<html>", b"#!/bin/sh"): assert env.c.post("/api/uploads", headers={**env.admin, "Content-Type": "image/png"}, content=bad).status_code == 400
    assert env.c.post("/api/uploads", headers=env.admin, content=PNG + b"0" * (3 * 1024 * 1024)).status_code == 413
    assert [env.c.get(u).status_code for u in ("/api/uploads/..%2Fmain.py", "/api/uploads/" + "0" * 32 + ".png", "/api/uploads/" + "0" * 32 + ".svg")] == [404] * 3

def test_csv_import_creates_hierarchy_and_dry_run_changes_nothing(env):
    text = "program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Water,w\n"
    r = env.c.post("/api/admin/import", headers=env.admin, json={"csv": text, "dry_run": True}); assert r.status_code == 200
    assert env.c.get("/api/tree", headers=env.admin).json() == []
    env.csv(text); assert env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["topics"][0]["title"] == "Water"

def test_health_and_security_headers(env):
    r = env.c.get("/api/health"); assert r.json() == {"ok": True, "db": True}
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert env.c.options("/api/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}).headers.get("access-control-allow-origin") is None

def test_math_content_is_stored_as_written(env):
    env.csv("program,semester,course,unit,topic,content\nMech,Semester 1,Chem,U1,Eq,$\\ce{CaCO3 + CO2 -> Ca(HCO3)2}$\n")
    t = env.c.get("/api/tree", headers=env.admin).json()[0]["semesters"][0]["courses"][0]["units"][0]["topics"][0]["id"]
    assert "\\ce{CaCO3" in env.c.get(f"/api/topics/{t}", headers=env.admin).json()["content"]
