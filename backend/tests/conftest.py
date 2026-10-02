import os, sys, tempfile
_tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/test.db", JWT_SECRET="t" * 40, UPLOAD_DIR=f"{_tmp}/uploads", PBKDF2_ITER="1000")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from fastapi.testclient import TestClient
import main
from main import Session_, User, hp

class Env:
    def __init__(self):
        self.c = TestClient(main.app)
    def login(self, email, pw="pw"):
        r = self.c.post("/api/login", json={"email": email, "password": pw}); assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["token"]}
    def csv(self, text):
        r = self.c.post("/api/admin/import", headers=self.admin, json={"csv": text, "dry_run": False}); assert r.status_code == 200, r.text
        return r.json()
    def add_user(self, email, role="student", program=None, semester=None, pw="pw"):
        with Session_() as s: s.add(User(name=email, email=email, pw=hp(pw), role=role, program_id=program, semester=semester)); s.commit()

@pytest.fixture
def env():
    main.Base.metadata.drop_all(main.engine); main.upgrade_schema()
    e = Env()
    e.add_user("admin@x.com", "admin"); e.add_user("fac@x.com", "faculty"); e.add_user("stu@x.com")
    e.admin, e.fac, e.stu = e.login("admin@x.com"), e.login("fac@x.com"), e.login("stu@x.com")
    return e
