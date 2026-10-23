PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_code TEXT NOT NULL UNIQUE,
    department_name TEXT NOT NULL UNIQUE,
    office_location TEXT,
    phone TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    program_code TEXT NOT NULL UNIQUE,
    program_name TEXT NOT NULL,
    degree_level TEXT NOT NULL CHECK (degree_level IN ('Certificate','Diploma','Bachelor','Master','Doctorate')),
    duration_years INTEGER NOT NULL CHECK (duration_years > 0),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT,
    gender TEXT CHECK (gender IN ('Female','Male','Other','Prefer not to say')),
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    admission_date TEXT NOT NULL,
    program_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Graduated','Suspended','Withdrawn')),
    FOREIGN KEY (program_id) REFERENCES programs(program_id)
);

CREATE TABLE IF NOT EXISTS instructors (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    department_id INTEGER NOT NULL,
    hire_date TEXT,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','On Leave','Inactive')),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    course_title TEXT NOT NULL,
    credit_hours INTEGER NOT NULL CHECK (credit_hours > 0),
    department_id INTEGER NOT NULL,
    description TEXT,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS classrooms (
    classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    building TEXT NOT NULL,
    room_number TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    UNIQUE (building, room_number)
);

CREATE TABLE IF NOT EXISTS course_offerings (
    offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    semester TEXT NOT NULL CHECK (semester IN ('Spring','Summer','Fall','Winter')),
    section TEXT NOT NULL DEFAULT 'A',
    classroom_id INTEGER,
    start_date TEXT,
    end_date TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
    UNIQUE (course_id, academic_year, semester, section)
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    offering_id INTEGER NOT NULL,
    enrollment_date TEXT NOT NULL,
    grade TEXT,
    status TEXT NOT NULL DEFAULT 'Enrolled' CHECK (status IN ('Enrolled','Completed','Dropped','Failed')),
    UNIQUE (student_id, offering_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (offering_id) REFERENCES course_offerings(offering_id)
);

CREATE TABLE IF NOT EXISTS class_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offering_id INTEGER NOT NULL,
    classroom_id INTEGER,
    weekday TEXT NOT NULL CHECK (weekday IN ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    FOREIGN KEY (offering_id) REFERENCES course_offerings(offering_id),
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'AFN' CHECK (currency IN ('AFN','USD')),
    payment_date TEXT NOT NULL,
    payment_type TEXT NOT NULL CHECK (payment_type IN ('Tuition','Registration','Library','Other')),
    reference_number TEXT UNIQUE,
    notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_students_program ON students(program_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_offering ON enrollments(offering_id);
CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);
