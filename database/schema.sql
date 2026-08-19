create table if not exists users (
  id bigserial primary key,
  emp_id varchar(50) unique not null,
  name varchar(160) not null,
  email varchar(255) unique,
  password_hash text not null,
  role varchar(20) not null check (role in ('ADMIN', 'EMPLOYEE')),
  department varchar(100),
  designation varchar(120),
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);
create table if not exists attendance (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  punch_in timestamptz not null default now(),
  punch_out timestamptz,
  total_seconds integer not null default 0,
  status varchar(20) not null default 'WORKING' check (status in ('WORKING','COMPLETED','ABNORMAL')),
  created_at timestamptz not null default now()
);
create unique index if not exists one_open_attendance_per_employee on attendance(employee_id) where punch_out is null;
create table if not exists tasks (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  title varchar(200) not null,
  description text,
  priority varchar(20) not null default 'MEDIUM',
  due_date date,
  status varchar(20) not null default 'TODO' check (status in ('TODO','IN_PROGRESS','COMPLETED','OVERDUE')),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create table if not exists productivity_reports (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
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
create table if not exists activity (
  id bigserial primary key,
  employee_id bigint unique not null references users(id) on delete cascade,
  last_activity timestamptz not null default now(),
  status varchar(20) not null default 'ACTIVE' check (status in ('ACTIVE','IDLE','OFFLINE')),
  updated_at timestamptz not null default now()
);
create table if not exists notifications (
  id bigserial primary key,
  employee_id bigint not null references users(id) on delete cascade,
  title varchar(180) not null,
  message text not null,
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);
