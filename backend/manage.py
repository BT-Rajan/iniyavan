"""Admin CLI: create admins/students, reset passwords, enable/disable, list.
Run via ./manage.sh (see README). Omit --password to be prompted securely."""
import argparse, getpass, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
from main import Base, engine, Session_, User, hp

def password(given):
    while True:
        p = given or getpass.getpass("Password: ")
        if len(p) < 8: print("Use at least 8 characters."); given = None; continue
        if given or p == getpass.getpass("Confirm password: "): return p
        print("Passwords don't match, try again.")

def find(s, email):
    u = s.query(User).filter_by(email=email.strip().lower()).first()
    if not u: sys.exit(f"No user with email {email}")
    return u

def main():
    ap = argparse.ArgumentParser(description=__doc__); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="create a user"); a.add_argument("--name", required=True); a.add_argument("--email", required=True)
    a.add_argument("--role", choices=["student", "admin"], default="student"); a.add_argument("--password")
    p = sub.add_parser("passwd", help="reset a password"); p.add_argument("--email", required=True); p.add_argument("--password")
    for c in ("enable", "disable"): sub.add_parser(c, help=c + " a user").add_argument("--email", required=True)
    r = sub.add_parser("role", help="change a user's role"); r.add_argument("--email", required=True); r.add_argument("--role", choices=["student", "admin"], required=True)
    sub.add_parser("list", help="list users")
    x = ap.parse_args(); Base.metadata.create_all(engine)
    with Session_() as s:
        if x.cmd == "add":
            e = x.email.strip().lower()
            if s.query(User).filter_by(email=e).first(): sys.exit(f"{e} already exists. Use passwd to reset the password.")
            s.add(User(name=x.name, email=e, pw=hp(password(x.password)), role=x.role)); s.commit(); print(f"Created {x.role} {e}")
        elif x.cmd == "list":
            for u in s.query(User).order_by(User.id): print(f"{u.id:>3}  {u.role:<8} {'active' if u.active else 'disabled':<9} {u.email}  ({u.name})")
        else:
            u = find(s, x.email)
            if x.cmd == "passwd": u.pw = hp(password(x.password))
            elif x.cmd == "role": u.role = x.role
            else: u.active = x.cmd == "enable"
            s.commit(); print(f"Updated {u.email}")

if __name__ == "__main__": main()
