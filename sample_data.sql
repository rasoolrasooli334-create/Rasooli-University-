PRAGMA foreign_keys = ON;

INSERT INTO buildings (building_id, name, address) VALUES
 (1, 'Science Block',  'Main Campus, Kabul'),
 (2, 'Business Block', 'Main Campus, Kabul'),
 (3, 'Humanities Hall','Main Campus, Kabul');

INSERT INTO rooms (room_id, building_id, room_number, capacity, room_type) VALUES
 (1, 1, '101', 40, 'classroom'),
 (2, 1, 'Lab-1', 25, 'lab'),
 (3, 2, '201', 45, 'lecture_hall'),
 (4, 2, '105', 30, 'classroom'),
 (5, 3, '010', 35, 'classroom');

INSERT INTO departments (department_id, code, name, building_id, head_instructor_id) VALUES
 (1, 'CS',   'Computer Science', 1, NULL),
 (2, 'MATH', 'Mathematics',      1, NULL),
 (3, 'BUS',  'Business Administration', 2, NULL),
 (4, 'ENG',  'English Language', 3, NULL);

INSERT INTO instructors (instructor_id, first_name, last_name, email, phone, department_id, title, hire_date, salary) VALUES
 (1, 'Nasrin',  'Rahimi',   'n.rahimi@uni.example',  '+93700000001', 1, 'Associate Professor', '2015-03-01', 1800),
 (2, 'Farid',   'Karimi',   'f.karimi@uni.example',  '+93700000002', 1, 'Assistant Professor', '2019-09-01', 1500),
 (3, 'Sohaila', 'Amini',    's.amini@uni.example',   '+93700000003', 2, 'Professor',           '2010-01-15', 2200),
 (4, 'Jawad',   'Noori',    'j.noori@uni.example',   '+93700000004', 3, 'Professor',           '2012-08-20', 2300),
 (5, 'Mina',    'Safi',     'm.safi@uni.example',    '+93700000005', 3, 'Lecturer',            '2021-02-10', 1200),
 (6, 'Daud',    'Stanikzai','d.stanikzai@uni.example','+93700000006', 4, 'Lecturer',           '2020-09-01', 1100);

UPDATE departments SET head_instructor_id = 1 WHERE department_id = 1;
UPDATE departments SET head_instructor_id = 3 WHERE department_id = 2;
UPDATE departments SET head_instructor_id = 4 WHERE department_id = 3;
UPDATE departments SET head_instructor_id = 6 WHERE department_id = 4;

INSERT INTO programs (program_id, department_id, name, degree_level, duration_years, total_credits) VALUES
 (1, 1, 'BSc Computer Science',   'Bachelor', 4, 128),
 (2, 3, 'BBA Business Administration', 'Bachelor', 4, 126),
 (3, 3, 'MBA',                    'Master',   2, 48),
 (4, 2, 'BSc Mathematics',        'Bachelor', 4, 124);

INSERT INTO courses (course_id, code, title, credits, department_id, description) VALUES
 (1,  'CS101',   'Introduction to Programming', 3, 1, 'Fundamentals of programming and problem solving'),
 (2,  'CS201',   'Data Structures',             3, 1, 'Lists, trees, graphs, algorithms'),
 (3,  'CS301',   'Database Systems',            3, 1, 'Relational model, SQL, normalization'),
 (4,  'MATH101', 'Calculus I',                  4, 2, 'Limits, derivatives, integrals'),
 (5,  'MATH201', 'Linear Algebra',              3, 2, 'Vectors, matrices, eigenvalues'),
 (6,  'BUS101',  'Principles of Management',    3, 3, 'Foundations of management'),
 (7,  'BUS201',  'Financial Accounting',        3, 3, 'Financial statements and reporting'),
 (8,  'BUS301',  'Islamic Banking and Finance', 3, 3, 'Principles and instruments of Islamic finance'),
 (9,  'ENG101',  'Academic Writing',            2, 4, 'Academic English and essay writing'),
 (10, 'STAT201', 'Statistics',                  3, 2, 'Probability and statistical inference');

INSERT INTO course_prerequisites (course_id, prerequisite_id) VALUES
 (2, 1), (3, 2), (5, 4), (8, 7), (10, 4);

INSERT INTO terms (term_id, name, start_date, end_date, is_current) VALUES
 (1, 'Fall 2025',   '2025-09-01', '2026-01-15', 0),
 (2, 'Spring 2026', '2026-02-15', '2026-06-30', 0),
 (3, 'Fall 2026',   '2026-09-01', '2027-01-15', 1);

INSERT INTO grade_scale (letter, points) VALUES
 ('A', 4.0), ('A-', 3.7), ('B+', 3.3), ('B', 3.0), ('B-', 2.7),
 ('C+', 2.3), ('C', 2.0), ('C-', 1.7), ('D', 1.0), ('F', 0.0), ('W', NULL);

