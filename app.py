# app.py
"""
Rasooli University — University Management System (CRUD).

Boot sequence:
  • detect legacy DBs, archive them,
  • create schema (idempotent), enable WAL + FKs,
  • seed departments + current semester,
  • seed admin user from env vars.
"""

import os
import re
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
    _secret = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY not set — using an ephemeral key.")

app.config.update(
    SECRET_KEY=_secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

# --------------------------------------------------------------------------- #
# Schema
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


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    try:
        rows = cur.fetchall()
    finally:
        cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    rid = cur.lastrowid
    cur.close()
    return rid


def count_rows(name):
    if not name:
        return 0
    return get_db().execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]


def table_exists(name):
    return get_db().execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    ).fetchone() is not None


def paginate(sql, args=(), page=1, per_page=25):
    page = max(1, int(page or 1))
    per_page = min(max(1, per_page), 200)
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    offset = (page - 1) * per_page
    rows = db.execute(f"{sql} LIMIT ? OFFSET ?",
                      (*args, per_page, offset)).fetchall()
    return [dict(r) for r in rows], {
        "page": page, "pages": pages, "per_page": per_page, "total": total,
    }


# --------------------------------------------------------------------------- #
# Schema bootstrap + seeding
# --------------------------------------------------------------------------- #

def _table_columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _legacy_schema_present():
    if not os.path.exists(DATABASE):
        return False
    conn = sqlite3.connect(DATABASE)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='students'"
        ).fetchone()
        if not row:
            return False
        cols = set(_table_columns(conn, "students"))
        return not {"department_id", "student_no",
                    "status", "enrolled_on"}.issubset(cols)
    finally:
        conn.close()


def _archive_legacy_db():
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{DATABASE}.legacy-{ts}.bak"
    for path in (DATABASE, DATABASE + "-wal", DATABASE + "-shm"):
        if os.path.exists(path):
            os.replace(path, backup + path[len(DATABASE):])
    app.logger.warning("Legacy DB archived to %s", backup)


def ensure_schema():
    if _legacy_schema_present():
        _archive_legacy_db()
    db = sqlite3.connect(DATABASE)
    try:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA_SQL)
        db.commit()
    finally:
        db.close()


def ensure_seed():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO departments(code, name) VALUES(?,?)",
            [("CS", "Computer Science"),
             ("EE", "Electrical Engineering"),
             ("BA", "Business Administration"),
             ("MA", "Mathematics"),
             ("PH", "Physics")],
        )
    if db.execute("SELECT COUNT(*) FROM semesters").fetchone()[0] == 0:
        db.execute(
            "INSERT INTO semesters(name, starts_on, ends_on, is_current) "
            "VALUES(?,?,?,1)",
            ("2025-Spring", "2025-01-15", "2025-05-30"),
        )
    db.commit()


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
        "VALUES (?, ?, 'admin')", (user, pw_hash),
    )
    db.commit()


with app.app_context():
    ensure_schema()
    ensure_seed()
    ensure_admin()


# --------------------------------------------------------------------------- #
# CSRF
# --------------------------------------------------------------------------- #

def csrf_token():
    tok = session.get("_csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf"] = tok
    return tok


def csrf_valid():
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    tok = session.get("_csrf")
    return bool(tok and sent) and secrets.compare_digest(tok, sent)


app.jinja_env.globals["csrf_token"] = csrf_token


# --------------------------------------------------------------------------- #
# Login rate limiting
# --------------------------------------------------------------------------- #

LOGIN_WINDOW = 300
LOGIN_MAX_FAILS = 10
_login_fails = {}


def _client_key():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() or request.remote_addr or "unknown"


def login_blocked(key):
    now = time.time()
    hits = [t for t in _login_fails.get(key, []) if now - t < LOGIN_WINDOW]
    _login_fails[key] = hits
    return len(hits) >= LOGIN_MAX_FAILS


def record_login_fail(key):
    _login_fails.setdefault(key, []).append(time.time())


