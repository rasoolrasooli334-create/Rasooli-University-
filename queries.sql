-- 1. List students with their program and department
SELECT s.student_number, s.first_name, s.last_name, p.program_name, d.department_name, s.status
FROM students s
JOIN programs p ON p.program_id = s.program_id
JOIN departments d ON d.department_id = p.department_id
ORDER BY s.last_name;

-- 2. Student roster for each course offering
SELECT c.course_code, c.course_title, co.academic_year, co.semester, co.section,
       s.student_number, s.first_name, s.last_name, e.status, e.grade
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN course_offerings co ON co.offering_id = e.offering_id
JOIN courses c ON c.course_id = co.course_id
ORDER BY c.course_code, s.last_name;

-- 3. Tuition/payment totals per student and currency
SELECT s.student_number, s.first_name, s.last_name, pay.currency, SUM(pay.amount) AS total_paid
FROM payments pay
JOIN students s ON s.student_id = pay.student_id
GROUP BY s.student_id, pay.currency
ORDER BY s.last_name;

-- 4. Number of active students by program
SELECT p.program_name, COUNT(*) AS active_students
FROM students s JOIN programs p ON p.program_id = s.program_id
WHERE s.status = 'Active'
GROUP BY p.program_id, p.program_name;

-- 5. Course schedule
SELECT c.course_code, c.course_title, cs.weekday, cs.start_time, cs.end_time,
       cl.building, cl.room_number, i.first_name || ' ' || i.last_name AS instructor
FROM class_sessions cs
JOIN course_offerings co ON co.offering_id = cs.offering_id
JOIN courses c ON c.course_id = co.course_id
JOIN instructors i ON i.instructor_id = co.instructor_id
LEFT JOIN classrooms cl ON cl.classroom_id = cs.classroom_id
ORDER BY cs.weekday, cs.start_time;
