import os
from datetime import datetime, date, timedelta, timezone
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-only-change-me')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('VERCEL') == '1')
IDLE_MINUTES = 5

def db():
    return psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)

def query(sql, params=(), one=False, commit=False):
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        result = cur.fetchone() if one else cur.fetchall()
        if commit: conn.commit()
        return result

def current_user():
    return query('select * from users where id=%s and is_active=true', (session.get('user_id'),), one=True) if session.get('user_id') else None

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            session.clear(); return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped

def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get('role') != role: abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

def fmt_seconds(seconds):
    seconds = max(0, int(seconds or 0)); return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'

def row_duration(row):
    if not row: return '00:00:00'
    end = row.get('punch_out') or datetime.now(timezone.utc)
    start = row.get('punch_in')
    if start and start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    return fmt_seconds((end - start).total_seconds()) if start else '00:00:00'

def hours_since(start):
    return fmt_seconds(query("select coalesce(sum(total_seconds),0) as seconds from attendance where employee_id=%s and punch_in >= %s", (start, session['user_id']), one=True)['seconds'])

@app.template_filter('duration')
def duration_filter(row): return row_duration(row)

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user(): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = query('select * from users where upper(emp_id)=upper(%s)', (request.form.get('emp_id', '').strip(),), one=True)
        if not user or not user['is_active'] or not check_password_hash(user['password_hash'], request.form.get('password', '')):
            flash('Invalid credentials or inactive account.'); return render_template('login.html'), 401
        session.clear(); session.update(user_id=user['id'], role=user['role'], name=user['name']); return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.get('/dashboard')
@login_required
def dashboard(): return redirect(url_for('admin_dashboard' if session['role'] == 'ADMIN' else 'employee_dashboard'))

@app.get('/employee')
@role_required('EMPLOYEE')
def employee_dashboard():
    user = current_user(); attendance = query('select * from attendance where employee_id=%s and punch_in::date=current_date order by punch_in desc limit 1', (user['id'],), one=True)
    tasks = query("select * from tasks where employee_id=%s order by (status='COMPLETED'), due_date nulls last, created_at desc", (user['id'],))
    reports = query('select * from productivity_reports where employee_id=%s order by report_date desc limit 5', (user['id'],))
    activity = query('select * from activity where employee_id=%s', (user['id'],), one=True) or {'status':'OFFLINE'}
    unfinished = [task for task in tasks if task['status'] != 'COMPLETED']
    return render_template('employee_dashboard.html', heading='My dashboard', user=user, attendance=attendance, tasks=tasks, reports=reports, activity=activity, unfinished=unfinished, now=datetime.now(), weekly_hours=hours_since(date.today()-timedelta(days=datetime.now().weekday())), monthly_hours=hours_since(date.today().replace(day=1)))

@app.post('/employee/punch-in')
@role_required('EMPLOYEE')
def punch_in():
    try:
        query('insert into attendance (employee_id,status) values (%s,\'WORKING\')', (session['user_id'],), commit=True)
        flash('You are punched in. Have a productive day.', 'success')
    except psycopg2.errors.UniqueViolation:
        flash('You are already punched in.', 'error')
    return redirect(url_for('employee_dashboard'))

@app.post('/employee/punch-out')
@role_required('EMPLOYEE')
def punch_out():
    attendance = query('select * from attendance where employee_id=%s and punch_out is null order by punch_in desc limit 1', (session['user_id'],), one=True)
    if not attendance: flash('No active work session found.', 'error'); return redirect(url_for('employee_dashboard'))
    form = request.form
    with db() as conn, conn.cursor() as cur:
        cur.execute('update attendance set punch_out=now(), total_seconds=extract(epoch from (now()-punch_in))::integer, status=\'COMPLETED\' where id=%s', (attendance['id'],))
        cur.execute('insert into productivity_reports (employee_id,report_date,work_completed,progress,achievements,blockers,remaining_work,productivity_rating,notes) values (%s,current_date,%s,%s,%s,%s,%s,%s,%s) on conflict(employee_id,report_date) do update set work_completed=excluded.work_completed,progress=excluded.progress,achievements=excluded.achievements,blockers=excluded.blockers,remaining_work=excluded.remaining_work,productivity_rating=excluded.productivity_rating,notes=excluded.notes', (session['user_id'], form['work_completed'], form['progress'], form.get('achievements'), form.get('blockers'), form.get('remaining_work'), form.get('productivity_rating'), form.get('notes')))
        conn.commit()
    flash('Your report was saved and the work session is complete.', 'success'); return redirect(url_for('employee_dashboard'))