INSERT INTO students (student_id, first_name, last_name, email, phone, date_of_birth, gender, address, program_id, admission_date, status) VALUES
 (1,  'Ahmad',   'Sadat',    'ahmad.sadat@student.example',   '+93790000001', '2005-04-12', 'M', 'Kabul District 4',  1, '2025-09-01', 'active'),
 (2,  'Fatima',  'Rezai',    'fatima.rezai@student.example',  '+93790000002', '2005-07-30', 'F', 'Kabul District 10', 1, '2025-09-01', 'active'),
 (3,  'Hamid',   'Wardak',   'hamid.wardak@student.example',  '+93790000003', '2004-11-02', 'M', 'Kabul District 6',  2, '2025-09-01', 'active'),
 (4,  'Zahra',   'Ahmadi',   'zahra.ahmadi@student.example',  '+93790000004', '2005-01-19', 'F', 'Kabul District 3',  2, '2025-09-01', 'active'),
 (5,  'Omar',    'Faizi',    'omar.faizi@student.example',    '+93790000005', '1996-06-25', 'M', 'Kabul District 12', 3, '2025-09-01', 'active'),
 (6,  'Maryam',  'Hashimi',  'maryam.hashimi@student.example','+93790000006', '2005-09-09', 'F', 'Kabul District 8',  4, '2025-09-01', 'active'),
 (7,  'Yusuf',   'Qaderi',   'yusuf.qaderi@student.example',  '+93790000007', '2004-12-14', 'M', 'Kabul District 5',  1, '2025-09-01', 'active'),
 (8,  'Laila',   'Naseri',   'laila.naseri@student.example',  '+93790000008', '2005-03-03', 'F', 'Kabul District 2',  2, '2025-09-01', 'active'),
 (9,  'Bilal',   'Mohmand',  'bilal.mohmand@student.example', '+93790000009', '2005-05-21', 'M', 'Kabul District 7',  4, '2025-09-01', 'active'),
 (10, 'Sara',    'Popal',    'sara.popal@student.example',    '+93790000010', '2008-08-08', 'F', 'Kabul District 9',  1, '2026-09-01', 'active');

INSERT INTO sections (section_id, course_id, term_id, instructor_id, room_id, section_number, capacity) VALUES
 -- Fall 2025
 (1,  1, 1, 1, 1, '01', 35),
 (2,  4, 1, 3, 3, '01', 40),
 (3,  6, 1, 4, 3, '01', 40),
 (4,  9, 1, 6, 5, '01', 30),
 (5,  7, 1, 5, 4, '01', 30),
 -- Spring 2026
 (6,  2, 2, 2, 1, '01', 35),
 (7,  5, 2, 3, 4, '01', 30),
 (8,  7, 2, 5, 4, '01', 30),
 (9, 10, 2, 3, 4, '01', 30),
 -- Fall 2026 (current)
 (10, 3, 3, 2, 1, '01', 35),
 (11, 8, 3, 4, 4, '01', 4),   -- small seminar: becomes full
 (12, 1, 3, 1, 2, '01', 25),
 (13, 4, 3, 3, 3, '01', 40);

INSERT INTO section_meetings (section_id, weekday, start_time, end_time) VALUES
 (1,  'Sat', '08:00', '09:30'), (1,  'Mon', '08:00', '09:30'),
 (2,  'Sat', '10:00', '11:30'), (2,  'Tue', '10:00', '11:30'),
 (3,  'Sun', '08:00', '09:30'), (3,  'Wed', '08:00', '09:30'),
 (4,  'Mon', '10:00', '11:30'),
 (5,  'Sun', '10:00', '11:30'), (5,  'Wed', '10:00', '11:30'),
 (6,  'Sat', '08:00', '09:30'), (6,  'Mon', '08:00', '09:30'),
 (7,  'Sun', '10:00', '11:30'), (7,  'Tue', '10:00', '11:30'),
 (8,  'Sat', '10:00', '11:30'), (8,  'Mon', '10:00', '11:30'),
 (9,  'Sun', '12:00', '13:30'), (9,  'Tue', '12:00', '13:30'),
 (10, 'Sat', '08:00', '09:30'), (10, 'Mon', '08:00', '09:30'),
 (11, 'Sun', '14:00', '15:30'), (11, 'Wed', '14:00', '15:30'),
 (12, 'Sat', '10:00', '11:30'), (12, 'Tue', '10:00', '11:30'),
 (13, 'Sun', '08:00', '09:30'), (13, 'Wed', '08:00', '09:30');

INSERT INTO tuition_fees (program_id, term_id, amount) VALUES
 (1,1,600),(1,2,600),(1,3,650),
 (2,1,550),(2,2,550),(2,3,600),
 (3,1,900),(3,2,900),(3,3,950),
 (4,1,500),(4,2,500),(4,3,550);

