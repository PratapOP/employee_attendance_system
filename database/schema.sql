-- WorkPulse Database Schema
-- Compatible with PostgreSQL (Supabase, Neon, Railway, RDS)

-- 1. Users & Authentication
create table if not exists users (
  id bigserial primary key,
  emp_id varchar(50) unique not null,
  name varchar(160) not null,
  email varchar(255) unique,
  password_hash text not null,
  role varchar(20) not null check (role in ('ADMIN', 'EMPLOYEE')),
  department varchar(100) default 'Operations',
  designation varchar(120) default 'Team Member',
  phone varchar(50),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  last_login timestamptz
);

-- 2. Attendance & Work Sessions
create table if not exists attendance (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  punch_in timestamptz not null default now(),
  punch_out timestamptz,
  total_seconds integer not null default 0,
  break_seconds integer not null default 0,
  status varchar(20) not null default 'WORKING' check (status in ('WORKING', 'ON_BREAK', 'COMPLETED', 'ABNORMAL')),
  location_note varchar(200),
  notes text,
  created_at timestamptz not null default now()
);

-- Ensure only one active/open attendance session per employee at any time
create unique index if not exists one_open_attendance_per_employee on attendance(employee_id) where punch_out is null;

-- 3. Work Breaks & Pauses (Lunch, Meeting, Personal)
create table if not exists breaks (
  id bigserial primary key,
  attendance_id bigint not null references attendance(id) on delete cascade,
  employee_id bigint not null references users(id) on delete cascade,
  break_type varchar(50) not null default 'LUNCH' check (break_type in ('LUNCH', 'SHORT_BREAK', 'MEETING', 'PERSONAL')),
  start_time timestamptz not null default now(),
  end_time timestamptz,
  total_seconds integer not null default 0,
  notes varchar(255),
  created_at timestamptz not null default now()
);

create unique index if not exists one_open_break_per_attendance on breaks(attendance_id) where end_time is null;

-- 4. Tasks & Project Deliverables
create table if not exists tasks (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  title varchar(200) not null,
  description text,
  priority varchar(20) not null default 'MEDIUM' check (priority in ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
  category varchar(100) default 'General',
  due_date date,
  status varchar(20) not null default 'TODO' check (status in ('TODO', 'IN_PROGRESS', 'COMPLETED', 'BLOCKED')),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

-- 5. Daily EOD Productivity & Standup Reports
create table if not exists productivity_reports (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  attendance_id bigint references attendance(id) on delete set null,
  report_date date not null,
  work_completed text not null,
  progress text not null,
  achievements text,
  blockers text,
  remaining_work text,
  productivity_rating integer check (productivity_rating between 1 and 5),
  notes text,
  created_at timestamptz not null default now(),
  unique(employee_id, report_date)
);

-- 6. Leave & Time-off Management
create table if not exists leaves (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  leave_type varchar(50) not null default 'CASUAL' check (leave_type in ('CASUAL', 'SICK', 'PAID_TIME_OFF', 'HALF_DAY', 'REMOTE_WORK')),
  start_date date not null,
  end_date date not null,
  reason text not null,
  status varchar(20) not null default 'PENDING' check (status in ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
  manager_comment text,
  reviewed_by bigint references users(id) on delete set null,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

-- 7. Real-Time Activity Heartbeat
create table if not exists activity (
  id bigserial primary key,
  employee_id bigint unique not null references users(id) on delete cascade,
  last_activity timestamptz not null default now(),
  status varchar(20) not null default 'ACTIVE' check (status in ('ACTIVE', 'IDLE', 'OFFLINE', 'ON_BREAK')),
  updated_at timestamptz not null default now()
);

-- 8. Notifications & Alerts
create table if not exists notifications (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  title varchar(180) not null,
  message text not null,
  category varchar(50) default 'SYSTEM' check (category in ('TASK', 'ATTENDANCE', 'LEAVE', 'SYSTEM', 'ANNOUNCEMENT')),
  link varchar(255),
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);

-- 9. Enterprise Audit Logs (Security & Compliance)
create table if not exists audit_logs (
  id bigserial primary key,
  user_id bigint references users(id) on delete set null,
  action varchar(100) not null,
  details text,
  ip_address varchar(60),
  created_at timestamptz not null default now()
);

-- Performance Indexes
create index if not exists idx_attendance_emp_date on attendance(employee_id, punch_in desc);
create index if not exists idx_tasks_emp_status on tasks(employee_id, status);
create index if not exists idx_reports_emp_date on productivity_reports(employee_id, report_date desc);
create index if not exists idx_leaves_emp_status on leaves(employee_id, status);
create index if not exists idx_notifications_emp on notifications(employee_id, is_read, created_at desc);
create index if not exists idx_breaks_attendance on breaks(attendance_id);