@app.post('/employee/tasks/<int:task_id>/complete')
@role_required('EMPLOYEE')
def complete_task(task_id):
    query("update tasks set status='COMPLETED',completed_at=now() where id=%s and employee_id=%s and status!='COMPLETED'", (task_id, session['user_id']), commit=True); flash('Task marked complete.', 'success'); return redirect(url_for('employee_dashboard'))

@app.post('/api/activity/heartbeat')
@login_required
def heartbeat():
    query("insert into activity(employee_id,last_activity,status,updated_at) values(%s,now(),'ACTIVE',now()) on conflict(employee_id) do update set last_activity=now(),status='ACTIVE',updated_at=now()", (session['user_id'],), commit=True); return jsonify({'status':'ACTIVE'})

@app.get('/api/activity/status')
@role_required('ADMIN')
def activity_status():
    query("update activity set status=case when last_activity < now()-interval '30 minutes' then 'OFFLINE' when last_activity < now()-interval '5 minutes' then 'IDLE' else 'ACTIVE' end,updated_at=now()", commit=True)
    return jsonify(query('select u.emp_id,u.name,a.status,a.last_activity from users u left join activity a on a.employee_id=u.id where u.role=\'EMPLOYEE\' order by u.name'))

@app.get('/admin')
@role_required('ADMIN')
def admin_dashboard():
    query("update activity set status=case when last_activity < now()-interval '30 minutes' then 'OFFLINE' when last_activity < now()-interval '5 minutes' then 'IDLE' else 'ACTIVE' end,updated_at=now()", commit=True)
    employees = query("select u.*,coalesce(a.status,'OFFLINE') activity_status,a.last_activity,at.punch_in,coalesce(at.total_seconds,extract(epoch from(now()-at.punch_in))::integer,0) seconds,coalesce(t.total_tasks,0) total_tasks,coalesce(t.completed_tasks,0) completed_tasks from users u left join activity a on a.employee_id=u.id left join lateral (select * from attendance where employee_id=u.id and punch_in::date=current_date order by punch_in desc limit 1) at on true left join lateral (select count(*) total_tasks,count(*) filter(where status='COMPLETED') completed_tasks from tasks where employee_id=u.id) t on true where u.role='EMPLOYEE' and u.is_active=true order by u.name")
    for row in employees: row['working_time'] = fmt_seconds(row['seconds']); row['last_activity'] = row['last_activity'].strftime('%I:%M %p') if row['last_activity'] else None
    stats = query("select count(*) filter(where role='EMPLOYEE' and is_active) total_employees,count(*) filter(where role='EMPLOYEE' and is_active and a.status='ACTIVE') working,count(*) filter(where role='EMPLOYEE' and is_active and a.status='IDLE') idle,count(*) filter(where role='EMPLOYEE' and is_active and (a.status='OFFLINE' or a.status is null)) offline,coalesce((select sum(total_seconds) from attendance where punch_in::date=current_date),0) hours_today from users u left join activity a on a.employee_id=u.id", one=True); stats['hours_today'] = fmt_seconds(stats['hours_today'])
    task_stats = query("select count(*) filter(where status='COMPLETED') completed,count(*) filter(where status!='COMPLETED') pending from tasks", one=True); chart = query("select u.name,round(coalesce(sum(a.total_seconds),0)/3600.0,1) hours from users u left join attendance a on a.employee_id=u.id and a.punch_in::date=current_date where u.role='EMPLOYEE' group by u.name order by u.name")
    return render_template('admin_dashboard.html', heading='Operations overview', stats=stats, employees=employees, chart_data={'completed':task_stats['completed'],'pending':task_stats['pending'],'names':[r['name'] for r in chart],'hours':[float(r['hours']) for r in chart]})

