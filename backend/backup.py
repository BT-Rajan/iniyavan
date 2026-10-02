"""Backups: a compressed database dump plus the uploaded images, with old copies pruned."""
import datetime as dt, gzip, os, shutil, sqlite3, subprocess, tarfile, tempfile, time
from sqlalchemy.engine import make_url

def run_backup(db_url, uploads_dir, out_dir, keep_days=14):
    os.makedirs(out_dir, exist_ok=True)
    stamp, url, made = dt.datetime.now().strftime("%Y%m%d-%H%M%S"), make_url(db_url), []
    if url.get_backend_name() == "sqlite":
        tmp = os.path.join(out_dir, f"engtutor-{stamp}-db.sqlite.tmp"); src, dst = sqlite3.connect(url.database), sqlite3.connect(tmp)
        src.backup(dst); src.close(); dst.close(); out = os.path.join(out_dir, f"engtutor-{stamp}-db.sqlite.gz")
        with open(tmp, "rb") as f, gzip.open(out, "wb") as g: shutil.copyfileobj(f, g)
        os.remove(tmp); made.append(out)
    else:
        if not shutil.which("mysqldump"): raise RuntimeError("mysqldump was not found. Install the MariaDB/MySQL client tools.")
        pw = (url.password or "").replace("\\", "\\\\").replace('"', '\\"')
        with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as cnf:  # keeps the password off the command line
            os.chmod(cnf.name, 0o600); cnf.write(f'[client]\nuser="{url.username or ""}"\npassword="{pw}"\nhost="{url.host or "localhost"}"\nport={url.port or 3306}\n')
        out = os.path.join(out_dir, f"engtutor-{stamp}-db.sql.gz")
        try:
            with gzip.open(out, "wb") as g:
                p = subprocess.run(["mysqldump", f"--defaults-extra-file={cnf.name}", "--single-transaction", "--routines", "--default-character-set=utf8mb4", url.database], stdout=g, stderr=subprocess.PIPE)
            if p.returncode: os.remove(out); raise RuntimeError("mysqldump failed: " + p.stderr.decode(errors="replace").strip())
        finally: os.remove(cnf.name)
        made.append(out)
    if os.path.isdir(uploads_dir) and os.listdir(uploads_dir):
        out = os.path.join(out_dir, f"engtutor-{stamp}-uploads.tar.gz")
        with tarfile.open(out, "w:gz") as t: t.add(uploads_dir, arcname="uploads")
        made.append(out)
    cutoff = time.time() - keep_days * 86400
    for f in os.listdir(out_dir):
        fp = os.path.join(out_dir, f)
        if f.startswith("engtutor-") and os.path.isfile(fp) and os.path.getmtime(fp) < cutoff: os.remove(fp)
    return made
