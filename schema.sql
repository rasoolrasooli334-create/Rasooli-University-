-- University Management Database (SQLite)
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- Reference / organisation
-- ---------------------------------------------------------------
CREATE TABLE buildings (
    building_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    address     TEXT
);

CREATE TABLE rooms (
    room_id     INTEGER PRIMARY KEY,
    building_id INTEGER NOT NULL REFERENCES buildings(building_id),
    room_number TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    room_type   TEXT NOT NULL DEFAULT 'classroom'
                CHECK (room_type IN ('classroom','lab','lecture_hall','seminar')),
    UNIQUE (building_id, room_number)
);

CREATE TABLE departments (
    department_id      INTEGER PRIMARY KEY,
    code               TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL UNIQUE,
    building_id        INTEGER REFERENCES buildings(building_id),
    head_instructor_id INTEGER REFERENCES instructors(instructor_id)
);

CREATE TABLE instructors (
    instructor_id INTEGER PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE CHECK (email LIKE '%_@_%'),
    phone         TEXT,
    department_id INTEGER NOT NULL REFERENCES departments(department_id),
    title         TEXT NOT NULL DEFAULT 'Lecturer'
                  CHECK (title IN ('Lecturer','Assistant Professor','Associate Professor','Professor')),
    hire_date     TEXT NOT NULL,
    salary        REAL CHECK (salary IS NULL OR salary >= 0),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

-- ---------------------------------------------------------------
-- Academic structure
-- ---------------------------------------------------------------
CREATE TABLE programs (
    program_id     INTEGER PRIMARY KEY,
    department_id  INTEGER NOT NULL REFERENCES departments(department_id),
    name           TEXT NOT NULL UNIQUE,
    degree_level   TEXT NOT NULL CHECK (degree_level IN ('Diploma','Bachelor','Master','PhD')),
    duration_years REAL NOT NULL CHECK (duration_years > 0),
    total_credits  INTEGER NOT NULL CHECK (total_credits > 0)
);

CREATE TABLE courses (
    course_id     INTEGER PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    credits       INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 8),
    department_id INTEGER NOT NULL REFERENCES departments(department_id),
    description   TEXT
);

CREATE TABLE course_prerequisites (
    course_id       INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    prerequisite_id INTEGER NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (course_id, prerequisite_id),
    CHECK (course_id <> prerequisite_id)
);

CREATE TABLE terms (
    term_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    CHECK (end_date > start_date)
);
-- At most one current term
CREATE UNIQUE INDEX ux_terms_one_current ON terms(is_current) WHERE is_current = 1;

CREATE TABLE sections (
    section_id     INTEGER PRIMARY KEY,
    course_id      INTEGER NOT NULL REFERENCES courses(course_id),
    term_id        INTEGER NOT NULL REFERENCES terms(term_id),
    instructor_id  INTEGER NOT NULL REFERENCES instructors(instructor_id),
    room_id        INTEGER REFERENCES rooms(room_id),
    section_number TEXT NOT NULL DEFAULT '01',
    capacity       INTEGER NOT NULL CHECK (capacity > 0),
    UNIQUE (course_id, term_id, section_number)
);

CREATE TABLE section_meetings (
    meeting_id INTEGER PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES sections(section_id) ON DELETE CASCADE,
    weekday    TEXT NOT NULL CHECK (weekday IN ('Sat','Sun','Mon','Tue','Wed','Thu','Fri')),
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    CHECK (end_time > start_time),
    UNIQUE (section_id, weekday, start_time)
);

-- ---------------------------------------------------------------
-- Students
-- ---------------------------------------------------------------
CREATE TABLE students (
    student_id     INTEGER PRIMARY KEY,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE CHECK (email LIKE '%_@_%'),
    phone          TEXT,
    date_of_birth  TEXT,
    gender         TEXT CHECK (gender IN ('F','M')),
    address        TEXT,
    program_id     INTEGER NOT NULL REFERENCES programs(program_id),
    admission_date TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','on_leave','graduated','withdrawn','suspended'))
);

CREATE TABLE grade_scale (
    letter TEXT PRIMARY KEY,
    points REAL            -- NULL = not counted in GPA (e.g. W)
);