@app.get('/admin/attendance')
@role_required('ADMIN')
def admin_attendance():
    employee = request.args.get('employee',''); selected_date = request.args.get('date','')
    sql = "select a.*,u.name,u.emp_id from attendance a join users u on u.id=a.employee_id where 1=1"; params=[]
    if employee: sql += ' and u.id=%s'; params.append(employee)
    if selected_date: sql += ' and a.punch_in::date=%s'; params.append(selected_date)
    sql += ' order by a.punch_in desc limit 200'
    return render_template('admin_attendance.html', heading='Attendance', records=query(sql,params), employees=query("select id,name from users where role='EMPLOYEE' order by name"), filters={'employee':employee,'date':selected_date})

@app.get('/admin/reports')
@role_required('ADMIN')
def admin_reports(): return render_template('admin_reports.html', heading='Productivity reports', reports=query("select p.*,u.name,u.emp_id from productivity_reports p join users u on u.id=p.employee_id order by p.report_date desc,p.created_at desc limit 200"))

@app.route('/admin/employees', methods=['GET', 'POST'])
@role_required('ADMIN')
def admin_employees():
    if request.method == 'POST':
        form = request.form
        if form.get('action') == 'toggle':
            query('update users set is_active=not is_active where id=%s and role=\'EMPLOYEE\'', (form.get('user_id'),), commit=True)
            flash('Employee access updated.', 'success')
        elif form.get('action') == 'create':
            try:
                query('insert into users (emp_id,name,email,password_hash,role,department,designation) values (%s,%s,%s,%s,\'EMPLOYEE\',%s,%s)', (form['emp_id'].strip(), form['name'].strip(), form.get('email') or None, generate_password_hash(form['password']), form.get('department'), form.get('designation')), commit=True)
                flash('Employee added.', 'success')
            except psycopg2.errors.UniqueViolation:
                flash('That EMP ID or email already exists.', 'error')
        return redirect(url_for('admin_employees'))
    return render_template('admin_employees.html', heading='Employee management', employees=query("select * from users where role='EMPLOYEE' order by is_active desc,name"))

@app.route('/admin/tasks', methods=['GET', 'POST'])
@role_required('ADMIN')
def admin_tasks():
    if request.method == 'POST':
        form = request.form
        if not form.get('title') or not form.get('employee_id'):
            flash('Task title and employee are required.', 'error')
        else:
            query('insert into tasks (employee_id,title,description,priority,due_date) values (%s,%s,%s,%s,%s)', (form['employee_id'], form['title'].strip(), form.get('description'), form.get('priority', 'MEDIUM'), form.get('due_date') or None), commit=True)
            flash('Task assigned successfully.', 'success')
            return redirect(url_for('admin_tasks'))
    return render_template('admin_tasks.html', heading='Task management', employees=query("select id,name,emp_id from users where role='EMPLOYEE' and is_active=true order by name"), tasks=query("select t.*,u.name from tasks t join users u on u.id=t.employee_id order by t.created_at desc limit 100"))

@app.get('/notifications')
@login_required
def notifications():
    return render_template('notifications.html', heading='Notifications', items=query('select * from notifications where employee_id=%s order by created_at desc limit 50', (session['user_id'],)))

@app.errorhandler(403)
def forbidden(_): return render_template('login.html', error='You do not have permission to view this page.'), 403

if __name__ == '__main__': app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1')
