-- Example queries for university.db  (run: sqlite3 university.db < queries.sql)
.headers on
.mode column

-- 1. Student GPA ranking
SELECT student, program, credits_earned, gpa
FROM v_student_gpa
WHERE gpa IS NOT NULL
ORDER BY gpa DESC;

-- 2. Seats left in current-term sections
SELECT * FROM v_section_availability
WHERE term = (SELECT name FROM terms WHERE is_current = 1)
ORDER BY seats_free;

-- 3. Class roster for a section (change section_id)
SELECT st.student_id, st.first_name, st.last_name, st.email
FROM enrollments e JOIN students st USING (student_id)
WHERE e.section_id = 10 AND e.status = 'enrolled'
ORDER BY st.last_name;

-- 4. Full transcript for one student
SELECT term, course_code, course_title, credits, grade_letter
FROM v_student_transcript
WHERE student_id = 1 AND status = 'completed'
ORDER BY term, course_code;

-- 5. Students with unpaid tuition this term
SELECT student, fee, paid, balance
FROM v_tuition_balance
WHERE term = (SELECT name FROM terms WHERE is_current = 1) AND balance > 0
ORDER BY balance DESC;

-- 6. Students with attendance below 75%
SELECT * FROM v_attendance_summary WHERE attendance_pct < 75;

-- 7. Instructor workload per term
SELECT * FROM v_instructor_workload ORDER BY term, teaching_credits DESC;

-- 8. Average grade points per course
SELECT c.code, c.title, COUNT(*) AS n, ROUND(AVG(g.points), 2) AS avg_points
FROM enrollments e
JOIN sections s ON s.section_id = e.section_id
JOIN courses c ON c.course_id = s.course_id
JOIN grade_scale g ON g.letter = e.grade_letter
WHERE g.points IS NOT NULL
GROUP BY c.course_id
ORDER BY avg_points DESC;

-- 9. Students per program and department
SELECT d.name AS department, p.name AS program, COUNT(st.student_id) AS students
FROM programs p
JOIN departments d ON d.department_id = p.department_id
LEFT JOIN students st ON st.program_id = p.program_id
GROUP BY p.program_id
ORDER BY d.name;

-- 10. Weekly timetable for one student in the current term
SELECT m.weekday, m.start_time, m.end_time, c.code, c.title, r.room_number
FROM enrollments e
JOIN sections s ON s.section_id = e.section_id
JOIN terms t ON t.term_id = s.term_id AND t.is_current = 1
JOIN courses c ON c.course_id = s.course_id
JOIN section_meetings m ON m.section_id = s.section_id
LEFT JOIN rooms r ON r.room_id = s.room_id
WHERE e.student_id = 1 AND e.status = 'enrolled'
ORDER BY CASE m.weekday WHEN 'Sat' THEN 1 WHEN 'Sun' THEN 2 WHEN 'Mon' THEN 3
                        WHEN 'Tue' THEN 4 WHEN 'Wed' THEN 5 WHEN 'Thu' THEN 6 ELSE 7 END,
         m.start_time;