CREATE TABLE enrollments (
    enrollment_id INTEGER PRIMARY KEY,
    student_id    INTEGER NOT NULL REFERENCES students(student_id),
    section_id    INTEGER NOT NULL REFERENCES sections(section_id),
    enrolled_on   TEXT NOT NULL DEFAULT (date('now')),
    status        TEXT NOT NULL DEFAULT 'enrolled'
                  CHECK (status IN ('enrolled','completed','withdrawn','failed')),
    grade_letter  TEXT REFERENCES grade_scale(letter),
    UNIQUE (student_id, section_id),
    CHECK (status <> 'completed' OR grade_letter IS NOT NULL)
);

CREATE TABLE attendance (
    attendance_id INTEGER PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES enrollments(enrollment_id) ON DELETE CASCADE,
    class_date    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('present','absent','late','excused')),
    UNIQUE (enrollment_id, class_date)
);

CREATE TABLE tuition_payments (
    payment_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    term_id    INTEGER NOT NULL REFERENCES terms(term_id),
    amount     REAL NOT NULL CHECK (amount > 0),
    paid_on    TEXT NOT NULL,
    method     TEXT NOT NULL CHECK (method IN ('cash','bank_transfer','card','mobile'))
);

CREATE TABLE tuition_fees (
    program_id INTEGER NOT NULL REFERENCES programs(program_id),
    term_id    INTEGER NOT NULL REFERENCES terms(term_id),
    amount     REAL NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (program_id, term_id)
);

-- ---------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------
CREATE INDEX ix_students_program    ON students(program_id);
CREATE INDEX ix_students_name       ON students(last_name, first_name);
CREATE INDEX ix_instructors_dept    ON instructors(department_id);
CREATE INDEX ix_courses_dept        ON courses(department_id);
CREATE INDEX ix_sections_term       ON sections(term_id);
CREATE INDEX ix_sections_instructor ON sections(instructor_id);
CREATE INDEX ix_enroll_section      ON enrollments(section_id);
CREATE INDEX ix_enroll_student      ON enrollments(student_id);
CREATE INDEX ix_payments_student    ON tuition_payments(student_id, term_id);

-- ---------------------------------------------------------------
-- Triggers (business rules)
-- ---------------------------------------------------------------
-- 1. A section cannot exceed its capacity
CREATE TRIGGER trg_enrollment_capacity
BEFORE INSERT ON enrollments
WHEN NEW.status IN ('enrolled','completed')
BEGIN
    SELECT RAISE(ABORT, 'Section is full')
    WHERE (SELECT COUNT(*) FROM enrollments
           WHERE section_id = NEW.section_id
             AND status IN ('enrolled','completed'))
          >= (SELECT capacity FROM sections WHERE section_id = NEW.section_id);
END;

-- 2. All prerequisites must be passed before enrolling
CREATE TRIGGER trg_enrollment_prerequisites
BEFORE INSERT ON enrollments
BEGIN
    SELECT RAISE(ABORT, 'Prerequisite not met')
    WHERE EXISTS (
        SELECT 1
        FROM sections s
        JOIN course_prerequisites cp ON cp.course_id = s.course_id
        WHERE s.section_id = NEW.section_id
          AND NOT EXISTS (
              SELECT 1
              FROM enrollments e
              JOIN sections s2 ON s2.section_id = e.section_id
              WHERE e.student_id = NEW.student_id
                AND s2.course_id = cp.prerequisite_id
                AND e.status = 'completed'
                AND e.grade_letter NOT IN ('F','W')
          )
    );
END;

-- 3. A student cannot take the same course twice in the same term
CREATE TRIGGER trg_enrollment_duplicate_course
BEFORE INSERT ON enrollments
BEGIN
    SELECT RAISE(ABORT, 'Already enrolled in this course this term')
    WHERE EXISTS (
        SELECT 1
        FROM enrollments e
        JOIN sections s_old ON s_old.section_id = e.section_id
        JOIN sections s_new ON s_new.section_id = NEW.section_id
        WHERE e.student_id = NEW.student_id
          AND e.status IN ('enrolled','completed')
          AND s_old.course_id = s_new.course_id
          AND s_old.term_id   = s_new.term_id
    );
END;

-- 4. Only active students may enrol
CREATE TRIGGER trg_enrollment_active_student
BEFORE INSERT ON enrollments
BEGIN
    SELECT RAISE(ABORT, 'Student is not active')
    WHERE (SELECT status FROM students WHERE student_id = NEW.student_id) <> 'active';
END;

