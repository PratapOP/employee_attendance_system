-- WorkPulse SQLite Local Zero-Config Database Schema

create table if not exists users (
  id integer primary key autoincrement,
  emp_id varchar(50) unique not null,
  name varchar(160) not null,
  email varchar(255) unique,
  password_hash text not null,
  role varchar(20) not null check (role in ('ADMIN', 'EMPLOYEE')),
  department varchar(100) default 'Operations',
  designation varchar(120) default 'Team Member',
  phone varchar(50),
  is_active integer not null default 1,
  created_at text not null default (datetime('now')),
  last_login text
);

create table if not exists attendance (
  id integer primary key autoincrement,
  employee_id integer not null references users(id) on delete cascade,
  punch_in text not null default (datetime('now')),
  punch_out text,
  total_seconds integer not null default 0,
  break_seconds integer not null default 0,
  status varchar(20) not null default 'WORKING' check (status in ('WORKING', 'ON_BREAK', 'COMPLETED', 'ABNORMAL')),
  location_note varchar(200),
  notes text,
  created_at text not null default (datetime('now'))
);

create unique index if not exists one_open_attendance_per_employee on attendance(employee_id) where punch_out is null;

create table if not exists breaks (
  id integer primary key autoincrement,
  attendance_id integer not null references attendance(id) on delete cascade,
  employee_id integer not null references users(id) on delete cascade,
  break_type varchar(50) not null default 'LUNCH',
  start_time text not null default (datetime('now')),
  end_time text,
  total_seconds integer not null default 0,
  notes varchar(255),
  created_at text not null default (datetime('now'))
);

create unique index if not exists one_open_break_per_attendance on breaks(attendance_id) where end_time is null;

create table if not exists tasks (
  id integer primary key autoincrement,
  employee_id integer not null references users(id) on delete cascade,
  title varchar(200) not null,
  description text,
  priority varchar(20) not null default 'MEDIUM',
  category varchar(100) default 'General',
  due_date text,
  status varchar(20) not null default 'TODO',
  created_at text not null default (datetime('now')),
  completed_at text
);

create table if not exists productivity_reports (
  id integer primary key autoincrement,
  employee_id integer not null references users(id) on delete cascade,
  attendance_id integer references attendance(id) on delete set null,
  report_date text not null,
  work_completed text not null,
  progress text not null,
  achievements text,
  blockers text,
  remaining_work text,
  productivity_rating integer,
  notes text,
  created_at text not null default (datetime('now')),
  unique(employee_id, report_date)
);

create table if not exists leaves (
  id integer primary key autoincrement,
  employee_id integer not null references users(id) on delete cascade,
  leave_type varchar(50) not null default 'CASUAL',
  start_date text not null,
  end_date text not null,
  reason text not null,
  status varchar(20) not null default 'PENDING',
  manager_comment text,
  reviewed_by integer references users(id) on delete set null,
  reviewed_at text,
  created_at text not null default (datetime('now'))
);

create table if not exists activity (
  id integer primary key autoincrement,
  employee_id integer unique not null references users(id) on delete cascade,
  last_activity text not null default (datetime('now')),
  status varchar(20) not null default 'ACTIVE',
  updated_at text not null default (datetime('now'))
);

create table if not exists notifications (
  id integer primary key autoincrement,
  employee_id integer not null references users(id) on delete cascade,
  title varchar(180) not null,
  message text not null,
  category varchar(50) default 'SYSTEM',
  link varchar(255),
  is_read integer not null default 0,
  created_at text not null default (datetime('now'))
);

create table if not exists audit_logs (
  id integer primary key autoincrement,
  user_id integer references users(id) on delete set null,
  action varchar(100) not null,
  details text,
  ip_address varchar(60),
  created_at text not null default (datetime('now'))
);

create index if not exists idx_sqlite_att_emp on attendance(employee_id, punch_in);
create index if not exists idx_sqlite_tasks_emp on tasks(employee_id, status);
create index if not exists idx_sqlite_leaves_emp on leaves(employee_id, status);
