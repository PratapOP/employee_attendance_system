import os
import csv
import io
from datetime import datetime, date, timedelta, timezone
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, session, url_for, Response, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'workpulse-corporate-dev-secret-key-2026')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('VERCEL') == '1' or os.getenv('FLASK_ENV') == 'production'
)

# Database Connection Helper
def get_db():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is missing.")
    # Support connection poolers and enforce SSL if in cloud
    if 'sslmode=' not in db_url and not db_url.startswith(('postgresql://localhost', 'postgresql://127.0.0.1')):
        db_url += ('&' if '?' in db_url else '?') + 'sslmode=require'
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)

def query(sql, params=(), one=False, commit=False):
    conn = None
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if commit:
                conn.commit()
                if one:
                    try:
                        return cur.fetchone()
                    except psycopg2.ProgrammingError:
                        return None
                return None
            return cur.fetchone() if one else cur.fetchall()
    except Exception as e:
        if conn and commit:
            conn.rollback()
        app.logger.error(f"Database query error: {e} | SQL: {sql} | Params: {params}")
        raise e
    finally:
        if conn:
            conn.close()

def log_audit(action, details=None, user_id=None):
    uid = user_id or session.get('user_id')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    try:
        query(
            "insert into audit_logs (user_id, action, details, ip_address) values (%s, %s, %s, %s)",
            (uid, action, details, ip),
            commit=True
        )
    except Exception as e:
        app.logger.warning(f"Failed to log audit event: {e}")

def create_notification(employee_id, title, message, category='SYSTEM', link=None):
    try:
        query(
            "insert into notifications (employee_id, title, message, category, link) values (%s, %s, %s, %s, %s)",
            (employee_id, title, message, category, link),
            commit=True
        )
    except Exception as e:
        app.logger.warning(f"Failed to create notification: {e}")

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    try:
        return query('select * from users where id=%s and is_active=true', (uid,), one=True)
    except Exception:
        return None

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            session.clear()
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped

def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get('role') != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

# Formatting Utilities
def fmt_seconds(seconds):
    seconds = max(0, int(seconds or 0))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def fmt_hours_decimal(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{round(seconds / 3600.0, 1)} hrs"

def row_duration(row):
    if not row:
        return '00:00:00'
    end = row.get('punch_out') or datetime.now(timezone.utc)
    start = row.get('punch_in')
    if not start:
        return '00:00:00'
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    diff = max(0, int((end - start).total_seconds()))
    # subtract breaks if not completed yet
    break_sec = row.get('break_seconds') or 0
    return fmt_seconds(max(0, diff - break_sec))

def hours_since(employee_id, start_date):
    """Calculate total worked seconds for an employee since a given start date."""
    res = query(
        "select coalesce(sum(total_seconds), 0) as seconds from attendance where employee_id=%s and punch_in >= %s",
        (employee_id, start_date),
        one=True
    )
    return fmt_seconds(res['seconds'] if res else 0)

@app.template_filter('duration')
def duration_filter(row):
    return row_duration(row)

@app.template_filter('format_seconds')
def format_seconds_filter(seconds):
    return fmt_seconds(seconds)

@app.template_filter('format_hours')
def format_hours_filter(seconds):
    return fmt_hours_decimal(seconds)

@app.context_processor
def inject_global_vars():
    unread_count = 0
    if session.get('user_id'):
        try:
            res = query(
                "select count(*) as count from notifications where employee_id=%s and is_read=false",
                (session['user_id'],),
                one=True
            )
            unread_count = res['count'] if res else 0
        except Exception:
            unread_count = 0
    return {
        'now_year': datetime.now().year,
        'unread_notifications': unread_count,
        'current_endpoint': request.endpoint
    }

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('dashboard'))
    
    db_configured = bool(os.getenv('DATABASE_URL'))
    
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip()
        password = request.form.get('password', '')
        
        try:
            user = query('select * from users where upper(emp_id)=upper(%s)', (emp_id,), one=True)
            if not user or not user['is_active'] or not check_password_hash(user['password_hash'], password):
                flash('Invalid credentials or inactive account.', 'error')
                return render_template('login.html', db_configured=db_configured), 401
            
            # Update last login
            query('update users set last_login=now() where id=%s', (user['id'],), commit=True)
            
            session.clear()
            session.update(
                user_id=user['id'],
                role=user['role'],
                name=user['name'],
                emp_id=user['emp_id'],
                department=user.get('department', 'Operations')
            )
            
            log_audit('USER_LOGIN', f"Signed in as {user['role']}", user['id'])
            
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        except Exception as e:
            app.logger.error(f"Login failure: {e}")
            flash('Database connection error. Please verify your DATABASE_URL configuration.', 'error')
            return render_template('login.html', db_configured=db_configured), 500

    return render_template('login.html', db_configured=db_configured)