# --------------------------------------------------------------------------- #
# Auth + form helpers
# --------------------------------------------------------------------------- #

def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email):
    return bool(EMAIL_RE.match(email or ""))


def form_str(name, default=""):
    v = request.form.get(name)
    return (v or default).strip()


def form_int(name):
    v = request.form.get(name)
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def friendly_integrity(err):
    msg = str(err).lower()
    if "unique" in msg:
        if "email" in msg:
            return "That email is already in use."
        if "student_no" in msg:
            return "That student number is already in use."
        if "employee_no" in msg:
            return "That employee number is already in use."
        if "code" in msg:
            return "That code is already in use."
        return "A unique field is duplicated."
    if "foreign key" in msg:
        return "A referenced record does not exist, or this record is in use."
    if "check" in msg:
        return "A field value is invalid."
    return "Database error: " + str(err)


def departments():
    return query("SELECT id, code, name FROM departments ORDER BY code")


def get_department(dept_id):
    if not dept_id:
        return None
    return query("SELECT id FROM departments WHERE id = ?",
                 (dept_id,), one=True)


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
button.danger { background:#b91c1c; }
button.danger:hover { background:#dc2626; }
button.small, .button.small { padding:6px 10px; margin-top:0; font-size:13px; }
table { width:100%; border-collapse:collapse; background:white; }
th,td { text-align:left; padding:10px; border-bottom:1px solid #e2e8f0; vertical-align:top; }
th { background:#eaf0f6; }
.table-wrap { overflow-x:auto; }
.message { padding:12px; background:#dcfce7; border-radius:6px; margin-bottom:12px; }
.message.error { background:#fee2e2; }
.toolbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.toolbar input { flex:1 1 220px; }
.pager { display:flex; gap:8px; margin-top:12px; }
.pager .button { margin-top:0; }
.muted { color:#64748b; }
.actions { white-space:nowrap; }
.actions form { display:inline; }
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
    <a href="{{ url_for('teachers') }}">Teachers</a>
    <a href="{{ url_for('departments_view') }}">Departments</a>
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

TABLE_CRUD = """
<div class="table-wrap">
  <table>
    <thead><tr>
      {% for c in columns %}<th>{{ c }}</th>{% endfor %}
      <th>Actions</th>
    </tr></thead>
    <tbody>
      {% for row in rows %}
      <tr>
        {% for c in columns %}
        <td>{{ row[c] if row[c] is not none else '' }}</td>
        {% endfor %}
        <td class="actions">
          <a class="button small" href="{{ row._edit }}">Edit</a>
          <form method="post" action="{{ row._delete }}"
                onsubmit="return confirm('Delete this record? This cannot be undone.');">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit" class="danger small">Delete</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="{{ columns|length + 1 }}" class="muted">No records found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
"""


def page(title, content, **ctx):
    body = render_template_string(content, **ctx)
    return render_template_string(PAGE, title=title, content=body, **ctx)


def _attach_urls(rows, edit_endpoint, delete_endpoint, key, param):
    for r in rows:
        r["_edit"] = url_for(edit_endpoint, **{param: r[key]})
        r["_delete"] = url_for(delete_endpoint, **{param: r[key]})
    return rows


def _pager(meta, endpoint, q=""):
    if meta["pages"] <= 1:
        return ""
    parts = []
    if meta["page"] > 1:
        args = {"page": meta["page"] - 1}
        if q:
            args["q"] = q
        parts.append(
            f'<a class="button" href="{url_for(endpoint, **args)}">Previous</a>'
        )
    if meta["page"] < meta["pages"]:
        args = {"page": meta["page"] + 1}
        if q:
            args["q"] = q
        parts.append(
            f'<a class="button" href="{url_for(endpoint, **args)}">Next</a>'
        )
    return '<div class="pager">' + "".join(parts) + "</div>"


def _error_box(errors):
    if not errors:
        return ""
    items = "".join(f"<li>{v}</li>" for v in errors.values())
    return (f'<div class="message error"><strong>Please fix these:</strong>'
            f'<ul>{items}</ul></div>')


# --------------------------------------------------------------------------- #
# Auth
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
            flash("Too many failed attempts. Try again later.", "error")
            return _login_page(), 429
        username = form_str("username")
        password = request.form.get("password") or ""
        ok = False
        user = query("SELECT id, password_hash FROM users "
                     "WHERE username = ? AND is_active = 1",
                     (username,), one=True)
        if user:
            try:
                ok = check_password_hash(user["password_hash"], password)
            except (ValueError, TypeError):
                ok = False
        else:
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
    return page("Login", """
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
      <p class="muted"><small>Admin is seeded from ADMIN_USERNAME and
      ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH).</small></p>
    </div>
    """)


@app.route("/logout", methods=["POST"])
def logout():
    if csrf_valid():
        session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

@app.route("/dashboard")
@login_required
def dashboard():
    content = """
    <div class="cards">
      <div class="card"><div>Students</div><div class="number">{{ s }}</div></div>
      <div class="card"><div>Courses</div><div class="number">{{ c }}</div></div>
      <div class="card"><div>Teachers</div><div class="number">{{ t }}</div></div>
      <div class="card"><div>Departments</div><div class="number">{{ d }}</div></div>
      <div class="card"><div>Enrollments</div><div class="number">{{ e }}</div></div>
    </div>
    <div class="card">
      <h3>Welcome, {{ username }}</h3>
      <p>Use the navigation menu to manage students, courses, and teachers.</p>
      <div class="toolbar" style="margin-top:12px">
        <a class="button" href="{{ url_for('student_new') }}">+ Add student</a>
        <a class="button" href="{{ url_for('course_new') }}">+ Add course</a>
        <a class="button" href="{{ url_for('teacher_new') }}">+ Add teacher</a>
        <a class="button" href="{{ url_for('department_new') }}">+ Add department</a>
      </div>
    </div>
    """
    return page(
        "Dashboard", content,
        s=count_rows("students"),
        c=count_rows("courses"),
        t=count_rows("instructors"),
        d=count_rows("departments"),
        e=count_rows("enrollments"),
        username=session.get("username", "Administrator"),
    )


# --------------------------------------------------------------------------- #
# Students CRUD
# --------------------------------------------------------------------------- #

STUDENT_FORM = """
<div class="card">
  {{ errors_html|safe }}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Student number *</label>
    <input name="student_no" value="{{ row.student_no }}" required maxlength="32">

    <label>First name *</label>
    <input name="first_name" value="{{ row.first_name }}" required maxlength="80">

    <label>Last name *</label>
    <input name="last_name" value="{{ row.last_name }}" required maxlength="80">

    <label>Email *</label>
    <input type="email" name="email" value="{{ row.email }}" required maxlength="120">

    <label>Department *</label>
    <select name="department_id" required>
      <option value="">— select —</option>
      {% for d in departments %}
      <option value="{{ d.id }}" {% if row.department_id|string == d.id|string %}selected{% endif %}>
        {{ d.code }} — {{ d.name }}
      </option>
      {% endfor %}
    </select>

    <label>Date of birth</label>
    <input type="date" name="date_of_birth" value="{{ row.date_of_birth }}">

    <label>Status</label>
    <select name="status">
      {% for s in statuses %}
      <option value="{{ s }}" {% if row.status == s %}selected{% endif %}>{{ s }}</option>
      {% endfor %}
    </select>

    <button type="submit">Save</button>
    <a class="button" href="{{ url_for('students') }}">Cancel</a>
  </form>
</div>
"""

STUDENT_STATUSES = ("active", "graduated", "suspended", "withdrawn")


def _student_row_from_form():
    return {
        "student_no": form_str("student_no")[:32],
        "first_name": form_str("first_name")[:80],
        "last_name": form_str("last_name")[:80],
        "email": form_str("email")[:120],
        "department_id": form_str("department_id"),
        "date_of_birth": form_str("date_of_birth"),
        "status": form_str("status", "active") or "active",
    }


def _validate_student(row):
    errors = {}
    if not row["student_no"]:
        errors["student_no"] = "Student number is required."
    if not row["first_name"]:
        errors["first_name"] = "First name is required."
    if not row["last_name"]:
        errors["last_name"] = "Last name is required."
    if not valid_email(row["email"]):
        errors["email"] = "A valid email is required."
    if not get_department(row["department_id"]):
        errors["department_id"] = "Select a valid department."
    if row["status"] not in STUDENT_STATUSES:
        errors["status"] = "Invalid status."
    return errors


def _render_student_form(action_url, row, errors, submit_label):
    return page(
        submit_label, STUDENT_FORM,
        row=row, errors=errors,
        errors_html=_error_box(errors),
        departments=departments(),
        statuses=STUDENT_STATUSES,
    )


@app.route("/students")
@login_required
def students():
    q = (request.args.get("q") or "").strip()
    sql = """
        SELECT s.id, s.student_no,
               s.first_name || ' ' || s.last_name AS full_name,
               s.email, d.code AS department, s.status
        FROM students s JOIN departments d ON d.id = s.department_id
    """
    args = []
    if q:
        sql += (" WHERE s.first_name LIKE ? OR s.last_name LIKE ? "
                "OR s.student_no LIKE ? OR s.email LIKE ?")
        like = f"%{q}%"
        args = [like, like, like, like]
    sql += " ORDER BY s.last_name, s.first_name"
    rows, meta = paginate(sql, args, request.args.get("page", 1, type=int))
    _attach_urls(rows, "student_edit", "student_delete", "id", "sid")
    columns = ["student_no", "full_name", "email", "department", "status"]

    content = render_template_string("""
    <div class="card">
      <form method="get" class="toolbar">
        <input name="q" value="{{ q }}" placeholder="Search name, number, or email">
        <button type="submit">Search</button>
        {% if q %}<a class="button" href="{{ url_for('students') }}">Clear</a>{% endif %}
        <a class="button" href="{{ url_for('student_new') }}">+ Add student</a>
      </form>
      <p class="muted">{{ meta.total }} record(s) — page {{ meta.page }} of {{ meta.pages }}.</p>
      """ + TABLE_CRUD + _pager(meta, "students", q) + """
    </div>
    """, rows=rows, columns=columns, meta=meta, q=q)
    return page("Students", content)


@app.route("/students/new", methods=["GET", "POST"])
@login_required
def student_new():
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _student_row_from_form()
        errors = _validate_student(row)
        if not errors:
            try:
                execute(
                    "INSERT INTO students(student_no, first_name, last_name, "
                    "email, date_of_birth, department_id, status) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (row["student_no"], row["first_name"], row["last_name"],
                     row["email"], row["date_of_birth"] or None,
                     int(row["department_id"]), row["status"]),
                )
                flash(f"Student {row['first_name']} {row['last_name']} added.")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_student_form(url_for("student_new"), row, errors,
                                    "Add student"), 400
    empty = {"student_no": "", "first_name": "", "last_name": "", "email": "",
             "department_id": "", "date_of_birth": "", "status": "active"}
    return _render_student_form(url_for("student_new"), empty, {}, "Add student")


@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def student_edit(sid):
    student = query("SELECT * FROM students WHERE id = ?", (sid,), one=True)
    if not student:
        abort(404)
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _student_row_from_form()
        errors = _validate_student(row)
        if not errors:
            try:
                execute(
                    "UPDATE students SET student_no=?, first_name=?, last_name=?, "
                    "email=?, date_of_birth=?, department_id=?, status=? WHERE id=?",
                    (row["student_no"], row["first_name"], row["last_name"],
                     row["email"], row["date_of_birth"] or None,
                     int(row["department_id"]), row["status"], sid),
                )
                flash("Student updated.")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_student_form(url_for("student_edit", sid=sid),
                                    row, errors, "Edit student"), 400
    # GET
    row = {
        "student_no": student["student_no"],
        "first_name": student["first_name"],
        "last_name": student["last_name"],
        "email": student["email"],
        "department_id": student["department_id"],
        "date_of_birth": student["date_of_birth"] or "",
        "status": student["status"],
    }
    return _render_student_form(url_for("student_edit", sid=sid),
                                row, {}, "Edit student")


@app.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def student_delete(sid):
    if not csrf_valid():
        abort(400, "Invalid or missing CSRF token.")
    if not query("SELECT 1 FROM students WHERE id = ?", (sid,), one=True):
        abort(404)
    try:
        execute("DELETE FROM students WHERE id = ?", (sid,))
        flash("Student deleted.")
    except sqlite3.IntegrityError as exc:
        flash(friendly_integrity(exc), "error")
    return redirect(url_for("students"))


# --------------------------------------------------------------------------- #
# Courses CRUD
# --------------------------------------------------------------------------- #

COURSE_FORM = """
<div class="card">
  {{ errors_html|safe }}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <label>Course code *</label>
    <input name="code" value="{{ row.code }}" required maxlength="16"
           placeholder="e.g. CS101">

    <label>Title *</label>
    <input name="title" value="{{ row.title }}" required maxlength="120">

    <label>Credits (1–6) *</label>
    <input type="number" name="credits" value="{{ row.credits }}" required min="1" max="6">

    <label>Department *</label>
    <select name="department_id" required>
      <option value="">— select —</option>
      {% for d in departments %}
      <option value="{{ d.id }}" {% if row.department_id|string == d.id|string %}selected{% endif %}>
        {{ d.code }} — {{ d.name }}
      </option>
      {% endfor %}
    </select>

    <button type="submit">Save</button>
    <a class="button" href="{{ url_for('courses') }}">Cancel</a>
  </form>
</div>
"""


def _course_row_from_form():
    return {
        "code": form_str("code")[:16],
        "title": form_str("title")[:120],
        "credits": form_int("credits"),
        "department_id": form_str("department_id"),
    }


def _validate_course(row):
    errors = {}
    if not row["code"]:
        errors["code"] = "Course code is required."
    if not row["title"]:
        errors["title"] = "Title is required."
    if row["credits"] is None or not 1 <= row["credits"] <= 6:
        errors["credits"] = "Credits must be an integer from 1 to 6."
    if not get_department(row["department_id"]):
        errors["department_id"] = "Select a valid department."
    return errors


def _render_course_form(row, errors, submit_label):
    return page(
        submit_label, COURSE_FORM,
        row=row, errors=errors,
        errors_html=_error_box(errors),
        departments=departments(),
    )


@app.route("/courses")
@login_required
def courses():
    sql = """
        SELECT c.id, c.code, c.title, c.credits, d.code AS department
        FROM courses c JOIN departments d ON d.id = c.department_id
        ORDER BY c.code
    """
    rows, meta = paginate(sql, (), request.args.get("page", 1, type=int))
    _attach_urls(rows, "course_edit", "course_delete", "id", "cid")
    columns = ["code", "title", "credits", "department"]

    content = render_template_string("""
    <div class="card">
      <div class="toolbar">
        <a class="button" href="{{ url_for('course_new') }}">+ Add course</a>
      </div>
      <p class="muted">{{ meta.total }} course(s) — page {{ meta.page }} of {{ meta.pages }}.</p>
      """ + TABLE_CRUD + _pager(meta, "courses") + """
    </div>
    """, rows=rows, columns=columns, meta=meta)
    return page("Courses", content)


@app.route("/courses/new", methods=["GET", "POST"])
@login_required
def course_new():
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _course_row_from_form()
        errors = _validate_course(row)
        if not errors:
            try:
                execute(
                    "INSERT INTO courses(code, title, credits, department_id) "
                    "VALUES (?,?,?,?)",
                    (row["code"], row["title"], row["credits"],
                     int(row["department_id"])),
                )
                flash(f"Course {row['code']} added.")
                return redirect(url_for("courses"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_course_form(row, errors, "Add course"), 400
    return _render_course_form(
        {"code": "", "title": "", "credits": 3, "department_id": ""},
        {}, "Add course",
    )


@app.route("/courses/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def course_edit(cid):
    course = query("SELECT * FROM courses WHERE id = ?", (cid,), one=True)
    if not course:
        abort(404)
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _course_row_from_form()
        errors = _validate_course(row)
        if not errors:
            try:
                execute(
                    "UPDATE courses SET code=?, title=?, credits=?, "
                    "department_id=? WHERE id=?",
                    (row["code"], row["title"], row["credits"],
                     int(row["department_id"]), cid),
                )
                flash("Course updated.")
                return redirect(url_for("courses"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_course_form(row, errors, "Edit course"), 400
    row = {
        "code": course["code"], "title": course["title"],
        "credits": course["credits"], "department_id": course["department_id"],
    }
    return _render_course_form(row, {}, "Edit course")


@app.route("/courses/<int:cid>/delete", methods=["POST"])
@login_required
def course_delete(cid):
    if not csrf_valid():
        abort(400, "Invalid or missing CSRF token.")
    if not query("SELECT 1 FROM courses WHERE id = ?", (cid,), one=True):
        abort(404)
    try:
        execute("DELETE FROM courses WHERE id = ?", (cid,))
        flash("Course deleted.")
    except sqlite3.IntegrityError as exc:
        flash(friendly_integrity(exc), "error")
    return redirect(url_for("courses"))


# --------------------------------------------------------------------------- #
# Teachers (instructors) CRUD
# --------------------------------------------------------------------------- #

TEACHER_FORM = """
<div class="card">
  {{ errors_html|safe }}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <label>Employee number *</label>
    <input name="employee_no" value="{{ row.employee_no }}" required maxlength="32">

    <label>First name *</label>
    <input name="first_name" value="{{ row.first_name }}" required maxlength="80">

    <label>Last name *</label>
    <input name="last_name" value="{{ row.last_name }}" required maxlength="80">

    <label>Email *</label>
    <input type="email" name="email" value="{{ row.email }}" required maxlength="120">

    <label>Department *</label>
    <select name="department_id" required>
      <option value="">— select —</option>
      {% for d in departments %}
      <option value="{{ d.id }}" {% if row.department_id|string == d.id|string %}selected{% endif %}>
        {{ d.code }} — {{ d.name }}
      </option>
      {% endfor %}
    </select>

    <label>Hired on</label>
    <input type="date" name="hired_on" value="{{ row.hired_on }}">

    <button type="submit">Save</button>
    <a class="button" href="{{ url_for('teachers') }}">Cancel</a>
  </form>
</div>
"""


def _teacher_row_from_form():
    return {
        "employee_no": form_str("employee_no")[:32],
        "first_name": form_str("first_name")[:80],
        "last_name": form_str("last_name")[:80],
        "email": form_str("email")[:120],
        "department_id": form_str("department_id"),
        "hired_on": form_str("hired_on"),
    }


def _validate_teacher(row):
    errors = {}
    if not row["employee_no"]:
        errors["employee_no"] = "Employee number is required."
    if not row["first_name"]:
        errors["first_name"] = "First name is required."
    if not row["last_name"]:
        errors["last_name"] = "Last name is required."
    if not valid_email(row["email"]):
        errors["email"] = "A valid email is required."
    if not get_department(row["department_id"]):
        errors["department_id"] = "Select a valid department."
    return errors


def _render_teacher_form(row, errors, submit_label):
    return page(
        submit_label, TEACHER_FORM,
        row=row, errors=errors,
        errors_html=_error_box(errors),
        departments=departments(),
    )


@app.route("/teachers")
@login_required
def teachers():
    sql = """
        SELECT i.id, i.employee_no,
               i.first_name || ' ' || i.last_name AS full_name,
               i.email, d.code AS department, i.hired_on
        FROM instructors i JOIN departments d ON d.id = i.department_id
        ORDER BY i.last_name, i.first_name
    """
    rows, meta = paginate(sql, (), request.args.get("page", 1, type=int))
    _attach_urls(rows, "teacher_edit", "teacher_delete", "id", "tid")
    columns = ["employee_no", "full_name", "email", "department", "hired_on"]

    content = render_template_string("""
    <div class="card">
      <div class="toolbar">
        <a class="button" href="{{ url_for('teacher_new') }}">+ Add teacher</a>
      </div>
      <p class="muted">{{ meta.total }} teacher(s) — page {{ meta.page }} of {{ meta.pages }}.</p>
      """ + TABLE_CRUD + _pager(meta, "teachers") + """
    </div>
    """, rows=rows, columns=columns, meta=meta)
    return page("Teachers", content)


@app.route("/teachers/new", methods=["GET", "POST"])
@login_required
def teacher_new():
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _teacher_row_from_form()
        errors = _validate_teacher(row)
        if not errors:
            try:
                execute(
                    "INSERT INTO instructors(employee_no, first_name, last_name, "
                    "email, department_id, hired_on) VALUES (?,?,?,?,?,?)",
                    (row["employee_no"], row["first_name"], row["last_name"],
                     row["email"], int(row["department_id"]),
                     row["hired_on"] or None),
                )
                flash(f"Teacher {row['first_name']} {row['last_name']} added.")
                return redirect(url_for("teachers"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_teacher_form(row, errors, "Add teacher"), 400
    return _render_teacher_form(
        {"employee_no": "", "first_name": "", "last_name": "", "email": "",
         "department_id": "", "hired_on": ""},
        {}, "Add teacher",
    )


@app.route("/teachers/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def teacher_edit(tid):
    teacher = query("SELECT * FROM instructors WHERE id = ?", (tid,), one=True)
    if not teacher:
        abort(404)
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = _teacher_row_from_form()
        errors = _validate_teacher(row)
        if not errors:
            try:
                execute(
                    "UPDATE instructors SET employee_no=?, first_name=?, "
                    "last_name=?, email=?, department_id=?, hired_on=? WHERE id=?",
                    (row["employee_no"], row["first_name"], row["last_name"],
                     row["email"], int(row["department_id"]),
                     row["hired_on"] or None, tid),
                )
                flash("Teacher updated.")
                return redirect(url_for("teachers"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return _render_teacher_form(row, errors, "Edit teacher"), 400
    row = {
        "employee_no": teacher["employee_no"],
        "first_name": teacher["first_name"],
        "last_name": teacher["last_name"],
        "email": teacher["email"],
        "department_id": teacher["department_id"],
        "hired_on": teacher["hired_on"] or "",
    }
    return _render_teacher_form(row, {}, "Edit teacher")


@app.route("/teachers/<int:tid>/delete", methods=["POST"])
@login_required
def teacher_delete(tid):
    if not csrf_valid():
        abort(400, "Invalid or missing CSRF token.")
    if not query("SELECT 1 FROM instructors WHERE id = ?", (tid,), one=True):
        abort(404)
    try:
        execute("DELETE FROM instructors WHERE id = ?", (tid,))
        flash("Teacher deleted.")
    except sqlite3.IntegrityError as exc:
        flash(friendly_integrity(exc), "error")
    return redirect(url_for("teachers"))


# --------------------------------------------------------------------------- #
# Departments (list + create; needed so students/courses/teachers have options)
# --------------------------------------------------------------------------- #

DEPARTMENT_FORM = """
<div class="card">
  {{ errors_html|safe }}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Department code *</label>
    <input name="code" value="{{ row.code }}" required maxlength="8"
           placeholder="e.g. CS">
    <label>Name *</label>
    <input name="name" value="{{ row.name }}" required maxlength="80">
    <button type="submit">Save</button>
    <a class="button" href="{{ url_for('departments_view') }}">Cancel</a>
  </form>
</div>
"""


@app.route("/departments")
@login_required
def departments_view():
    rows = query("""
        SELECT d.id, d.code, d.name,
               (SELECT COUNT(*) FROM students s WHERE s.department_id = d.id) AS students,
               (SELECT COUNT(*) FROM courses c WHERE c.department_id = d.id) AS courses,
               (SELECT COUNT(*) FROM instructors i WHERE i.department_id = d.id) AS teachers
        FROM departments d ORDER BY d.code
    """)
    content = render_template_string("""
    <div class="card">
      <div class="toolbar">
        <a class="button" href="{{ url_for('department_new') }}">+ Add department</a>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Code</th><th>Name</th><th>Students</th><th>Courses</th><th>Teachers</th>
          </tr></thead>
          <tbody>
          {% for r in rows %}
            <tr>
              <td>{{ r.code }}</td><td>{{ r.name }}</td>
              <td>{{ r.students }}</td><td>{{ r.courses }}</td><td>{{ r.teachers }}</td>
            </tr>
          {% else %}
            <tr><td colspan="5" class="muted">No departments.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
      <p class="muted">Departments cannot be deleted while they have students,
      courses, or teachers attached.</p>
    </div>
    """, rows=rows)
    return page("Departments", content)


@app.route("/departments/new", methods=["GET", "POST"])
@login_required
def department_new():
    if request.method == "POST":
        if not csrf_valid():
            abort(400, "Invalid or missing CSRF token.")
        row = {"code": form_str("code")[:8].upper(),
               "name": form_str("name")[:80]}
        errors = {}
        if not row["code"]:
            errors["code"] = "Code is required."
        if not row["name"]:
            errors["name"] = "Name is required."
        if not errors:
            try:
                execute("INSERT INTO departments(code, name) VALUES(?,?)",
                        (row["code"], row["name"]))
                flash(f"Department {row['code']} added.")
                return redirect(url_for("departments_view"))
            except sqlite3.IntegrityError as exc:
                errors["_form"] = friendly_integrity(exc)
        return page("Add department", DEPARTMENT_FORM, row=row,
                    errors=errors, errors_html=_error_box(errors)), 400
    return page("Add department", DEPARTMENT_FORM,
                row={"code": "", "name": ""}, errors={}, errors_html="")


# --------------------------------------------------------------------------- #
# Database info
# --------------------------------------------------------------------------- #

@app.route("/database")
@login_required
def database_info():
    db = get_db()
    names = [r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    info = [
        {"name": n, "rows": count_rows(n),
         "columns": [c["name"] for c in db.execute(f'PRAGMA table_info("{n}")')]}
        for n in names
    ]
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    fk_issues = len(db.execute("PRAGMA foreign_key_check").fetchall())
    db_size = (f"{Path(DATABASE).stat().st_size / 1024:.1f} KB"
               if Path(DATABASE).exists() else "n/a")
    content = render_template_string("""
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
            <tr><td>{{ t.name }}</td><td>{{ t.rows }}</td>
                <td>{{ t.columns|join(', ') }}</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
      <p class="muted"><strong>Backup:</strong> Render's ephemeral disk
      loses SQLite changes on redeploy. Use PostgreSQL or a persistent disk.</p>
    </div>
    """, info=info, integrity=integrity, fk_issues=fk_issues,
        db_file=Path(DATABASE).name, db_size=db_size)
    return page("Database Information", content)


# --------------------------------------------------------------------------- #
# Errors + headers
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
    return page("Not found",
                '<div class="card">Page does not exist. '
                '<a class="button" href="' + url_for("dashboard") + '">Back</a></div>'), 404


@app.errorhandler(400)
def bad_request(err):
    return page("Bad request",
                f'<div class="card">{getattr(err, "description", "Bad request.")}</div>'), 400


@app.errorhandler(sqlite3.IntegrityError)
def integrity_error(err):
    app.logger.warning("DB integrity error: %s", err)
    return page("Database error",
                '<div class="card">A database constraint was violated.</div>'), 400


@app.errorhandler(HTTPException)
def http_error(err):
    return page(err.name,
                f'<div class="card">{err.description or ""}</div>'), err.code


@app.errorhandler(500)
def server_error(err):
    app.logger.exception("Unhandled error: %s", err)
    return page("Server error",
                '<div class="card">An internal error occurred. Check the logs.</div>'), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
