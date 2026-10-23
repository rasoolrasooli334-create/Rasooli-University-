# app.py
"""
Rasooli University — University Management System.

Single-file Flask application backed by SQLite. On first boot it
creates the schema, enables WAL + foreign keys, and bootstraps an
administrator account from environment variables.
"""

import os
import secrets
import sqlite3
import time
from functools import wraps
from pathlib import Path

from flask import (
    Flask, g, request, redirect, url_for,
    render_template_string, session, flash, abort,
)
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "university.db"))

app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    # Dev fallback: sessions reset on restart. Set SECRET_KEY in production.
    _secret = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY not set — using an ephemeral key.")

app.config.update(
    SECRET_KEY=_secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,     # 8 hours
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,          # 2 MB request cap
)

# --------------------------------------------------------------------------- #
# Schema (idempotent — safe to run on every boot)
# --------------------------------------------------------------------------- #

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    id         INTEGER PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS instructors (
    id            INTEGER PRIMARY KEY,
    employee_no   TEXT NOT NULL UNIQUE,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    hired_on      TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    id            INTEGER PRIMARY KEY,
    student_no    TEXT NOT NULL UNIQUE,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    date_of_birth TEXT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    enrolled_on   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status        TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','graduated','suspended','withdrawn'))
);

CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    credits       INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 6),
    department_id INTEGER NOT NULL REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS semesters (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    starts_on  TEXT NOT NULL,
    ends_on    TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1))
);

CREATE TABLE IF NOT EXISTS sections (
    id            INTEGER PRIMARY KEY,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    semester_id   INTEGER NOT NULL REFERENCES semesters(id),
    instructor_id INTEGER REFERENCES instructors(id),
    room          TEXT,
    schedule      TEXT,
    capacity      INTEGER NOT NULL DEFAULT 30 CHECK (capacity > 0)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    section_id  INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    enrolled_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    grade       TEXT CHECK (grade IN ('A','B','C','D','F','I','W')),
    UNIQUE (student_id, section_id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'admin'
        CHECK (role IN ('admin','staff','instructor')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_department ON students(department_id);
CREATE INDEX IF NOT EXISTS idx_students_status     ON students(status);
CREATE INDEX IF NOT EXISTS idx_instructors_dept    ON instructors(department_id);
CREATE INDEX IF NOT EXISTS idx_courses_department  ON courses(department_id);
CREATE INDEX IF NOT EXISTS idx_sections_semester   ON sections(semester_id);
CREATE INDEX IF NOT EXISTS idx_sections_instructor ON sections(instructor_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_section ON enrollments(section_id);

CREATE VIEW IF NOT EXISTS v_student_directory AS
SELECT s.id,
       s.student_no,
       s.first_name || ' ' || s.last_name AS full_name,
       s.email,
       d.code AS department,
       s.status
FROM students s
JOIN departments d ON d.id = s.department_id;
"""

# --------------------------------------------------------------------------- #
# Database layer
# --------------------------------------------------------------------------- #

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA synchronous = NORMAL")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql: str, args=(), one: bool = False):
    """Run a SELECT and return dict rows (or a single dict)."""
    cur = get_db().execute(sql, args)
    try:
        rows = cur.fetchall()
    finally:
        cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def execute(sql: str, args=()):
    """Run a write statement and commit."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    rid = cur.lastrowid
    cur.close()
    return rid


def table_exists(name: str) -> bool:
    return get_db().execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (name,),
    ).fetchone() is not None


def table_columns(name: str):
    if not table_exists(name):
        return []
    return [r["name"] for r in get_db().execute(f'PRAGMA table_info("{name}")')]


def count_rows(name: str) -> int:
    if not name or not table_exists(name):
        return 0
    return get_db().execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]


def paginate(sql: str, args=(), page: int = 1, per_page: int = 25):
    """Return (rows, meta) for a SELECT with stable ordering."""
    page = max(1, int(page or 1))
    per_page = min(max(1, per_page), 200)
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    offset = (page - 1) * per_page
    rows = db.execute(
        f"{sql} LIMIT ? OFFSET ?", (*args, per_page, offset)
    ).fetchall()
    return [dict(r) for r in rows], {
        "page": page, "pages": pages, "per_page": per_page, "total": total,
    }


# --------------------------------------------------------------------------- #
# Schema bootstrap + admin seeding (runs once at import)
# --------------------------------------------------------------------------- #

def ensure_schema():
    db = sqlite3.connect(DATABASE)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA_SQL)
        db.commit()
    finally:
        db.close()


def ensure_admin():
    user = os.environ.get("ADMIN_USERNAME")
    pw = os.environ.get("ADMIN_PASSWORD")
    pw_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if not user or not (pw or pw_hash):
        return
    pw_hash = pw_hash or generate_password_hash(pw)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO users(username, password_hash, role) "
        "VALUES (?, ?, 'admin')",
        (user, pw_hash),
    )
    db.commit()