@app.get('/logout')
def logout():
    if session.get('user_id'):
        log_audit('USER_LOGOUT', 'User signed out', session['user_id'])
    session.clear()
    flash('You have been securely signed out.', 'success')
    return redirect(url_for('login'))

@app.get('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('admin_dashboard' if session.get('role') == 'ADMIN' else 'employee_dashboard'))

# ==========================================
# EMPLOYEE WORKSPACE ROUTES
# ==========================================

@app.get('/employee')
@role_required('EMPLOYEE')
def employee_dashboard():
    user = current_user()
    today = date.today()
    
    # Active or today's latest attendance session
    attendance = query(
        'select * from attendance where employee_id=%s and punch_in::date=current_date order by punch_in desc limit 1',
        (user['id'],),
        one=True
    )
    
    # Active open break
    active_break = None
    if attendance:
        active_break = query(
            'select * from breaks where attendance_id=%s and end_time is null order by start_time desc limit 1',
            (attendance['id'],),
            one=True
        )
    
    # Today's completed breaks list
    today_breaks = []
    if attendance:
        today_breaks = query(
            'select * from breaks where attendance_id=%s order by start_time desc',
            (attendance['id'],)
        )
    
    # Tasks assigned
    tasks = query(
        "select * from tasks where employee_id=%s order by (status='COMPLETED'), priority='URGENT' desc, priority='HIGH' desc, due_date nulls last, created_at desc",
        (user['id'],)
    )
    unfinished_tasks = [t for t in tasks if t['status'] != 'COMPLETED']
    
    # Reports
    reports = query(
        'select * from productivity_reports where employee_id=%s order by report_date desc limit 5',
        (user['id'],)
    )
    
    # Activity
    activity = query('select * from activity where employee_id=%s', (user['id'],), one=True) or {'status': 'OFFLINE'}
    
    # Leave status summary
    pending_leaves = query(
        "select count(*) as count from leaves where employee_id=%s and status='PENDING'",
        (user['id'],),
        one=True
    )
    
    # Calculate worked hours
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    weekly_hours = hours_since(user['id'], start_of_week)
    monthly_hours = hours_since(user['id'], start_of_month)
    
    return render_template(
        'employee_dashboard.html',
        heading='My Operations Workspace',
        user=user,
        attendance=attendance,
        active_break=active_break,
        today_breaks=today_breaks,
        tasks=tasks,
        unfinished=unfinished_tasks,
        reports=reports,
        activity=activity,
        pending_leaves=pending_leaves['count'] if pending_leaves else 0,
        weekly_hours=weekly_hours,
        monthly_hours=monthly_hours,
        now=datetime.now()
    )

@app.post('/employee/punch-in')
@role_required('EMPLOYEE')
def punch_in():
    user = current_user()
    location_note = request.form.get('location_note', 'Web Portal').strip()
    try:
        query(
            "insert into attendance (employee_id, status, location_note) values (%s, 'WORKING', %s)",
            (user['id'], location_note),
            commit=True
        )
        query(
            "insert into activity (employee_id, last_activity, status, updated_at) values (%s, now(), 'ACTIVE', now()) on conflict (employee_id) do update set last_activity=now(), status='ACTIVE', updated_at=now()",
            (user['id'],),
            commit=True
        )
        log_audit('PUNCH_IN', f"Location: {location_note}")
        flash('You are punched in. Have a productive shift!', 'success')
    except psycopg2.errors.UniqueViolation:
        flash('You already have an active work session in progress.', 'error')
    except Exception as e:
        app.logger.error(f"Punch in error: {e}")
        flash('Could not record punch in. Please try again.', 'error')
    return redirect(url_for('employee_dashboard'))

@app.post('/employee/punch-out')
@role_required('EMPLOYEE')
def punch_out():
    user = current_user()
    attendance = query(
        'select * from attendance where employee_id=%s and punch_out is null order by punch_in desc limit 1',
        (user['id'],),
        one=True
    )
    if not attendance:
        flash('No active work session found to punch out.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    form = request.form
    try:
        with get_db() as conn, conn.cursor() as cur:
            # 1. Close any open break
            cur.execute(
                "update breaks set end_time=now(), total_seconds=extract(epoch from (now()-start_time))::integer where attendance_id=%s and end_time is null",
                (attendance['id'],)
            )
            # 2. Recalculate total break seconds
            cur.execute("select coalesce(sum(total_seconds), 0) as total_break from breaks where attendance_id=%s", (attendance['id'],))
            break_res = cur.fetchone()
            total_breaks = break_res['total_break'] if break_res else 0
            
            # 3. Complete attendance session
            cur.execute("""
                update attendance
                set punch_out = now(),
                    break_seconds = %s,
                    total_seconds = greatest(0, (extract(epoch from (now() - punch_in))::integer - %s)),
                    status = 'COMPLETED'
                where id = %s
            """, (total_breaks, total_breaks, attendance['id']))
            
            # 4. Upsert productivity report
            cur.execute("""
                insert into productivity_reports
                (employee_id, attendance_id, report_date, work_completed, progress, achievements, blockers, remaining_work, productivity_rating, notes)
                values (%s, %s, current_date, %s, %s, %s, %s, %s, %s, %s)
                on conflict (employee_id, report_date) do update set
                    attendance_id = excluded.attendance_id,
                    work_completed = excluded.work_completed,
                    progress = excluded.progress,
                    achievements = excluded.achievements,
                    blockers = excluded.blockers,
                    remaining_work = excluded.remaining_work,
                    productivity_rating = excluded.productivity_rating,
                    notes = excluded.notes
            """, (
                user['id'], attendance['id'],
                form.get('work_completed', '').strip(),
                form.get('progress', '').strip(),
                form.get('achievements', '').strip() or None,
                form.get('blockers', '').strip() or None,
                form.get('remaining_work', '').strip() or None,
                int(form.get('productivity_rating', 4)),
                form.get('notes', '').strip() or None
            ))
            
            # 5. Set activity status to OFFLINE
            cur.execute("update activity set status='OFFLINE', updated_at=now() where employee_id=%s", (user['id'],))
            conn.commit()
            
        log_audit('PUNCH_OUT', f"Session #{attendance['id']} ended with EOD report.")
        flash('Work session ended and daily report saved successfully.', 'success')
    except Exception as e:
        app.logger.error(f"Punch out error: {e}")
        flash('An error occurred during punch out. Please try again.', 'error')
    
    return redirect(url_for('employee_dashboard'))

@app.post('/employee/break/start')
@role_required('EMPLOYEE')
def break_start():
    user = current_user()
    attendance = query(
        'select * from attendance where employee_id=%s and punch_out is null order by punch_in desc limit 1',
        (user['id'],),
        one=True
    )
    if not attendance:
        flash('You must be punched in to take a break.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    break_type = request.form.get('break_type', 'LUNCH')
    notes = request.form.get('notes', '').strip() or None
    
    try:
        query(
            "insert into breaks (attendance_id, employee_id, break_type, notes) values (%s, %s, %s, %s)",
            (attendance['id'], user['id'], break_type, notes),
            commit=True
        )
        query("update attendance set status='ON_BREAK' where id=%s", (attendance['id'],), commit=True)
        query("update activity set status='ON_BREAK', updated_at=now() where employee_id=%s", (user['id'],), commit=True)
        
        log_audit('BREAK_START', f"Started {break_type}")
        flash(f'Break started ({break_type.replace("_", " ").title()}). Enjoy your pause!', 'success')
    except psycopg2.errors.UniqueViolation:
        flash('You are already on an active break.', 'error')
    except Exception as e:
        app.logger.error(f"Break start error: {e}")
        flash('Failed to start break.', 'error')
        
    return redirect(url_for('employee_dashboard'))

@app.post('/employee/break/end')
@role_required('EMPLOYEE')
def break_end():
    user = current_user()
    attendance = query(
        'select * from attendance where employee_id=%s and punch_out is null order by punch_in desc limit 1',
        (user['id'],),
        one=True
    )
    if not attendance:
        flash('No active work session found.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    try:
        with get_db() as conn, conn.cursor() as cur:
            # End open break
            cur.execute("""
                update breaks
                set end_time = now(),
                    total_seconds = extract(epoch from (now() - start_time))::integer
                where attendance_id = %s and end_time is null
            """, (attendance['id'],))
            
            # Recalculate total break duration
            cur.execute("select coalesce(sum(total_seconds), 0) as break_sum from breaks where attendance_id=%s", (attendance['id'],))
            break_sum = cur.fetchone()['break_sum']
            
            cur.execute("update attendance set status='WORKING', break_seconds=%s where id=%s", (break_sum, attendance['id']))
            cur.execute("update activity set status='ACTIVE', last_activity=now(), updated_at=now() where employee_id=%s", (user['id'],))
            conn.commit()
            
        log_audit('BREAK_END', f"Resumed work after break. Total breaks: {fmt_seconds(break_sum)}")
        flash('Welcome back! Work timer is actively running.', 'success')
    except Exception as e:
        app.logger.error(f"Break end error: {e}")
        flash('Failed to resume from break.', 'error')
        
    return redirect(url_for('employee_dashboard'))

@app.post('/employee/tasks/<int:task_id>/status')
@role_required('EMPLOYEE')
def update_task_status(task_id):
    user = current_user()
    new_status = request.form.get('status', 'COMPLETED')
    if new_status not in ('TODO', 'IN_PROGRESS', 'COMPLETED', 'BLOCKED'):
        flash('Invalid task status.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    completed_at_clause = ", completed_at=now()" if new_status == 'COMPLETED' else ", completed_at=null"
    query(
        f"update tasks set status=%s {completed_at_clause} where id=%s and employee_id=%s",
        (new_status, task_id, user['id']),
        commit=True
    )
    log_audit('TASK_STATUS_UPDATE', f"Task #{task_id} marked as {new_status}")
    flash(f'Task marked as {new_status.replace("_", " ").title()}.', 'success')
    return redirect(url_for('employee_dashboard'))

@app.get('/employee/attendance')
@role_required('EMPLOYEE')
def employee_attendance_history():
    user = current_user()
    selected_month = request.args.get('month', date.today().strftime('%Y-%m'))
    
    sql = """
        select a.*,
               coalesce((select sum(total_seconds) from breaks b where b.attendance_id = a.id), 0) as total_break_seconds
        from attendance a
        where a.employee_id = %s
          and to_char(a.punch_in, 'YYYY-MM') = %s
        order by a.punch_in desc
    """
    records = query(sql, (user['id'], selected_month))
    
    total_seconds_month = sum(r['total_seconds'] for r in records)
    total_break_month = sum(r.get('total_break_seconds', 0) for r in records)
    days_worked = len(records)
    
    return render_template(
        'employee_attendance.html',
        heading='My Attendance Timesheet',
        records=records,
        selected_month=selected_month,
        total_worked=fmt_seconds(total_seconds_month),
        total_breaks=fmt_seconds(total_break_month),
        days_worked=days_worked
    )

@app.route('/employee/leaves', methods=['GET', 'POST'])
@role_required('EMPLOYEE')
def employee_leaves():
    user = current_user()
    if request.method == 'POST':
        leave_type = request.form.get('leave_type', 'CASUAL')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason', '').strip()
        
        if not start_date or not end_date or not reason:
            flash('Start date, end date, and reason are required.', 'error')
        elif start_date > end_date:
            flash('End date cannot be earlier than start date.', 'error')
        else:
            try:
                query(
                    "insert into leaves (employee_id, leave_type, start_date, end_date, reason, status) values (%s, %s, %s, %s, %s, 'PENDING')",
                    (user['id'], leave_type, start_date, end_date, reason),
                    commit=True
                )
                log_audit('LEAVE_REQUEST', f"{leave_type} from {start_date} to {end_date}")
                flash('Your leave request has been submitted for management review.', 'success')
                return redirect(url_for('employee_leaves'))
            except Exception as e:
                app.logger.error(f"Leave request error: {e}")
                flash('Could not submit leave request.', 'error')
                
    leaves = query(
        """
        select l.*, u.name as reviewer_name
        from leaves l
        left join users u on u.id = l.reviewed_by
        where l.employee_id = %s
        order by l.created_at desc
        """,
        (user['id'],)
    )
    return render_template('employee_leaves.html', heading='Leave & Time Off', leaves=leaves)

@app.post('/employee/profile/password')
@login_required
def update_password():
    user = current_user()
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')
    
    if not check_password_hash(user['password_hash'], current_pw):
        flash('Current password is incorrect.', 'error')
    elif len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
    elif new_pw != confirm_pw:
        flash('New password and confirmation do not match.', 'error')
    else:
        query(
            "update users set password_hash=%s where id=%s",
            (generate_password_hash(new_pw), user['id']),
            commit=True
        )
        log_audit('PASSWORD_CHANGE', 'User updated password')
        flash('Password successfully updated.', 'success')
        
    return redirect(url_for('dashboard'))

# ==========================================
# ADMIN MANAGEMENT ROUTES
# ==========================================

@app.get('/admin')
@role_required('ADMIN')
def admin_dashboard():
    # Update stale activity statuses automatically
    query("""
        update activity
        set status = case
            when last_activity < now() - interval '30 minutes' then 'OFFLINE'
            when last_activity < now() - interval '5 minutes' then 'IDLE'
            else status
        end,
        updated_at = now()
    """, commit=True)
    
    # Real-time Team Pulse
    employees = query("""
        select u.*,
               coalesce(a.status, 'OFFLINE') as activity_status,
               a.last_activity,
               at.id as attendance_id,
               at.punch_in,
               at.status as attendance_status,
               coalesce(at.break_seconds, 0) as break_seconds,
               coalesce(
                   case
                       when at.punch_out is not null then at.total_seconds
                       when at.punch_in is not null then greatest(0, extract(epoch from (now() - at.punch_in))::integer - coalesce(at.break_seconds, 0))
                       else 0
                   end, 0
               ) as seconds,
               coalesce(t.total_tasks, 0) as total_tasks,
               coalesce(t.completed_tasks, 0) as completed_tasks,
               coalesce(curr_t.title, 'No active task') as current_task
        from users u
        left join activity a on a.employee_id = u.id
        left join lateral (
            select * from attendance
            where employee_id = u.id and punch_in::date = current_date
            order by punch_in desc limit 1
        ) at on true
        left join lateral (
            select count(*) as total_tasks,
                   count(*) filter (where status = 'COMPLETED') as completed_tasks
            from tasks where employee_id = u.id
        ) t on true
        left join lateral (
            select title from tasks
            where employee_id = u.id and status in ('IN_PROGRESS', 'TODO')
            order by priority = 'URGENT' desc, priority = 'HIGH' desc, due_date nulls last limit 1
        ) curr_t on true
        where u.role = 'EMPLOYEE' and u.is_active = true
        order by u.name
    """)
    
    for row in employees:
        row['working_time'] = fmt_seconds(row['seconds'])
        row['last_activity_fmt'] = row['last_activity'].strftime('%I:%M %p') if row['last_activity'] else 'Never'
    
    # Overview Stats
    stats = query("""
        select
            count(*) filter (where role = 'EMPLOYEE' and is_active) as total_employees,
            count(*) filter (where role = 'EMPLOYEE' and is_active and a.status = 'ACTIVE') as working,
            count(*) filter (where role = 'EMPLOYEE' and is_active and a.status = 'ON_BREAK') as on_break,
            count(*) filter (where role = 'EMPLOYEE' and is_active and a.status = 'IDLE') as idle,
            count(*) filter (where role = 'EMPLOYEE' and is_active and (a.status = 'OFFLINE' or a.status is null)) as offline,
            coalesce((select sum(total_seconds) from attendance where punch_in::date = current_date), 0) as hours_today,
            (select count(*) from leaves where status = 'PENDING') as pending_leaves
        from users u
        left join activity a on a.employee_id = u.id
    """, one=True)
    
    stats['hours_today_fmt'] = fmt_hours_decimal(stats['hours_today'])
    
    # Task completion breakdown
    task_stats = query("""
        select
            count(*) filter (where status = 'COMPLETED') as completed,
            count(*) filter (where status = 'IN_PROGRESS') as in_progress,
            count(*) filter (where status = 'TODO') as todo,
            count(*) filter (where status = 'BLOCKED') as blocked
        from tasks
    """, one=True)
    
    # Hours by Department & Employee
    chart = query("""
        select u.name,
               u.department,
               round(coalesce(sum(a.total_seconds), 0) / 3600.0, 1) as hours
        from users u
        left join attendance a on a.employee_id = u.id and a.punch_in::date >= current_date - interval '7 days'
        where u.role = 'EMPLOYEE' and u.is_active = true
        group by u.name, u.department
        order by hours desc
    """)
    
    return render_template(
        'admin_dashboard.html',
        heading='Executive Operations Overview',
        stats=stats,
        employees=employees,
        chart_data={
            'completed': task_stats['completed'] or 0,
            'in_progress': task_stats['in_progress'] or 0,
            'todo': task_stats['todo'] or 0,
            'blocked': task_stats['blocked'] or 0,
            'names': [r['name'] for r in chart],
            'hours': [float(r['hours']) for r in chart]
        }
    )

@app.get('/admin/attendance')
@role_required('ADMIN')
def admin_attendance():
    employee = request.args.get('employee', '')
    selected_date = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    
    sql = """
        select a.*, u.name, u.emp_id, u.department
        from attendance a
        join users u on u.id = a.employee_id
        where 1=1
    """
    params = []
    if employee:
        sql += " and u.id = %s"
        params.append(employee)
    if selected_date:
        sql += " and a.punch_in::date = %s"
        params.append(selected_date)
    if status_filter:
        sql += " and a.status = %s"
        params.append(status_filter)
        
    sql += " order by a.punch_in desc limit 250"
    
    records = query(sql, params)
    employees = query("select id, name, emp_id from users where role='EMPLOYEE' order by name")
    
    return render_template(
        'admin_attendance.html',
        heading='Workforce Attendance Records',
        records=records,
        employees=employees,
        filters={'employee': employee, 'date': selected_date, 'status': status_filter}
    )

@app.get('/admin/export/attendance')
@role_required('ADMIN')
def export_attendance_csv():
    employee = request.args.get('employee', '')
    selected_date = request.args.get('date', '')
    
    sql = """
        select a.id, u.emp_id, u.name, u.department,
               a.punch_in, a.punch_out, a.break_seconds, a.total_seconds,
               a.status, a.location_note
        from attendance a
        join users u on u.id = a.employee_id
        where 1=1
    """
    params = []
    if employee:
        sql += " and u.id = %s"
        params.append(employee)
    if selected_date:
        sql += " and a.punch_in::date = %s"
        params.append(selected_date)
    sql += " order by a.punch_in desc"
    
    rows = query(sql, params)
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Session ID', 'Employee ID', 'Name', 'Department', 'Punch In', 'Punch Out', 'Break Duration', 'Total Worked Hours', 'Status', 'Location Note'])
    
    for r in rows:
        cw.writerow([
            r['id'],
            r['emp_id'],
            r['name'],
            r['department'],
            r['punch_in'].strftime('%Y-%m-%d %H:%M:%S') if r['punch_in'] else '',
            r['punch_out'].strftime('%Y-%m-%d %H:%M:%S') if r['punch_out'] else 'IN PROGRESS',
            fmt_seconds(r['break_seconds']),
            fmt_seconds(r['total_seconds']),
            r['status'],
            r['location_note'] or ''
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_export_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/employees', methods=['GET', 'POST'])
@role_required('ADMIN')
def admin_employees():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            emp_id = request.form.get('emp_id', '').strip()
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip() or None
            password = request.form.get('password', 'Employee@123')
            department = request.form.get('department', 'Operations').strip()
            designation = request.form.get('designation', 'Coordinator').strip()
            phone = request.form.get('phone', '').strip() or None
            
            try:
                query("""
                    insert into users (emp_id, name, email, password_hash, role, department, designation, phone, is_active)
                    values (%s, %s, %s, %s, 'EMPLOYEE', %s, %s, %s, true)
                """, (emp_id, name, email, generate_password_hash(password), department, designation, phone), commit=True)
                
                log_audit('CREATE_EMPLOYEE', f"Created employee {emp_id} - {name}")
                flash(f'Employee {name} ({emp_id}) added successfully.', 'success')
            except psycopg2.errors.UniqueViolation:
                flash(f'Employee ID {emp_id} or email already exists in the system.', 'error')
            except Exception as e:
                app.logger.error(f"Create employee error: {e}")
                flash('Failed to create employee.', 'error')
                
        elif action == 'toggle':
            user_id = request.form.get('user_id')
            query("update users set is_active = not is_active where id=%s and role='EMPLOYEE'", (user_id,), commit=True)
            log_audit('TOGGLE_EMPLOYEE_STATUS', f"Toggled status for user #{user_id}")
            flash('Employee access state toggled.', 'success')
            
        elif action == 'reset_password':
            user_id = request.form.get('user_id')
            new_password = request.form.get('new_password', 'Employee@123')
            query("update users set password_hash=%s where id=%s and role='EMPLOYEE'", (generate_password_hash(new_password), user_id), commit=True)
            log_audit('RESET_PASSWORD', f"Reset password for user #{user_id}")
            flash('Employee password reset successfully.', 'success')
            
        return redirect(url_for('admin_employees'))
        
    search = request.args.get('q', '').strip()
    dept = request.args.get('dept', '').strip()
    
    sql = "select * from users where role='EMPLOYEE'"
    params = []
    if search:
        sql += " and (upper(name) like upper(%s) or upper(emp_id) like upper(%s) or upper(email) like upper(%s))"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if dept:
        sql += " and department = %s"
        params.append(dept)
    sql += " order by is_active desc, name"
    
    employees = query(sql, params)
    departments = query("select distinct department from users where department is not null and role='EMPLOYEE' order by department")
    
    return render_template(
        'admin_employees.html',
        heading='Workforce Directory & Access',
        employees=employees,
        departments=[d['department'] for d in departments],
        search=search,
        selected_dept=dept
    )

@app.get('/admin/export/employees')
@role_required('ADMIN')
def export_employees_csv():
    employees = query("select emp_id, name, email, department, designation, phone, is_active, created_at, last_login from users where role='EMPLOYEE' order by name")
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Employee ID', 'Name', 'Email', 'Department', 'Designation', 'Phone', 'Status', 'Joined Date', 'Last Login'])
    for e in employees:
        cw.writerow([
            e['emp_id'], e['name'], e['email'] or '', e['department'] or '', e['designation'] or '', e['phone'] or '',
            'ACTIVE' if e['is_active'] else 'INACTIVE',
            e['created_at'].strftime('%Y-%m-%d') if e['created_at'] else '',
            e['last_login'].strftime('%Y-%m-%d %H:%M:%S') if e['last_login'] else 'Never'
        ])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=workforce_directory_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/tasks', methods=['GET', 'POST'])
@role_required('ADMIN')
def admin_tasks():
    if request.method == 'POST':
        action = request.form.get('action', 'create')
        if action == 'create':
            emp_id = request.form.get('employee_id')
            title = request.form.get('title', '').strip()
            desc = request.form.get('description', '').strip() or None
            priority = request.form.get('priority', 'MEDIUM')
            category = request.form.get('category', 'General').strip()
            due_date = request.form.get('due_date') or None
            
            if not title or not emp_id:
                flash('Task title and assignee are required.', 'error')
            else:
                try:
                    query("""
                        insert into tasks (employee_id, title, description, priority, category, due_date, status)
                        values (%s, %s, %s, %s, %s, %s, 'TODO')
                    """, (emp_id, title, desc, priority, category, due_date), commit=True)
                    
                    create_notification(
                        emp_id,
                        f"New Task Assigned: {title}",
                        f"Priority: {priority}. Due: {due_date or 'No deadline'}",
                        category='TASK',
                        link='/employee'
                    )
                    log_audit('ASSIGN_TASK', f"Assigned task '{title}' to user #{emp_id}")
                    flash('Task successfully assigned to employee.', 'success')
                except Exception as e:
                    app.logger.error(f"Task creation error: {e}")
                    flash('Failed to assign task.', 'error')
        return redirect(url_for('admin_tasks'))
        
    status_filter = request.args.get('status', '')
    employee_filter = request.args.get('employee', '')
    
    sql = """
        select t.*, u.name as employee_name, u.emp_id, u.department
        from tasks t
        join users u on u.id = t.employee_id
        where 1=1
    """
    params = []
    if status_filter:
        sql += " and t.status = %s"
        params.append(status_filter)
    if employee_filter:
        sql += " and t.employee_id = %s"
        params.append(employee_filter)
    sql += " order by (t.status='COMPLETED'), t.priority='URGENT' desc, t.priority='HIGH' desc, t.due_date nulls last, t.created_at desc limit 200"
    
    tasks = query(sql, params)
    employees = query("select id, name, emp_id from users where role='EMPLOYEE' and is_active=true order by name")
    
    return render_template(
        'admin_tasks.html',
        heading='Task & Deliverables Dispatch',
        tasks=tasks,
        employees=employees,
        filters={'status': status_filter, 'employee': employee_filter}
    )

@app.post('/admin/tasks/<int:task_id>/delete')
@role_required('ADMIN')
def admin_delete_task(task_id):
    query("delete from tasks where id=%s", (task_id,), commit=True)
    log_audit('DELETE_TASK', f"Deleted task #{task_id}")
    flash('Task deleted.', 'success')
    return redirect(url_for('admin_tasks'))

@app.get('/admin/reports')
@role_required('ADMIN')
def admin_reports():
    date_filter = request.args.get('date', '')
    emp_filter = request.args.get('employee', '')
    
    sql = """
        select p.*, u.name, u.emp_id, u.department
        from productivity_reports p
        join users u on u.id = p.employee_id
        where 1=1
    """
    params = []
    if date_filter:
        sql += " and p.report_date = %s"
        params.append(date_filter)
    if emp_filter:
        sql += " and u.id = %s"
        params.append(emp_filter)
    sql += " order by p.report_date desc, p.created_at desc limit 200"
    
    reports = query(sql, params)
    employees = query("select id, name, emp_id from users where role='EMPLOYEE' order by name")
    
    return render_template(
        'admin_reports.html',
        heading='Daily EOD Standup Reports',
        reports=reports,
        employees=employees,
        filters={'date': date_filter, 'employee': emp_filter}
    )

@app.get('/admin/export/reports')
@role_required('ADMIN')
def export_reports_csv():
    reports = query("""
        select p.report_date, u.emp_id, u.name, u.department,
               p.work_completed, p.progress, p.achievements, p.blockers,
               p.remaining_work, p.productivity_rating, p.notes, p.created_at
        from productivity_reports p
        join users u on u.id = p.employee_id
        order by p.report_date desc
    """)
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Report Date', 'Employee ID', 'Name', 'Department', 'Work Completed', 'Progress', 'Achievements', 'Blockers', 'Remaining Work', 'Rating (1-5)', 'Notes', 'Submitted At'])
    for r in reports:
        cw.writerow([
            r['report_date'], r['emp_id'], r['name'], r['department'],
            r['work_completed'], r['progress'], r['achievements'] or '', r['blockers'] or '',
            r['remaining_work'] or '', r['productivity_rating'], r['notes'] or '',
            r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else ''
        ])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=productivity_reports_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/leaves', methods=['GET'])
@role_required('ADMIN')
def admin_leaves():
    leaves = query("""
        select l.*, u.name as employee_name, u.emp_id, u.department,
               rev.name as reviewer_name
        from leaves l
        join users u on u.id = l.employee_id
        left join users rev on rev.id = l.reviewed_by
        order by (l.status='PENDING') desc, l.start_date desc
    """)
    return render_template('admin_leaves.html', heading='Leave Approval Queue', leaves=leaves)

@app.post('/admin/leaves/<int:leave_id>/action')
@role_required('ADMIN')
def admin_leave_action(leave_id):
    action = request.form.get('action') # 'APPROVED' or 'REJECTED'
    comment = request.form.get('manager_comment', '').strip() or None
    admin_user = current_user()
    
    if action not in ('APPROVED', 'REJECTED'):
        flash('Invalid leave action.', 'error')
        return redirect(url_for('admin_leaves'))
    
    leave = query("select * from leaves where id=%s", (leave_id,), one=True)
    if not leave:
        flash('Leave request not found.', 'error')
        return redirect(url_for('admin_leaves'))
        
    query("""
        update leaves
        set status = %s,
            manager_comment = %s,
            reviewed_by = %s,
            reviewed_at = now()
        where id = %s
    """, (action, comment, admin_user['id'], leave_id), commit=True)
    
    create_notification(
        leave['employee_id'],
        f"Leave Request {action.title()}",
        f"Your {leave['leave_type'].replace('_', ' ').title()} request from {leave['start_date']} to {leave['end_date']} has been {action.lower()}. Comment: {comment or 'None'}",
        category='LEAVE',
        link='/employee/leaves'
    )
    
    log_audit('REVIEW_LEAVE', f"Marked leave #{leave_id} as {action}")
    flash(f"Leave request marked as {action.title()}.", 'success')
    return redirect(url_for('admin_leaves'))

@app.get('/admin/audit')
@role_required('ADMIN')
def admin_audit():
    logs = query("""
        select a.*, u.name, u.emp_id, u.role
        from audit_logs a
        left join users u on u.id = a.user_id
        order by a.created_at desc limit 200
    """)
    return render_template('admin_audit.html', heading='Enterprise Audit Logs', logs=logs)

# ==========================================
# SHARED & API ROUTES
# ==========================================

@app.post('/api/activity/heartbeat')
@login_required
def heartbeat():
    uid = session['user_id']
    user_att = query(
        'select * from attendance where employee_id=%s and punch_out is null order by punch_in desc limit 1',
        (uid,),
        one=True
    )
    new_status = 'ON_BREAK' if (user_att and user_att['status'] == 'ON_BREAK') else 'ACTIVE'
    
    query("""
        insert into activity (employee_id, last_activity, status, updated_at)
        values (%s, now(), %s, now())
        on conflict (employee_id) do update
        set last_activity = now(),
            status = %s,
            updated_at = now()
    """, (uid, new_status, new_status), commit=True)
    
    return jsonify({'status': new_status, 'timestamp': datetime.now().isoformat()})

@app.get('/api/activity/status')
@role_required('ADMIN')
def activity_status():
    query("""
        update activity
        set status = case
            when last_activity < now() - interval '30 minutes' then 'OFFLINE'
            when last_activity < now() - interval '5 minutes' then 'IDLE'
            else status
        end,
        updated_at = now()
    """, commit=True)
    
    active_users = query("""
        select u.emp_id, u.name, u.department, a.status, a.last_activity
        from users u
        left join activity a on a.employee_id = u.id
        where u.role = 'EMPLOYEE' and u.is_active = true
        order by u.name
    """)
    return jsonify(active_users)

@app.get('/notifications')
@login_required
def notifications():
    items = query(
        "select * from notifications where employee_id=%s order by created_at desc limit 100",
        (session['user_id'],)
    )
    return render_template('notifications.html', heading='Alerts & Notifications', items=items)

@app.post('/notifications/read-all')
@login_required
def notifications_read_all():
    query("update notifications set is_read=true where employee_id=%s", (session['user_id'],), commit=True)
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))

@app.get('/health')
def healthcheck():
    db_ok = False
    try:
        query("select 1", one=True)
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({'status': 'healthy' if db_ok else 'degraded', 'database': db_ok, 'server_time': datetime.now().isoformat()})

# ==========================================
# ERROR HANDLERS & SECURITY HEADERS
# ==========================================

@app.errorhandler(403)
def forbidden(e):
    return render_template('login.html', error='Access denied. You lack permissions for this resource.'), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', heading='Page Not Found', error_message='The requested route does not exist.'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', heading='Server Error', error_message='An unexpected error occurred. Please check system logs or database connection.'), 500

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
