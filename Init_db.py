# init_db.py
import os, sqlite3
from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, "university.db")
SCHEMA = os.path.join(BASE, "schema.sql")

def init():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")     # concurrent reads
    with open(SCHEMA, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    # Seed reference data (only if empty)
    cur = db.execute("SELECT COUNT(*) FROM departments")
    if cur.fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO departments(code,name) VALUES(?,?)",
            [("CS","Computer Science"), ("EE","Electrical Engineering"),
             ("BA","Business Administration")]
        )
        db.executemany(
            "INSERT INTO semesters(name,starts_on,ends_on,is_current) VALUES(?,?,?,?)",
            [("2025-Spring","2025-01-15","2025-05-30",1)]
        )

    # Bootstrap the admin user from env (never hardcode).
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    admin_pw   = os.environ.get("ADMIN_PASSWORD", "")
    if admin_pw:
        db.execute(
            """INSERT OR IGNORE INTO users(username,password_hash,role)
               VALUES(?,?, 'admin')""",
            (admin_user, generate_password_hash(admin_pw))
        )

    db.commit()
    db.close()
    print(f"Database ready at {DB}")

if __name__ == "__main__":
    init()
