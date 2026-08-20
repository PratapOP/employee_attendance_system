import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

db_url = os.getenv('DATABASE_URL', '')
is_sqlite = not db_url or db_url.startswith(('sqlite:', 'local')) or 'postgres' not in db_url

if not is_sqlite:
    try:
        import psycopg
        USE_PSYCOPG3 = True
    except ImportError:
        import psycopg2
        USE_PSYCOPG3 = False

today = date.today()
now_utc = datetime.now(timezone.utc)
now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')

def seed_database():
    if is_sqlite:
        print(" Seeding local SQLite database (workpulse.db)...")
        conn = sqlite3.connect('workpulse.db')
        # Load schema first
        if os.path.exists('database/schema_sqlite.sql'):
            with open('database/schema_sqlite.sql', 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
        
        conn.executescript("""
            delete from audit_logs;
            delete from notifications;
            delete from leaves;
            delete from breaks;
            delete from activity;
            delete from productivity_reports;
            delete from tasks;
            delete from attendance;
            delete from users;
        """)
        cur = conn.cursor()
        
        people = [
            ('ADMIN001', 'Avery Morgan', 'admin@workpulse.local', 'ADMIN', 'Executive Operations', 'Director of Operations', '+1 (555) 019-2834'),
            ('EMP001', 'Maya Chen', 'maya@workpulse.local', 'EMPLOYEE', 'Event Production', 'Senior Event Coordinator', '+1 (555) 014-9281'),
            ('EMP002', 'Jordan Ellis', 'jordan@workpulse.local', 'EMPLOYEE', 'Sponsorship & Brand', 'Partnerships Lead', '+1 (555) 018-3829'),
            ('EMP003', 'Samira Patel', 'samira@workpulse.local', 'EMPLOYEE', 'Creative & Design', 'Creative Producer', '+1 (555) 017-4820'),
            ('EMP004', 'Noah Williams', 'noah@workpulse.local', 'EMPLOYEE', 'Stage & Tech Ops', 'Technical Operations Specialist', '+1 (555) 012-9482'),
            ('EMP005', 'Riley Brooks', 'riley@workpulse.local', 'EMPLOYEE', 'Growth & Marketing', 'Brand Marketing Manager', '+1 (555) 016-5738'),
        ]

        ids = {}
        for emp_id, name, email, role, department, designation, phone in people:
            password = 'Admin@123' if role == 'ADMIN' else 'Employee@123'
            cur.execute("""
                insert into users (emp_id, name, email, password_hash, role, department, designation, phone, is_active, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (emp_id, name, email, generate_password_hash(password), role, department, designation, phone, now_str))
            ids[emp_id] = cur.lastrowid

        # Historical attendance
        for emp_key in ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005']:
            uid = ids[emp_key]
            for days_ago in range(5, 0, -1):
                past_date = today - timedelta(days=days_ago)
                if past_date.weekday() >= 5:
                    continue
                p_in = datetime(past_date.year, past_date.month, past_date.day, 9, 0, 0) + timedelta(minutes=(days_ago * 7) % 25)
                worked_sec = int((7.5 + (days_ago % 3) * 0.5) * 3600)
                p_out = p_in + timedelta(seconds=worked_sec)

                cur.execute("""
                    insert into attendance (employee_id, punch_in, punch_out, total_seconds, break_seconds, status, location_note, created_at)
                    values (?, ?, ?, ?, 1800, 'COMPLETED', 'HQ Office - Floor 4', ?)
                """, (uid, p_in.strftime('%Y-%m-%d %H:%M:%S'), p_out.strftime('%Y-%m-%d %H:%M:%S'), worked_sec, p_in.strftime('%Y-%m-%d %H:%M:%S')))
                att_id = cur.lastrowid

                cur.execute("""
                    insert into breaks (attendance_id, employee_id, break_type, start_time, end_time, total_seconds, notes, created_at)
                    values (?, ?, 'LUNCH', ?, ?, 1800, 'Team lunch', ?)
                """, (att_id, uid, (p_in + timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S'), (p_in + timedelta(hours=4, minutes=30)).strftime('%Y-%m-%d %H:%M:%S'), p_in.strftime('%Y-%m-%d %H:%M:%S')))

                cur.execute("""
                    insert into productivity_reports (employee_id, attendance_id, report_date, work_completed, progress, achievements, blockers, remaining_work, productivity_rating, notes, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (uid, att_id, past_date.strftime('%Y-%m-%d'), "Delivered daily milestone targets.", "On track for sprint.", "Aligned with stakeholders.", "None.", "Review run-sheet.", 5 if days_ago % 2 == 0 else 4, "Smooth shift.", p_out.strftime('%Y-%m-%d %H:%M:%S')))

        # Live today sessions
        today_in = datetime(today.year, today.month, today.day, 9, 15, 0).strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("insert into attendance (employee_id, punch_in, status, location_note) values (?, ?, 'WORKING', 'Main Stage Control Room')", (ids['EMP001'], today_in))
        
        cur.execute("insert into attendance (employee_id, punch_in, status, location_note) values (?, ?, 'ON_BREAK', 'Partner Lounge')", (ids['EMP002'], today_in))
        j_att = cur.lastrowid
        cur.execute("insert into breaks (attendance_id, employee_id, break_type, start_time, notes) values (?, ?, 'LUNCH', ?, 'Sponsor lunch')", (j_att, ids['EMP002'], (now_utc - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')))

        cur.execute("insert into attendance (employee_id, punch_in, punch_out, total_seconds, status, location_note) values (?, ?, ?, 21600, 'COMPLETED', 'Design Studio')", (ids['EMP003'], today_in, (now_utc - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')))

        # Activities
        cur.execute("insert into activity (employee_id, last_activity, status) values (?, ?, 'ACTIVE')", (ids['EMP001'], now_str))
        cur.execute("insert into activity (employee_id, last_activity, status) values (?, ?, 'ON_BREAK')", (ids['EMP002'], (now_utc - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')))
        cur.execute("insert into activity (employee_id, last_activity, status) values (?, ?, 'IDLE')", (ids['EMP003'], (now_utc - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')))
        cur.execute("insert into activity (employee_id, last_activity, status) values (?, ?, 'OFFLINE')", (ids['EMP004'], (now_utc - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S')))
        cur.execute("insert into activity (employee_id, last_activity, status) values (?, ?, 'ACTIVE')", (ids['EMP005'], now_str))

        # Tasks
        tasks_list = [
            (ids['EMP001'], 'Finalize VIP Hospitality Run-Sheet', 'Review artist hospitality riders.', 'HIGH', 'Logistics', (today + timedelta(days=1)).strftime('%Y-%m-%d'), 'IN_PROGRESS'),
            (ids['EMP001'], 'Safety & Fire Marshal Inspection', 'Coordinate inspector walkthrough.', 'URGENT', 'Compliance', today.strftime('%Y-%m-%d'), 'TODO'),
            (ids['EMP001'], 'Audio Engineer Briefing', 'Confirm soundcheck frequencies.', 'MEDIUM', 'Technical', (today - timedelta(days=1)).strftime('%Y-%m-%d'), 'COMPLETED'),
            (ids['EMP002'], 'Sponsorship Deck Distribution', 'Send verified stats to title sponsors.', 'HIGH', 'Sponsorship', (today + timedelta(days=2)).strftime('%Y-%m-%d'), 'IN_PROGRESS'),
            (ids['EMP003'], 'Motion Graphics Render for Stage', 'Final 4K renders for opening.', 'HIGH', 'Creative', today.strftime('%Y-%m-%d'), 'TODO'),
            (ids['EMP004'], 'Power Grid Load Testing', 'Test backup generators under load.', 'HIGH', 'Technical', (today + timedelta(days=1)).strftime('%Y-%m-%d'), 'IN_PROGRESS'),
            (ids['EMP005'], 'Live Stream Announcement Blast', 'Schedule promo posts.', 'MEDIUM', 'Marketing', (today + timedelta(days=1)).strftime('%Y-%m-%d'), 'TODO')
        ]
        for e_id, title, desc, prio, cat, due, stat in tasks_list:
            cur.execute("insert into tasks (employee_id, title, description, priority, category, due_date, status, completed_at) values (?, ?, ?, ?, ?, ?, ?, ?)", (e_id, title, desc, prio, cat, due, stat, now_str if stat == 'COMPLETED' else None))

        # Leaves
        cur.execute("insert into leaves (employee_id, leave_type, start_date, end_date, reason, status) values (?, 'PAID_TIME_OFF', ?, ?, 'Family wedding.', 'PENDING')", (ids['EMP004'], (today + timedelta(days=7)).strftime('%Y-%m-%d'), (today + timedelta(days=10)).strftime('%Y-%m-%d')))
        cur.execute("insert into leaves (employee_id, leave_type, start_date, end_date, reason, status, manager_comment, reviewed_by, reviewed_at) values (?, 'REMOTE_WORK', ?, ?, 'Graphic render sprint.', 'APPROVED', 'Approved.', ?, ?)", (ids['EMP003'], (today + timedelta(days=3)).strftime('%Y-%m-%d'), (today + timedelta(days=4)).strftime('%Y-%m-%d'), ids['ADMIN001'], now_str))

        # Notifications & Audit
        cur.execute("insert into notifications (employee_id, title, message, category, link, is_read) values (?, 'Task Assigned: Safety Inspection', 'Avery assigned you an urgent task.', 'TASK', '/employee', 0)", (ids['EMP001'],))
        cur.execute("insert into notifications (employee_id, title, message, category, link, is_read) values (%s, 'Leave Approved', 'Remote work request approved.', 'LEAVE', '/employee/leaves', 1)", (ids['EMP003'],))
        cur.execute("insert into audit_logs (user_id, action, details, ip_address) values (?, 'SYSTEM_SEED', 'Local SQLite seed initialized.', '127.0.0.1')", (ids['ADMIN001'],))

        conn.commit()
        conn.close()
        print(" SQLite demo database successfully populated!")

    else:
        print(f" Connecting to PostgreSQL ({db_url[:28]}...)...")
        conn = psycopg.connect(db_url) if USE_PSYCOPG3 else psycopg2.connect(db_url)
        with conn, conn.cursor() as cur:
            cur.execute("delete from audit_logs; delete from notifications; delete from leaves; delete from breaks; delete from activity; delete from productivity_reports; delete from tasks; delete from attendance; delete from users;")
            people = [
                ('ADMIN001', 'Avery Morgan', 'admin@workpulse.local', 'ADMIN', 'Executive Operations', 'Director of Operations', '+1 (555) 019-2834'),
                ('EMP001', 'Maya Chen', 'maya@workpulse.local', 'EMPLOYEE', 'Event Production', 'Senior Event Coordinator', '+1 (555) 014-9281'),
                ('EMP002', 'Jordan Ellis', 'jordan@workpulse.local', 'EMPLOYEE', 'Sponsorship & Brand', 'Partnerships Lead', '+1 (555) 018-3829'),
                ('EMP003', 'Samira Patel', 'samira@workpulse.local', 'EMPLOYEE', 'Creative & Design', 'Creative Producer', '+1 (555) 017-4820'),
                ('EMP004', 'Noah Williams', 'noah@workpulse.local', 'EMPLOYEE', 'Stage & Tech Ops', 'Technical Operations Specialist', '+1 (555) 012-9482'),
                ('EMP005', 'Riley Brooks', 'riley@workpulse.local', 'EMPLOYEE', 'Growth & Marketing', 'Brand Marketing Manager', '+1 (555) 016-5738'),
            ]
            ids = {}
            for emp_id, name, email, role, department, designation, phone in people:
                password = 'Admin@123' if role == 'ADMIN' else 'Employee@123'
                cur.execute("insert into users (emp_id, name, email, password_hash, role, department, designation, phone, is_active) values (%s, %s, %s, %s, %s, %s, %s, %s, true) returning id", (emp_id, name, email, generate_password_hash(password), role, department, designation, phone))
                ids[emp_id] = cur.fetchone()[0]

            for emp_key in ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005']:
                uid = ids[emp_key]
                for days_ago in range(5, 0, -1):
                    past_date = today - timedelta(days=days_ago)
                    if past_date.weekday() >= 5: continue
                    p_in = datetime(past_date.year, past_date.month, past_date.day, 9, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=(days_ago * 7) % 25)
                    worked_sec = int((7.5 + (days_ago % 3) * 0.5) * 3600)
                    cur.execute("insert into attendance (employee_id, punch_in, punch_out, total_seconds, break_seconds, status, location_note, created_at) values (%s, %s, %s, %s, 1800, 'COMPLETED', 'HQ Office - Floor 4', %s) returning id", (uid, p_in, p_in + timedelta(seconds=worked_sec), worked_sec, p_in))
                    att_id = cur.fetchone()[0]
                    cur.execute("insert into breaks (attendance_id, employee_id, break_type, start_time, end_time, total_seconds, notes) values (%s, %s, 'LUNCH', %s, %s, 1800, 'Team lunch')", (att_id, uid, p_in + timedelta(hours=4), p_in + timedelta(hours=4, minutes=30)))
                    cur.execute("insert into productivity_reports (employee_id, attendance_id, report_date, work_completed, progress, achievements, blockers, remaining_work, productivity_rating, notes) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict (employee_id, report_date) do nothing", (uid, att_id, past_date, "Delivered milestone targets.", "On track for sprint.", "Aligned with stakeholders.", "None.", "Review run-sheet.", 4 if days_ago % 2 == 0 else 5, "Smooth shift."))

            today_in = datetime(today.year, today.month, today.day, 9, 15, 0, tzinfo=timezone.utc)
            cur.execute("insert into attendance (employee_id, punch_in, status, location_note) values (%s, %s, 'WORKING', 'Main Stage Control Room')", (ids['EMP001'], today_in))
            cur.execute("insert into attendance (employee_id, punch_in, status, location_note) values (%s, %s, 'ON_BREAK', 'Partner Lounge') returning id", (ids['EMP002'], today_in))
            j_att = cur.fetchone()[0]
            cur.execute("insert into breaks (attendance_id, employee_id, break_type, start_time, notes) values (%s, %s, 'LUNCH', %s, 'Sponsor lunch')", (j_att, ids['EMP002'], now_utc - timedelta(minutes=20)))
            cur.execute("insert into attendance (employee_id, punch_in, punch_out, total_seconds, status, location_note) values (%s, %s, %s, 21600, 'COMPLETED', 'Design Studio')", (ids['EMP003'], today_in, today_in + timedelta(hours=6)))

            cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now(), 'ACTIVE')", (ids['EMP001'],))
            cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '2 minutes', 'ON_BREAK')", (ids['EMP002'],))
            cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '10 minutes', 'IDLE')", (ids['EMP003'],))
            cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '45 minutes', 'OFFLINE')", (ids['EMP004'],))
            cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now(), 'ACTIVE')", (ids['EMP005'],))

            tasks_list = [
                (ids['EMP001'], 'Finalize VIP Hospitality Run-Sheet', 'Review artist hospitality riders.', 'HIGH', 'Logistics', today + timedelta(days=1), 'IN_PROGRESS'),
                (ids['EMP001'], 'Safety & Fire Marshal Inspection', 'Coordinate inspector walkthrough.', 'URGENT', 'Compliance', today, 'TODO'),
                (ids['EMP001'], 'Audio Engineer Briefing', 'Confirm soundcheck frequencies.', 'MEDIUM', 'Technical', today - timedelta(days=1), 'COMPLETED'),
                (ids['EMP002'], 'Sponsorship Deck Distribution', 'Send verified stats to title sponsors.', 'HIGH', 'Sponsorship', today + timedelta(days=2), 'IN_PROGRESS'),
                (ids['EMP003'], 'Motion Graphics Render for Stage', 'Final 4K renders for opening.', 'HIGH', 'Creative', today, 'TODO'),
                (ids['EMP004'], 'Power Grid Load Testing', 'Test backup generators under load.', 'HIGH', 'Technical', today + timedelta(days=1), 'IN_PROGRESS'),
                (ids['EMP005'], 'Live Stream Announcement Blast', 'Schedule promo posts.', 'MEDIUM', 'Marketing', today + timedelta(days=1), 'TODO')
            ]
            for e_id, title, desc, prio, cat, due, stat in tasks_list:
                cur.execute("insert into tasks (employee_id, title, description, priority, category, due_date, status, completed_at) values (%s, %s, %s, %s, %s, %s, %s, %s)", (e_id, title, desc, prio, cat, due, stat, now_utc if stat == 'COMPLETED' else None))

            cur.execute("insert into leaves (employee_id, leave_type, start_date, end_date, reason, status) values (%s, 'PAID_TIME_OFF', %s, %s, 'Family wedding.', 'PENDING')", (ids['EMP004'], today + timedelta(days=7), today + timedelta(days=10)))
            cur.execute("insert into leaves (employee_id, leave_type, start_date, end_date, reason, status, manager_comment, reviewed_by, reviewed_at) values (%s, 'REMOTE_WORK', %s, %s, 'Graphic render sprint.', 'APPROVED', 'Approved.', %s, now())", (ids['EMP003'], today + timedelta(days=3), today + timedelta(days=4), ids['ADMIN001']))

            cur.execute("insert into notifications (employee_id, title, message, category, link, is_read) values (%s, 'Task Assigned: Safety Inspection', 'Avery assigned you an urgent task.', 'TASK', '/employee', false)", (ids['EMP001'],))
            cur.execute("insert into notifications (employee_id, title, message, category, link, is_read) values (%s, 'Leave Approved', 'Remote work request approved.', 'LEAVE', '/employee/leaves', true)", (ids['EMP003'],))
            cur.execute("insert into audit_logs (user_id, action, details, ip_address) values (%s, 'SYSTEM_SEED', 'PostgreSQL seed initialized.', '127.0.0.1')", (ids['ADMIN001'],))

            conn.commit()
            print(" PostgreSQL demo database successfully populated!")

if __name__ == '__main__':
    seed_database()
    print("\n Demo Accounts:")
    print("  Director/Admin: ADMIN001 / Admin@123")
    print("  Shift Lead:     EMP001   / Employee@123")
    print("  Partnerships:   EMP002   / Employee@123")
