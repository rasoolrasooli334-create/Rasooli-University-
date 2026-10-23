PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,           -- e.g. CS, EE
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    code          TEXT NOT NULL UNIQUE,          -- e.g. CS101
    title         TEXT NOT NULL,
    credits       INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 6),
    department_id INTEGER NOT NULL REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS semesters (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,             -- e.g. "2025-Spring"
    starts_on  TEXT NOT NULL,
    ends_on    TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1))
);

-- A "section" is what students actually enroll in (a course offering).
CREATE TABLE IF NOT EXISTS sections (
    id            INTEGER PRIMARY KEY,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    semester_id   INTEGER NOT NULL REFERENCES semesters(id),
    instructor_id INTEGER REFERENCES instructors(id),
    room          TEXT,
    schedule      TEXT,
    capacity      INTEGER NOT NULL DEFAULT 30 CHECK (capacity > 0),
    UNIQUE (course_id, semester_id, instructor_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    section_id  INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    enrolled_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    grade       TEXT CHECK (grade IN ('A','B','C','D','F','I','W')),
    UNIQUE (student_id, section_id)
);

-- Application login users (separate from student data).
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'admin'
        CHECK (role IN ('admin','staff','instructor')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes (the ones you will actually query by)
CREATE INDEX IF NOT EXISTS idx_students_department  ON students(department_id);
CREATE INDEX IF NOT EXISTS idx_students_status      ON students(status);
CREATE INDEX IF NOT EXISTS idx_instructors_dept     ON instructors(department_id);
CREATE INDEX IF NOT EXISTS idx_courses_department   ON courses(department_id);
CREATE INDEX IF NOT EXISTS idx_sections_semester    ON sections(semester_id);
CREATE INDEX IF NOT EXISTS idx_sections_instructor  ON sections(instructor_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student  ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_section  ON enrollments(section_id);

-- Convenience views
CREATE VIEW IF NOT EXISTS v_student_directory AS
SELECT s.id, s.student_no,
       s.first_name || ' ' || s.last_name AS full_name,
       s.email, d.code AS department, s.status
FROM students s
JOIN departments d ON d.id = s.department_id;

CREATE VIEW IF NOT EXISTS v_section_load AS
SELECT sec.id AS section_id, c.code AS course_code, c.title AS course_title,
       sem.name AS semester, COUNT(e.id) AS enrolled, sec.capacity
FROM sections sec
JOIN courses c       ON c.id  = sec.course_id
JOIN semesters sem   ON sem.id = sec.semester_id
LEFT JOIN enrollments e ON e.section_id = sec.id
GROUP BY sec.id;
