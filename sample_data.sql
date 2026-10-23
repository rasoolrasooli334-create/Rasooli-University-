INSERT INTO departments (department_code, department_name, office_location, phone, email) VALUES
('BUS','Business Administration','Building A, Room 101','0700000001','business@example.edu'),
('IT','Information Technology','Building B, Room 201','0700000002','it@example.edu'),
('ENG','Engineering','Building C, Room 301','0700000003','engineering@example.edu');

INSERT INTO programs (department_id, program_code, program_name, degree_level, duration_years) VALUES
(1,'BBA','Bachelor of Business Administration','Bachelor',4),
(1,'MBA','Master of Business Administration','Master',2),
(2,'BSIT','Bachelor of Science in Information Technology','Bachelor',4),
(3,'BENG','Bachelor of Engineering','Bachelor',4);

INSERT INTO instructors (employee_number, first_name, last_name, email, phone, department_id, hire_date) VALUES
('EMP-001','Amina','Ahmadi','amina.ahmadi@example.edu','0701000001',1,'2022-03-01'),
('EMP-002','Farid','Rahimi','farid.rahimi@example.edu','0701000002',2,'2021-09-15'),
('EMP-003','Laila','Noori','laila.noori@example.edu','0701000003',3,'2020-02-10');

INSERT INTO courses (course_code, course_title, credit_hours, department_id, description) VALUES
('BUS101','Introduction to Business',3,1,'Business fundamentals'),
('BUS201','Financial Accounting',3,1,'Principles of financial accounting'),
('IT101','Introduction to Programming',4,2,'Programming fundamentals'),
('ENG101','Engineering Mathematics',3,3,'Core mathematics for engineers');

INSERT INTO classrooms (building, room_number, capacity) VALUES
('Building A','101',40),
('Building B','201',35),
('Building C','301',45);

INSERT INTO students (student_number, first_name, last_name, date_of_birth, gender, email, phone, address, admission_date, program_id, status) VALUES
('STU-2026-001','Ahmad','Karimi','2004-05-12','Male','ahmad.karimi@example.edu','0702000001','Kabul','2026-03-01',1,'Active'),
('STU-2026-002','Maryam','Safai','2003-11-24','Female','maryam.safai@example.edu','0702000002','Kabul','2026-03-01',2,'Active'),
('STU-2026-003','Omid','Hussaini','2005-01-09','Male','omid.hussaini@example.edu','0702000003','Kabul','2026-03-02',3,'Active');

INSERT INTO course_offerings (course_id, instructor_id, academic_year, semester, section, classroom_id, start_date, end_date) VALUES
(1,1,'2026-2027','Fall','A',1,'2026-09-01','2027-01-15'),
(2,1,'2026-2027','Fall','A',1,'2026-09-01','2027-01-15'),
(3,2,'2026-2027','Fall','A',2,'2026-09-01','2027-01-15'),
(4,3,'2026-2027','Fall','A',3,'2026-09-01','2027-01-15');

INSERT INTO enrollments (student_id, offering_id, enrollment_date, grade, status) VALUES
(1,1,'2026-09-01',NULL,'Enrolled'),
(1,2,'2026-09-01',NULL,'Enrolled'),
(2,2,'2026-09-01',NULL,'Enrolled'),
(3,3,'2026-09-02',NULL,'Enrolled');

INSERT INTO class_sessions (offering_id, classroom_id, weekday, start_time, end_time) VALUES
(1,1,'Sunday','09:00','10:30'),
(2,1,'Tuesday','10:45','12:15'),
(3,2,'Monday','09:00','11:00'),
(4,3,'Wednesday','08:30','10:00');

INSERT INTO payments (student_id, amount, currency, payment_date, payment_type, reference_number, notes) VALUES
(1,15000,'AFN','2026-09-05','Tuition','PAY-2026-001','Sample payment'),
(2,200,'USD','2026-09-06','Registration','PAY-2026-002','Sample payment');