with app.app_context():
    ensure_schema()
    ensure_admin()


# --------------------------------------------------------------------------- #
# CSRF
# --------------------------------------------------------------------------- #

def csrf_token() -> str:
    tok = session.get("_csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf"] = tok
    return tok


def csrf_valid() -> bool:
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    tok = session.get("_csrf")
    return bool(tok and sent) and secrets.compare_digest(tok, sent)


app.jinja_env.globals["csrf_token"] = csrf_token


# --------------------------------------------------------------------------- #
# Login rate limiting (per-process, best-effort)
# --------------------------------------------------------------------------- #

LOGIN_WINDOW = 300           # seconds
LOGIN_MAX_FAILS = 10
_login_fails: dict[str, list[float]] = {}


def _client_key() -> str:
    # Render puts the real IP in X-Forwarded-For.
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote_addr or "unknown")


def login_blocked(key: str) -> bool:
    now = time.time()
    hits = [t for t in _login_fails.get(key, []) if now - t < LOGIN_WINDOW]
    _login_fails[key] = hits
    return len(hits) >= LOGIN_MAX_FAILS


def record_login_fail(key: str):
    _login_fails.setdefault(key, []).append(time.time())


# --------------------------------------------------------------------------- #
# Auth decorator
# --------------------------------------------------------------------------- #

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Rasooli University</title>
<style>
* { box-sizing:border-box; }
body { margin:0; font-family:Arial,sans-serif; background:#f1f5f9; color:#172033; }
header { background:#123b63; color:white; padding:18px; }
header h1 { margin:0 0 8px; font-size:23px; }
nav { display:flex; gap:9px; flex-wrap:wrap; margin-top:12px; align-items:center; }
nav a, nav button { color:white; text-decoration:none; background:#24547d;
  padding:10px 12px; border:0; border-radius:6px; font:inherit; cursor:pointer; }
nav button:hover, nav a:hover { background:#2f6596; }
main { max-width:1100px; margin:20px auto; padding:0 14px; }
.card { background:white; padding:18px; border-radius:10px;
  box-shadow:0 2px 8px #0000000d; margin-bottom:16px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
.number { font-size:28px; font-weight:bold; color:#123b63; }
label { display:block; font-weight:bold; margin:12px 0 5px; }
input,select,textarea { width:100%; padding:11px; border:1px solid #cbd5e1;
  border-radius:6px; font-size:16px; }
button,.button { display:inline-block; background:#123b63; color:white;
  padding:11px 15px; border:0; border-radius:6px; text-decoration:none;
  cursor:pointer; margin-top:12px; font:inherit; }
button:hover,.button:hover { background:#1b5286; }
table { width:100%; border-collapse:collapse; background:white; }
th,td { text-align:left; padding:10px; border-bottom:1px solid #e2e8f0;
  vertical-align:top; }
th { background:#eaf0f6; }
.table-wrap { overflow-x:auto; }
.message { padding:12px; background:#dcfce7; border-radius:6px; margin-bottom:12px; }
.message.error { background:#fee2e2; }
.toolbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.toolbar input { flex:1 1 220px; }
.pager { display:flex; gap:8px; margin-top:12px; }
.pager .button { margin-top:0; }
.muted { color:#64748b; }
@media(max-width:600px) { header h1 { font-size:20px; } th,td { padding:8px; font-size:13px; } }
</style>
</head>
<body>
<header>
  <h1>Rasooli University</h1>
  <div>University Management System</div>
  {% if session.get('logged_in') %}
  <nav>
    <a href="{{ url_for('dashboard') }}">Dashboard</a>
    <a href="{{ url_for('students') }}">Students</a>
    <a href="{{ url_for('courses') }}">Courses</a>
    <a href="{{ url_for('database_info') }}">Database</a>
    <form method="post" action="{{ url_for('logout') }}" style="margin:0">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit">Log out</button>
    </form>
  </nav>
  {% endif %}
</header>
<main>
  {% for category, msg in get_flashed_messages(with_categories=true) %}
  <div class="message {{ 'error' if category == 'error' else '' }}">{{ msg }}</div>
  {% endfor %}
  <h2>{{ title }}</h2>
  {{ content|safe }}
</main>
</body>
</html>
"""

TABLE_SNIPPET = """
<div class="table-wrap">
  <table>
    <thead>
      <tr>{% for c in columns %}<th>{{ c }}</th>{% endfor %}</tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        {% for c in columns %}
        <td>{{ row[c] if row[c] is not none else '' }}</td>
        {% endfor %}
      </tr>
      {% else %}
      <tr><td colspan="{{ columns|length or 1 }}" class="muted">No records found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
"""


def page(title: str, content: str, **ctx) -> str:
    """
    Render `content` first (with autoescape), then inject it into PAGE.
    Dynamic values passed via `ctx` are escaped by Jinja — no `|safe`
    is ever applied to user or database data.
    """
    body = render_template_string(content, **ctx)
    return render_template_string(PAGE, title=title, content=body, **ctx)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("logged_in") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")

        key = _client_key()
        if login_blocked(key):
            flash("Too many failed attempts. Try again in a few minutes.", "error")
            return _login_page(), 429

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        ok = False
        user = query(
            "SELECT id, password_hash FROM users "
            "WHERE username = ? AND is_active = 1",
            (username,), one=True,
        )
        if user:
            try:
                ok = check_password_hash(user["password_hash"], password)
            except (ValueError, TypeError):
                ok = False
        else:
            # Bootstrap fallback if the users table is empty/misconfigured.
            env_user = os.environ.get("ADMIN_USERNAME")
            env_pw = os.environ.get("ADMIN_PASSWORD")
            env_hash = os.environ.get("ADMIN_PASSWORD_HASH")
            if env_user and username == env_user:
                if env_pw:
                    ok = secrets.compare_digest(password, env_pw)
                elif env_hash:
                    try:
                        ok = check_password_hash(env_hash, password)
                    except (ValueError, TypeError):
                        ok = False

        if ok:
            _login_fails.pop(key, None)
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("dashboard"))

        record_login_fail(key)
        flash("Login failed. Please check your username and password.", "error")

    return _login_page()


def _login_page():
    content = """
    <div class="card">
      <p>Sign in to the University Management System.</p>
      <form method="post" autocomplete="on">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <label for="username">Username</label>
        <input id="username" name="username" required autocomplete="username" autofocus>
        <label for="password">Password</label>
        <input id="password" type="password" name="password"
               required autocomplete="current-password">
        <button type="submit">Sign in</button>
      </form>
      <p class="muted"><small>Administrator accounts are seeded from
      ADMIN_USERNAME and ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH).</small></p>
    </div>
    """
    return page("Login", content)


@app.route("/logout", methods=["POST"])
def logout():
    if csrf_valid():
        session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    students_n = count_rows("students")
    courses_n = count_rows("courses")
    teachers_n = count_rows("instructors")
    enrollments_n = count_rows("enrollments")

    recent = []
    if table_exists("enrollments") and table_exists("sections"):
        recent = query("""
            SELECT s.student_no,
                   s.first_name || ' ' || s.last_name AS student,
                   c.code  AS course,
                   sem.name AS semester,
                   e.enrolled_on
            FROM enrollments e
            JOIN students  s   ON s.id  = e.student_id
            JOIN sections  sec ON sec.id = e.section_id
            JOIN courses   c   ON c.id  = sec.course_id
            JOIN semesters sem ON sem.id = sec.semester_id
            ORDER BY e.enrolled_on DESC, e.id DESC
            LIMIT 10
        """)

    content = """
    <div class="cards">
      <div class="card"><div>Students</div><div class="number">{{ students_n }}</div></div>
      <div class="card"><div>Courses</div><div class="number">{{ courses_n }}</div></div>
      <div class="card"><div>Teachers</div><div class="number">{{ teachers_n }}</div></div>
      <div class="card"><div>Enrollments</div><div class="number">{{ enrollments_n }}</div></div>
    </div>

    <div class="card">
      <h3>Welcome, {{ username }}</h3>
      <p>Use the navigation menu to browse your university records.</p>
      <p class="muted">Database: <strong>university.db</strong> (SQLite, WAL)</p>
    </div>

    {% if recent %}
    <div class="card">
      <h3>Recent enrollments</h3>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Student No.</th><th>Student</th><th>Course</th>
            <th>Semester</th><th>Enrolled</th>
          </tr></thead>
          <tbody>
          {% for r in recent %}
            <tr>
              <td>{{ r.student_no }}</td><td>{{ r.student }}</td>
              <td>{{ r.course }}</td><td>{{ r.semester }}</td>
              <td>{{ r.enrolled_on }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    {% endif %}
    """
    return page(
        "Dashboard", content,
        students_n=students_n, courses_n=courses_n,
        teachers_n=teachers_n, enrollments_n=enrollments_n,
        recent=recent, username=session.get("username", "Administrator"),
    )


@app.route("/students")
@login_required
def students():
    if not table_exists("v_student_directory"):
        return page(
            "Students",
            '<div class="card">The student directory view is missing. '
            'Delete university.db to rebuild the schema.</div>',
        )

    q = (request.args.get("q") or "").strip()
    where, args = "", []
    if q:
        where = ("WHERE full_name LIKE ? OR student_no LIKE ? OR email LIKE ?")
        like = f"%{q}%"
        args = [like, like, like]

    sql = f"SELECT * FROM v_student_directory {where} ORDER BY full_name, student_no"
    rows, meta = paginate(sql, args, request.args.get("page", 1, type=int), 25)
    columns = ["student_no", "full_name", "email", "department", "status"]

    content = """
    <div class="card">
      <form method="get" class="toolbar">
        <input name="q" value="{{ q }}" placeholder="Search name, number, or email">
        <button type="submit">Search</button>
        {% if q %}<a class="button" href="{{ url_for('students') }}">Clear</a>{% endif %}
      </form>
      <p class="muted">
        {{ meta.total }} record(s) — page {{ meta.page }} of {{ meta.pages }}.
      </p>
      """ + TABLE_SNIPPET + """
      <div class="pager">
        {% if meta.page > 1 %}
        <a class="button" href="{{ url_for('students', q=q, page=meta.page - 1) }}">Previous</a>
        {% endif %}
        {% if meta.page < meta.pages %}
        <a class="button" href="{{ url_for('students', q=q, page=meta.page + 1) }}">Next</a>
        {% endif %}
      </div>
    </div>
    """
    return page("Students", content, rows=rows, columns=columns, meta=meta, q=q)


@app.route("/courses")
@login_required
def courses():
    if not table_exists("courses"):
        return page("Courses", '<div class="card">Courses table not found.</div>')

    sql = """
        SELECT c.code, c.title, c.credits, d.code AS department
        FROM courses c
        JOIN departments d ON d.id = c.department_id
        ORDER BY c.code
    """
    rows, meta = paginate(sql, (), request.args.get("page", 1, type=int), 25)
    columns = ["code", "title", "credits", "department"]

    content = """
    <div class="card">
      <p class="muted">
        {{ meta.total }} course(s) — page {{ meta.page }} of {{ meta.pages }}.
      </p>
      """ + TABLE_SNIPPET + """
      <div class="pager">
        {% if meta.page > 1 %}
        <a class="button" href="{{ url_for('courses', page=meta.page - 1) }}">Previous</a>
        {% endif %}
        {% if meta.page < meta.pages %}
        <a class="button" href="{{ url_for('courses', page=meta.page + 1) }}">Next</a>
        {% endif %}
      </div>
    </div>
    """
    return page("Courses", content, rows=rows, columns=columns, meta=meta)


@app.route("/database")
@login_required
def database_info():
    db = get_db()
    names = [r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    info = [
        {"name": n, "rows": count_rows(n), "columns": table_columns(n)}
        for n in names
    ]

    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    fk_issues = len(db.execute("PRAGMA foreign_key_check").fetchall())
    db_size = f"{Path(DATABASE).stat().st_size / 1024:.1f} KB" if Path(DATABASE).exists() else "n/a"

    content = """
    <div class="card">
      <p class="muted">
        File: <strong>{{ db_file }}</strong> · Size: {{ db_size }} ·
        Integrity: <strong>{{ integrity }}</strong> ·
        Foreign-key issues: <strong>{{ fk_issues }}</strong>
      </p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Table</th><th>Rows</th><th>Columns</th></tr></thead>
          <tbody>
          {% for t in info %}
            <tr>
              <td>{{ t.name }}</td>
              <td>{{ t.rows }}</td>
              <td>{{ t.columns|join(', ') }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
      <p class="muted"><strong>Backup:</strong> Render's ephemeral disk loses
      SQLite changes on redeploy. Use Render PostgreSQL or attach a
      persistent disk and point <code>DATABASE_PATH</code> at it.</p>
    </div>
    """
    return page(
        "Database Information", content,
        info=info, integrity=integrity, fk_issues=fk_issues,
        db_file=Path(DATABASE).name, db_size=db_size,
    )


# --------------------------------------------------------------------------- #
# Error handlers + security headers
# --------------------------------------------------------------------------- #

@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'",
    )
    return resp


@app.errorhandler(404)
def not_found(_err):
    return page(
        "Not found",
        '<div class="card">The page you requested does not exist. '
        '<a class="button" href="' + url_for("dashboard") + '">Back to dashboard</a></div>',
    ), 404


@app.errorhandler(400)
def bad_request(err):
    msg = getattr(err, "description", "Bad request.")
    return page("Bad request", f'<div class="card">{escape(msg)}</div>'), 400


@app.errorhandler(sqlite3.IntegrityError)
def integrity_error(err):
    app.logger.warning("Database integrity error: %s", err)
    return page(
        "Database error",
        '<div class="card">That operation would violate a database '
        'constraint (duplicate value or missing reference).</div>',
    ), 400


@app.errorhandler(HTTPException)
def http_error(err):
    return page(
        err.name,
        f'<div class="card">{escape(err.description or "")}</div>',
    ), err.code


@app.errorhandler(500)
def server_error(err):
    app.logger.exception("Unhandled error: %s", err)
    return page(
        "Server error",
        '<div class="card">An internal error occurred. '
        'Check the Render logs for details.</div>',
    ), 500


# --------------------------------------------------------------------------- #
# Dev entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Production: gunicorn "app:app" --bind 0.0.0.0:$PORT
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
