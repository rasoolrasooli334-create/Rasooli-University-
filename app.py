import os
import sqlite3
from functools import wraps
from flask import (
    Flask, g, request, redirect,
    url_for, render_template_string, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "university.db")

# --------------------------------------------------
# Database
# --------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def table_exists(table):
    row = get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return row is not None


def table_columns(table):
    if not table_exists(table):
        return []
    return [row["name"] for row in get_db().execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()]


def find_table(candidates):
    for name in candidates:
        if table_exists(name):
            return name
    return None


def count_rows(table):
    if not table:
        return 0
    # Table names are selected from sqlite_master, not user input.
    return get_db().execute(
        f'SELECT COUNT(*) AS n FROM "{table}"'
    ).fetchone()["n"]


# --------------------------------------------------
# Login
# --------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Rasooli University</title>
<style>
* { box-sizing:border-box; }
body {
  margin:0; font-family:Arial,sans-serif;
  background:#f1f5f9; color:#172033;
}
header {
  background:#123b63; color:white; padding:18px;
}
header h1 { margin:0 0 8px; font-size:23px; }
nav { display:flex; gap:9px; flex-wrap:wrap; margin-top:12px; }
nav a {
  color:white; text-decoration:none; background:#24547d;
  padding:10px 12px; border-radius:6px;
}
main { max-width:1100px; margin:20px auto; padding:0 14px; }
.card {
  background:white; padding:18px; border-radius:10px;
  box-shadow:0 2px 8px #0000000d; margin-bottom:16px;
}
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
.number { font-size:28px; font-weight:bold; color:#123b63; }
label { display:block; font-weight:bold; margin:12px 0 5px; }
input,select,textarea {
  width:100%; padding:11px; border:1px solid #cbd5e1;
  border-radius:6px; font-size:16px;
}
button,.button {
  display:inline-block; background:#123b63; color:white;
  padding:11px 15px; border:0; border-radius:6px;
  text-decoration:none; cursor:pointer; margin-top:12px;
}
table { width:100%; border-collapse:collapse; background:white; }
th,td { text-align:left; padding:10px; border-bottom:1px solid #e2e8f0; }
th { background:#eaf0f6; }
.table-wrap { overflow-x:auto; }
.message { padding:12px; background:#dcfce7; border-radius:6px; margin-bottom:12px; }
small { color:#64748b; }
@media(max-width:600px) {
  header h1 { font-size:20px; }
  th,td { padding:8px; font-size:13px; }
}
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
<a href="{{ url_for('logout') }}">Log out</a>
</nav>
{% endif %}
</header>
<main>
{% for msg in get_flashed_messages() %}
<div class="message">{{ msg }}</div>
{% endfor %}
<h2>{{ title }}</h2>
{{ content|safe }}
</main>
</body>
</html>
"""


def page(title, content, **kwargs):
    return render_template_string(
        PAGE, title=title, content=content, **kwargs
    )


@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Read credentials securely from Render environment variables.
        admin_user = os.environ.get("ADMIN_USERNAME", "")
        admin_password = os.environ.get("ADMIN_PASSWORD", "")
        admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")

        valid_password = False

        # Option 1: Use a password stored in Render Environment.
        if admin_password:
            valid_password = (
                password == admin_password
            )

        # Option 2: Support the existing password-hash method.
        elif admin_hash:
            try:
                valid_password = check_password_hash(
                    admin_hash, password
                )
            except (ValueError, TypeError):
                valid_password = False

        if (
            admin_user
            and username == admin_user
            and valid_password
        ):
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))

        flash("Login failed. Please check your username and password.")

    content = """
    <div class="card">
      <p>Sign in to Rasooli University Management System.</p>

      <form method="post">
        <label>Username</label>
        <input
          name="username"
          required
          autocomplete="username"
        >

        <label>Password</label>
        <input
          type="password"
          name="password"
          required
          autocomplete="current-password"
        >

        <button type="submit">Sign in</button>
      </form>
    </div>
    """

    return page("Login", content)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Configure credentials using environment variables in Render.
        admin_user = os.environ.get("ADMIN_USERNAME")
        admin_hash = os.environ.get("ADMIN_PASSWORD_HASH")

        if (
            admin_user and admin_hash
            and username == admin_user
            and check_password_hash(admin_hash, password)
        ):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))

        flash("Login failed. Check your configured administrator credentials.")

    content = """
    <div class="card">
      <p>Sign in using the administrator credentials configured in Render.</p>
      <form method="post">
        <label>Username</label>
        <input name="username" required autocomplete="username">
        <label>Password</label>
        <input type="password" name="password" required autocomplete="current-password">
        <button type="submit">Sign in</button>
      </form>
      <p><small>Set ADMIN_USERNAME, ADMIN_PASSWORD_HASH and SECRET_KEY in Render environment variables.</small></p>
    </div>
    """
    return page("Login", content)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    student_table = find_table(["students", "student"])
    course_table = find_table(["courses", "course"])
    instructor_table = find_table(["instructors", "teachers", "instructor"])
    enrollment_table = find_table(["enrollments", "enrollment"])

    content = """
    <div class="cards">
      <div class="card"><div>Students</div><div class="number">{{ students }}</div></div>
      <div class="card"><div>Courses</div><div class="number">{{ courses }}</div></div>
      <div class="card"><div>Teachers</div><div class="number">{{ teachers }}</div></div>
      <div class="card"><div>Enrollments</div><div class="number">{{ enrollments }}</div></div>
    </div>
    <div class="card">
      <h3>Welcome, {{ username }}</h3>
      <p>Use the navigation menu to view your university records.</p>
      <p><strong>Database:</strong> university.db</p>
    </div>
    """
    return page(
        "Dashboard", content,
        students=count_rows(student_table),
        courses=count_rows(course_table),
        teachers=count_rows(instructor_table),
        enrollments=count_rows(enrollment_table),
        username=session.get("username", "Administrator")
    )


@app.route("/students")
@login_required
def students():
    db = get_db()
    table = find_table(["students", "student"])

    if not table:
        return page(
            "Students",
            '<div class="card">No students table was found. '
            'Check schema.sql and your database file.</div>'
        )

    columns = table_columns(table)
    rows = db.execute(f'SELECT * FROM "{table}" LIMIT 500').fetchall()

    headers = "".join(f"<th>{c}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{row[c] if row[c] is not None else ''}</td>"
            for c in columns
        ) + "</tr>"
        for row in rows
    )

    content = f"""
    <div class="card">
      <p>Showing up to 500 records from <strong>{table}</strong>.</p>
      <div class="table-wrap">
      <table><thead><tr>{headers}</tr></thead>
      <tbody>{body}</tbody></table>
      </div>
    </div>
    """
    return page("Students", content)


@app.route("/courses")
@login_required
def courses():
    db = get_db()
    table = find_table(["courses", "course"])

    if not table:
        return page(
            "Courses",
            '<div class="card">No courses table was found. Check schema.sql.</div>'
        )

    columns = table_columns(table)
    rows = db.execute(f'SELECT * FROM "{table}" LIMIT 500').fetchall()

    headers = "".join(f"<th>{c}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{row[c] if row[c] is not None else ''}</td>"
            for c in columns
        ) + "</tr>"
        for row in rows
    )

    content = f"""
    <div class="card">
      <div class="table-wrap">
      <table><thead><tr>{headers}</tr></thead>
      <tbody>{body}</tbody></table>
      </div>
    </div>
    """
    return page("Courses", content)


@app.route("/database")
@login_required
def database_info():
    db = get_db()
    tables = db.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    rows = ""
    for item in tables:
        name = item["name"]
        rows += (
            f"<tr><td>{name}</td>"
            f"<td>{count_rows(name)}</td></tr>"
        )

    content = f"""
    <div class="card">
      <p>Database file: <strong>university.db</strong></p>
      <div class="table-wrap">
      <table><thead><tr><th>Table</th><th>Records</th></tr></thead>
      <tbody>{rows}</tbody></table>
      </div>
      <p><strong>Backup reminder:</strong> Render's temporary filesystem may lose
      database changes after a restart or redeployment.</p>
    </div>
    """
    return page("Database Information", content)


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unexpected application error: %s", error)
    return "An internal error occurred. Check the Render logs.", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