-- Enrollments are inserted in chronological order so the
-- prerequisite / capacity triggers see the right history.

-- Fall 2025 (completed)
INSERT INTO enrollments (student_id, section_id, enrolled_on, status, grade_letter) VALUES
 (1, 1, '2025-08-25', 'completed', 'A'),
 (1, 2, '2025-08-25', 'completed', 'B+'),
 (1, 4, '2025-08-25', 'completed', 'A-'),
 (2, 1, '2025-08-26', 'completed', 'A-'),
 (2, 2, '2025-08-26', 'completed', 'B'),
 (2, 4, '2025-08-26', 'completed', 'B+'),
 (3, 3, '2025-08-26', 'completed', 'B+'),
 (3, 5, '2025-08-26', 'completed', 'B'),
 (3, 4, '2025-08-26', 'completed', 'B'),
 (4, 3, '2025-08-27', 'completed', 'A'),
 (4, 5, '2025-08-27', 'completed', 'A-'),
 (5, 5, '2025-08-27', 'completed', 'B+'),
 (5, 3, '2025-08-27', 'completed', 'A-'),
 (6, 2, '2025-08-28', 'completed', 'A'),
 (6, 4, '2025-08-28', 'completed', 'A'),
 (7, 1, '2025-08-28', 'completed', 'B'),
 (7, 2, '2025-08-28', 'completed', 'C+'),
 (8, 3, '2025-08-29', 'completed', 'C+'),
 (8, 4, '2025-08-29', 'completed', 'B-'),
 (9, 2, '2025-08-29', 'completed', 'B'),
 (9, 4, '2025-08-29', 'completed', 'B+');

-- Spring 2026 (completed)
INSERT INTO enrollments (student_id, section_id, enrolled_on, status, grade_letter) VALUES
 (1, 6, '2026-02-08', 'completed', 'A-'),
 (1, 7, '2026-02-08', 'completed', 'B+'),
 (2, 6, '2026-02-09', 'completed', 'B+'),
 (2, 9, '2026-02-09', 'completed', 'B'),
 (7, 6, '2026-02-09', 'completed', 'C'),
 (6, 7, '2026-02-10', 'completed', 'A'),
 (6, 9, '2026-02-10', 'completed', 'A-'),
 (9, 7, '2026-02-10', 'completed', 'B'),
 (9, 9, '2026-02-10', 'withdrawn', 'W'),
 (8, 8, '2026-02-11', 'completed', 'B');

-- Bilal took leave after Spring 2026 (set after his history is loaded)
UPDATE students SET status = 'on_leave' WHERE student_id = 9;

-- Fall 2026 (current, in progress)
INSERT INTO enrollments (student_id, section_id, enrolled_on, status) VALUES
 (1, 10, '2026-08-25', 'enrolled'),
 (2, 10, '2026-08-25', 'enrolled'),
 (7, 10, '2026-08-26', 'enrolled'),
 (3, 11, '2026-08-26', 'enrolled'),
 (4, 11, '2026-08-26', 'enrolled'),
 (8, 11, '2026-08-27', 'enrolled'),
 (5, 11, '2026-08-27', 'enrolled'),
 (10, 12, '2026-08-28', 'enrolled'),
 (10, 13, '2026-08-28', 'enrolled');

WITH a(sid, secid, d, st) AS (VALUES
 (1, 10, '2026-09-05', 'present'), (1, 10, '2026-09-07', 'present'), (1, 10, '2026-09-12', 'late'),
 (2, 10, '2026-09-05', 'present'), (2, 10, '2026-09-07', 'absent'),  (2, 10, '2026-09-12', 'present'),
 (7, 10, '2026-09-05', 'absent'),  (7, 10, '2026-09-07', 'absent'),  (7, 10, '2026-09-12', 'present'),
 (3, 11, '2026-09-06', 'present'), (3, 11, '2026-09-09', 'present'),
 (5, 11, '2026-09-06', 'present'), (5, 11, '2026-09-09', 'excused'))
INSERT INTO attendance (enrollment_id, class_date, status)
SELECT e.enrollment_id, a.d, a.st
FROM a JOIN enrollments e ON e.student_id = a.sid AND e.section_id = a.secid;

INSERT INTO tuition_payments (student_id, term_id, amount, paid_on, method) VALUES
 (1, 3, 650, '2026-08-20', 'bank_transfer'),
 (2, 3, 300, '2026-08-21', 'cash'),
 (2, 3, 200, '2026-09-10', 'mobile'),
 (3, 3, 600, '2026-08-22', 'card'),
 (4, 3, 600, '2026-08-22', 'bank_transfer'),
 (5, 3, 950, '2026-08-23', 'bank_transfer'),
 (7, 3, 400, '2026-08-30', 'cash'),
 (10, 3, 650, '2026-08-28', 'mobile');
