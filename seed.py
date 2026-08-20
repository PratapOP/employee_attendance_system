import os
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import psycopg2

load_dotenv()

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("Error: DATABASE_URL is not set in your .env file.")
    exit(1)

print("Connecting to database...")
conn = psycopg2.connect(db_url)

with conn, conn.cursor() as cur:
    print("Clearing old demo data...")
    cur.execute("""
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

    print("Creating enterprise users...")
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
            insert into users (emp_id, name, email, password_hash, role, department, designation, phone, is_active)
            values (%s, %s, %s, %s, %s, %s, %s, %s, true)
            returning id
        """, (emp_id, name, email, generate_password_hash(password), role, department, designation, phone))
        ids[emp_id] = cur.fetchone()[0]

    today = date.today()
    now_utc = datetime.now(timezone.utc)

    print("Populating historical and live attendance records...")
    # Past 5 days of attendance for EMP001-EMP005
    for emp_key in ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005']:
        uid = ids[emp_key]
        for days_ago in range(5, 0, -1):
            past_date = today - timedelta(days=days_ago)
            # Skip weekends
            if past_date.weekday() >= 5:
                continue
            punch_in_time = datetime(past_date.year, past_date.month, past_date.day, 9, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=(days_ago * 7) % 25)
            worked_hours = 7.5 + (days_ago % 3) * 0.5
            total_sec = int(worked_hours * 3600)
            punch_out_time = punch_in_time + timedelta(seconds=total_sec)
            
            cur.execute("""
                insert into attendance (employee_id, punch_in, punch_out, total_seconds, break_seconds, status, location_note, created_at)
                values (%s, %s, %s, %s, 1800, 'COMPLETED', 'HQ Office - Floor 4', %s)
                returning id
            """, (uid, punch_in_time, punch_out_time, total_sec, punch_in_time))
            att_id = cur.fetchone()[0]

            # Break record for that past day
            cur.execute("""
                insert into breaks (attendance_id, employee_id, break_type, start_time, end_time, total_seconds, notes)
                values (%s, %s, 'LUNCH', %s, %s, 1800, 'Team lunch')
            """, (att_id, uid, punch_in_time + timedelta(hours=4), punch_in_time + timedelta(hours=4, minutes=30)))

            # EOD Productivity report
            cur.execute("""
                insert into productivity_reports (employee_id, attendance_id, report_date, work_completed, progress, achievements, blockers, remaining_work, productivity_rating, notes)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (employee_id, report_date) do nothing
            """, (
                uid, att_id, past_date,
                f"Delivered milestones for corporate event roadmap. Coordinated with 3 vendor partners.",
                "Completed 90% of scheduled deliverables for the daily sprint.",
                "Approved stage lighting schedule & vendor contracts.",
                "None today - clear alignment across stakeholders.",
                "Review run-sheet tomorrow morning.",
                4 if days_ago % 2 == 0 else 5,
                "Smooth operational day."
            ))

    # Active live session today for EMP001 (Maya Chen)
    today_punch_in = datetime(today.year, today.month, today.day, 9, 15, 0, tzinfo=timezone.utc)
    cur.execute("""
        insert into attendance (employee_id, punch_in, status, location_note)
        values (%s, %s, 'WORKING', 'Main Stage Control Room')
        returning id
    """, (ids['EMP001'], today_punch_in))
    maya_att_id = cur.fetchone()[0]

    # Active session on break for EMP002 (Jordan Ellis)
    cur.execute("""
        insert into attendance (employee_id, punch_in, status, location_note)
        values (%s, %s, 'ON_BREAK', 'Partner Lounge')
        returning id
    """, (ids['EMP002'], today_punch_in - timedelta(minutes=15)))
    jordan_att_id = cur.fetchone()[0]

    cur.execute("""
        insert into breaks (attendance_id, employee_id, break_type, start_time, notes)
        values (%s, %s, 'LUNCH', %s, 'Sponsor lunch meeting')
    """, (jordan_att_id, ids['EMP002'], now_utc - timedelta(minutes=20)))

    # Completed session today for EMP003 (Samira Patel)
    cur.execute("""
        insert into attendance (employee_id, punch_in, punch_out, total_seconds, status, location_note)
        values (%s, %s, %s, %s, 'COMPLETED', 'Design Studio')
    """, (ids['EMP003'], today_punch_in - timedelta(hours=1), today_punch_in + timedelta(hours=5), 21600))

    print("Setting real-time activity status...")
    cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now(), 'ACTIVE')", (ids['EMP001'],))
    cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '2 minutes', 'ON_BREAK')", (ids['EMP002'],))
    cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '10 minutes', 'IDLE')", (ids['EMP003'],))
    cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now() - interval '45 minutes', 'OFFLINE')", (ids['EMP004'],))
    cur.execute("insert into activity (employee_id, last_activity, status) values (%s, now(), 'ACTIVE')", (ids['EMP005'],))

    print("Assigning realistic tasks...")
    sample_tasks = [
        (ids['EMP001'], 'Finalize VIP Hospitality Run-Sheet', 'Review artist hospitality riders and assign catering security staff.', 'HIGH', 'Logistics', today + timedelta(days=1), 'IN_PROGRESS'),
        (ids['EMP001'], 'Safety & Fire Marshal Inspection Walkthrough', 'Coordinate city inspector check at West Entrance.', 'URGENT', 'Compliance', today, 'TODO'),
        (ids['EMP001'], 'Audio Engineer Briefing', 'Confirm soundcheck timings and wireless frequencies.', 'MEDIUM', 'Technical', today - timedelta(days=1), 'COMPLETED'),
        (ids['EMP002'], 'Sponsorship Deck Distribution for Keynote', 'Send verified attendance statistics to title sponsors.', 'HIGH', 'Sponsorship', today + timedelta(days=2), 'IN_PROGRESS'),
        (ids['EMP002'], 'Contract Signoff for Beverage Partner', 'Ensure liability clauses are accepted by legal.', 'MEDIUM', 'Legal', today + timedelta(days=3), 'TODO'),
        (ids['EMP003'], 'Motion Graphics Render for Stage LED Screen', 'Final 4K renders for opening keynote sequence.', 'HIGH', 'Creative', today, 'TODO'),
        (ids['EMP003'], 'Wayfinding Signage Print Approval', 'Review physical proofs before high-volume batch print.', 'LOW', 'Creative', today - timedelta(days=2), 'COMPLETED'),
        (ids['EMP004'], 'Power Grid Load Testing on Main Stage', 'Test backup generators under full 3-phase load.', 'HIGH', 'Technical', today + timedelta(days=1), 'IN_PROGRESS'),
        (ids['EMP005'], 'Live Stream Social Announcement Blast', 'Schedule promo posts across LinkedIn, X, and Instagram.', 'MEDIUM', 'Marketing', today + timedelta(days=1), 'TODO')
    ]
    for emp_id, title, desc, prio, cat, due, stat in sample_tasks:
        cur.execute("""
            insert into tasks (employee_id, title, description, priority, category, due_date, status, completed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (emp_id, title, desc, prio, cat, due, stat, now_utc if stat == 'COMPLETED' else None))

    print("Seeding leave requests...")
    leaves_data = [
        (ids['EMP004'], 'PAID_TIME_OFF', today + timedelta(days=7), today + timedelta(days=10), 'Attending brother wedding in Chicago.', 'PENDING', None, None),
        (ids['EMP003'], 'REMOTE_WORK', today + timedelta(days=3), today + timedelta(days=4), 'Focus sprint on heavy graphic renders.', 'APPROVED', 'Approved. Please be online for 10am standup.', ids['ADMIN001']),
        (ids['EMP005'], 'CASUAL', today - timedelta(days=10), today - timedelta(days=9), 'Personal family errands.', 'APPROVED', 'Enjoy the time off.', ids['ADMIN001']),
    ]
    for emp_id, l_type, s_date, e_date, reason, status, mgr_cmt, reviewer in leaves_data:
        cur.execute("""
            insert into leaves (employee_id, leave_type, start_date, end_date, reason, status, manager_comment, reviewed_by, reviewed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (emp_id, l_type, s_date, e_date, reason, status, mgr_cmt, reviewer, now_utc if reviewer else None))

    print("Seeding notifications & audit logs...")
    cur.execute("""
        insert into notifications (employee_id, title, message, category, link, is_read)
        values
        (%s, 'Task Assigned: Safety Inspection', 'Avery Morgan assigned you an urgent task: Safety & Fire Marshal Inspection Walkthrough.', 'TASK', '/employee', false),
        (%s, 'Leave Request Approved', 'Your remote work request for next week was approved.', 'LEAVE', '/employee/leaves', true),
        (%s, 'Daily Attendance Logged', 'Your attendance record for yesterday was processed.', 'ATTENDANCE', '/employee/attendance', true)
    """, (ids['EMP001'], ids['EMP003'], ids['EMP001']))

    cur.execute("""
        insert into audit_logs (user_id, action, details, ip_address)
        values
        (%s, 'SYSTEM_SEED', 'Initial system seed executed with enterprise data.', '127.0.0.1'),
        (%s, 'USER_LOGIN', 'Admin authenticated from corporate network.', '192.168.1.100')
    """, (ids['ADMIN001'], ids['ADMIN001']))

print("\n Enterprise Seed Complete!")
print("Demo Accounts:")
print("  Director/Admin: ADMIN001 / Admin@123")
print("  Coordinator:    EMP001   / Employee@123")
print("  Partnerships:   EMP002   / Employee@123")
print("  Creative:       EMP003   / Employee@123")
print("  Tech Ops:       EMP004   / Employee@123")
print("  Marketing:      EMP005   / Employee@123")