-- 5. Room must be big enough for the section
CREATE TRIGGER trg_section_room_capacity
BEFORE INSERT ON sections
WHEN NEW.room_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Section capacity exceeds room capacity')
    WHERE NEW.capacity > (SELECT capacity FROM rooms WHERE room_id = NEW.room_id);
END;

-- ---------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------
CREATE VIEW v_student_transcript AS
SELECT st.student_id,
       st.first_name || ' ' || st.last_name AS student,
       t.name  AS term,
       c.code  AS course_code,
       c.title AS course_title,
       c.credits,
       e.status,
       e.grade_letter,
       g.points AS grade_points
FROM enrollments e
JOIN students st ON st.student_id = e.student_id
JOIN sections s  ON s.section_id  = e.section_id
JOIN courses c   ON c.course_id   = s.course_id
JOIN terms t     ON t.term_id     = s.term_id
LEFT JOIN grade_scale g ON g.letter = e.grade_letter;

CREATE VIEW v_student_gpa AS
SELECT st.student_id,
       st.first_name || ' ' || st.last_name AS student,
       p.name AS program,
       COALESCE(SUM(c.credits), 0) AS credits_earned,
       ROUND(SUM(g.points * c.credits) / SUM(c.credits), 2) AS gpa
FROM students st
JOIN programs p ON p.program_id = st.program_id
LEFT JOIN enrollments e ON e.student_id = st.student_id AND e.status = 'completed'
LEFT JOIN grade_scale g ON g.letter = e.grade_letter AND g.points IS NOT NULL
LEFT JOIN sections s ON s.section_id = e.section_id
LEFT JOIN courses c ON c.course_id = s.course_id AND g.points IS NOT NULL
GROUP BY st.student_id;

CREATE VIEW v_section_availability AS
SELECT s.section_id,
       t.name AS term,
       c.code AS course_code,
       c.title AS course_title,
       i.first_name || ' ' || i.last_name AS instructor,
       s.capacity,
       COUNT(e.enrollment_id) AS seats_taken,
       s.capacity - COUNT(e.enrollment_id) AS seats_free
FROM sections s
JOIN courses c     ON c.course_id = s.course_id
JOIN terms t       ON t.term_id = s.term_id
JOIN instructors i ON i.instructor_id = s.instructor_id
LEFT JOIN enrollments e ON e.section_id = s.section_id AND e.status IN ('enrolled','completed')
GROUP BY s.section_id;

CREATE VIEW v_instructor_workload AS
SELECT i.instructor_id,
       i.first_name || ' ' || i.last_name AS instructor,
       d.name AS department,
       t.name AS term,
       COUNT(DISTINCT s.section_id) AS sections_taught,
       SUM(c.credits) AS teaching_credits
FROM instructors i
JOIN departments d ON d.department_id = i.department_id
JOIN sections s    ON s.instructor_id = i.instructor_id
JOIN courses c     ON c.course_id = s.course_id
JOIN terms t       ON t.term_id = s.term_id
GROUP BY i.instructor_id, t.term_id;

CREATE VIEW v_tuition_balance AS
SELECT st.student_id,
       st.first_name || ' ' || st.last_name AS student,
       t.name AS term,
       f.amount AS fee,
       COALESCE((SELECT SUM(p.amount) FROM tuition_payments p
                 WHERE p.student_id = st.student_id AND p.term_id = t.term_id), 0) AS paid,
       f.amount - COALESCE((SELECT SUM(p.amount) FROM tuition_payments p
                 WHERE p.student_id = st.student_id AND p.term_id = t.term_id), 0) AS balance
FROM students st
JOIN tuition_fees f ON f.program_id = st.program_id
JOIN terms t        ON t.term_id = f.term_id
WHERE t.start_date >= st.admission_date OR t.is_current = 1;

CREATE VIEW v_attendance_summary AS
SELECT e.enrollment_id,
       st.first_name || ' ' || st.last_name AS student,
       c.code AS course_code,
       COUNT(*) AS sessions,
       SUM(a.status IN ('present','late')) AS attended,
       ROUND(100.0 * SUM(a.status IN ('present','late')) / COUNT(*), 1) AS attendance_pct
FROM attendance a
JOIN enrollments e ON e.enrollment_id = a.enrollment_id
JOIN students st   ON st.student_id = e.student_id
JOIN sections s    ON s.section_id = e.section_id
JOIN courses c     ON c.course_id = s.course_id
GROUP BY e.enrollment_id;
