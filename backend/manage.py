"""Admin CLI: create/reset admins, add students, reset any password, enable/disable, list.
Run via ./manage.sh. Omit --password to be prompted securely."""
import argparse, getpass, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
from main import Base, engine, Session_, User, hp, upgrade_schema

def password(given):
    while True:
        p = given or getpass.getpass("Password: ")
        if len(p) < 8: print("Use at least 8 characters."); given = None; continue
        if given or p == getpass.getpass("Confirm password: "): return p
        print("Passwords don't match, try again."); given = None

def find(s, email):
    u = s.query(User).filter_by(email=email.strip().lower()).first()
    if not u: sys.exit(f"No user with email {email}. See: ./manage.sh list")
    return u

def main():
    ap = argparse.ArgumentParser(description=__doc__); sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("admin", help="create the admin, or reset its password and re-enable it")
    ad.add_argument("--email", required=True); ad.add_argument("--name", default="Admin"); ad.add_argument("--password")
    a = sub.add_parser("add", help="create a user"); a.add_argument("--name", required=True); a.add_argument("--email", required=True)
    a.add_argument("--role", choices=["student", "admin"], default="student"); a.add_argument("--password")
    p = sub.add_parser("passwd", help="reset the password of any user"); p.add_argument("--email", required=True); p.add_argument("--password")
    for c in ("enable", "disable"): sub.add_parser(c, help=c + " a user").add_argument("--email", required=True)
    r = sub.add_parser("role", help="change a user's role"); r.add_argument("--email", required=True); r.add_argument("--role", choices=["student", "admin"], required=True)
    sub.add_parser("list", help="list users"); sub.add_parser("check", help="exit 1 if there is no active admin")
    x = ap.parse_args(); upgrade_schema()
    with Session_() as s:
        if x.cmd == "check": sys.exit(0 if s.query(User).filter_by(role="admin", active=True).first() else 1)
        if x.cmd == "list":
            for u in s.query(User).order_by(User.id): print(f"{u.id:>3}  {u.role:<8} {'active' if u.active else 'disabled':<9} {u.email}  ({u.name})")
        elif x.cmd == "add":
            e = x.email.strip().lower()
            if s.query(User).filter_by(email=e).first(): sys.exit(f"{e} already exists. Use passwd to reset the password.")
            s.add(User(name=x.name, email=e, pw=hp(password(x.password)), role=x.role, must_change=x.role != "admin")); s.commit(); print(f"Created {x.role} {e}")
        elif x.cmd == "admin":
            e = x.email.strip().lower(); u = s.query(User).filter_by(email=e).first()
            if u: u.pw = hp(password(x.password)); u.role = "admin"; u.active = True; print(f"Reset password and set {e} as active admin")
            else: s.add(User(name=x.name, email=e, pw=hp(password(x.password)), role="admin")); print(f"Created admin {e}")
            s.commit()
        else:
            u = find(s, x.email)
            if x.cmd == "passwd": u.pw = hp(password(x.password)); u.must_change = u.role != "admin"
            elif x.cmd == "role": u.role = x.role
            else: u.active = x.cmd == "enable"
            s.commit(); print(f"Updated {u.email}")

if __name__ == "__main__": main()
