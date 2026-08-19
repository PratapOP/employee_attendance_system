import os
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import psycopg2

load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn, conn.cursor() as cur:
    cur.execute("delete from notifications; delete from activity; delete from productivity_reports; delete from tasks; delete from attendance; delete from users;")
    people = [('ADMIN001','Avery Morgan','admin@workpulse.local','ADMIN','Operations','Operations Lead'),('EMP001','Maya Chen','maya@workpulse.local','EMPLOYEE','Event Operations','Event Coordinator'),('EMP002','Jordan Ellis','jordan@workpulse.local','EMPLOYEE','Sponsorship','Partnerships Manager'),('EMP003','Samira Patel','samira@workpulse.local','EMPLOYEE','Creative','Creative Producer'),('EMP004','Noah Williams','noah@workpulse.local','EMPLOYEE','Production','Production Manager'),('EMP005','Riley Brooks','riley@workpulse.local','EMPLOYEE','Marketing','Marketing Specialist')]
    ids = {}
    for emp_id, name, email, role, department, designation in people:
        password = 'Admin@123' if role == 'ADMIN' else 'Employee@123'
        cur.execute("insert into users (emp_id,name,email,password_hash,role,department,designation) values (%s,%s,%s,%s,%s,%s,%s) returning id", (emp_id,name,email,generate_password_hash(password),role,department,designation))
        ids[emp_id] = cur.fetchone()[0]
    for index, emp_id in enumerate(['EMP001','EMP002','EMP003','EMP004','EMP005']):
        cur.execute("insert into activity (employee_id,last_activity,status) values (%s,now() - (%s || ' minutes')::interval,%s)", (ids[emp_id], index * 3, 'ACTIVE' if index < 3 else 'IDLE'))
        cur.execute("insert into tasks (employee_id,title,description,priority,due_date,status) values (%s,%s,%s,%s,%s,%s)", (ids[emp_id], ['Venue walkthrough','Sponsor follow-up','Stage moodboard','Vendor run sheet','Campaign recap'][index], 'Prepare the next event deliverable.', 'HIGH' if index == 0 else 'MEDIUM', date.today() + timedelta(days=index - 1), 'TODO' if index != 1 else 'COMPLETED'))
        cur.execute("insert into productivity_reports (employee_id,report_date,work_completed,progress,achievements,blockers,remaining_work,productivity_rating) values (%s,%s,%s,%s,%s,%s,%s,%s)", (ids[emp_id], date.today() - timedelta(days=1), 'Completed core event planning work.', 'On track for this week.', 'Aligned the team on next steps.', 'Waiting on one external reply.', 'Close remaining follow-ups.', 4))
print('Seed complete. Demo users are ready.')
