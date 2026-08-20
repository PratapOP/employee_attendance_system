# WorkPulse Enterprise Operations Platform

**WorkPulse** is a corporate-grade Employee Attendance, Workforce Operations, Shift Timekeeping, and Daily Asynchronous Standup Platform engineered for high-velocity teams and event operations.

Designed for frictionless serverless deployment on **Vercel** backed by cloud **PostgreSQL (Supabase / Neon)**.

---

## Key Enterprise Features

### 1. Authoritative Attendance & Shift Stopwatch
- **Server-Authoritative Timekeeping**: Punch-in and punch-out calculations are validated server-side to prevent client timestamp tampering.
- **Break & Pause Tracking**: Seamlessly start and stop Lunch, Coffee, Meeting, and Personal breaks with authoritative subtraction from total shift hours.
- **Live Visual Stopwatch**: Real-time responsive timer showing live net working hours and pulse status.
- **Personal Timesheets**: Employees can inspect monthly punch logs, break durations, and location notes.

### 2. Daily EOD Standup & Productivity Reports
- **Structured Shift Wrap-Up**: Employees submit accomplishments, progress milestones, blockers, and self-ratings upon punch-out.
- **Blocker Alert System**: Management dashboard highlights blocked initiatives for instant unblocking.
- **Task Acknowledgment Guard**: Prompts employees before sign-off if priority deliverables remain incomplete.

### 3. Task Delivery Queue & Priority Dispatch
- **Priority Matrix**: Categorize tasks by `URGENT`, `HIGH`, `MEDIUM`, or `LOW`.
- **Workflow State Progression**: Move deliverables across `TODO`, `IN_PROGRESS`, `COMPLETED`, and `BLOCKED`.
- **Automated Notifications**: Team members receive in-app alerts whenever work is assigned.

### 4. Leave & Time-Off Management
- **Self-Service Requests**: Submit PTO, Casual, Sick, Half-Day, or Remote Work requests with date ranges and rationale.
- **Manager Review Workflow**: Operations leads approve or reject with contextual comments.

### 5. Management Command & Executive Analytics
- **Live Team Pulse**: Monitor active workers, on-break staff, idle members, and offline team in real time.
- **Interactive Visualizations (Chart.js)**:
  - Task execution breakdown (Donut chart).
  - 7-day workforce hours logged (Bar chart).
- **Payroll-Ready CSV Exports**: One-click exports for Timesheets, Standup Reports, and Workforce Directory.
- **Enterprise Audit Trail**: Automated security logging for logins, punches, task completions, and status changes.

---

## Technology Stack

- **Backend**: Python 3.11, Flask 3.1, WSGI Serverless Runtime
- **Database**: PostgreSQL 15+ (Supabase / Neon / Railway / AWS RDS) with `psycopg2-binary`
- **Frontend**: Semantic HTML5, Custom Executive Design System (Vanilla CSS), Vanilla JavaScript, Chart.js CDN
- **Cloud Platform**: Vercel Serverless Functions (`@vercel/python`)

---

## Local Development Quickstart

### 1. Clone & Environment Setup
```bash
git clone https://github.com/YOUR_USERNAME/employee_attendance_system.git
cd employee_attendance_system
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your database string:
```bash
cp .env.example .env
```

### 3. Initialize Schema & Seed Data
Execute `database/schema.sql` in your Supabase or PostgreSQL SQL editor, then seed demo accounts:
```bash
python seed.py
```

### 4. Start Development Server
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Vercel Deployment

For complete step-by-step instructions, see **[DEPLOYMENT_ROADMAP.md](DEPLOYMENT_ROADMAP.md)**.

1. Push your repository to GitHub.
2. Import project on [Vercel](https://vercel.com).
3. Set environment variables:
   - `DATABASE_URL`: `postgresql://...` (Supabase / Neon Connection Pooler URL with `?sslmode=require`)
   - `SECRET_KEY`: `[64-character random hex string]`
   - `FLASK_ENV`: `production`
   - `VERCEL`: `1`
4. Click **Deploy**.

---

## Demo Accounts

| Role | Employee ID | Password | Department |
|---|---|---|---|
| **Director of Operations** | `ADMIN001` | `Admin@123` | Executive Operations |
| **Shift Lead (Coordinator)** | `EMP001` | `Employee@123` | Event Production |
| **Partnerships Lead** | `EMP002` | `Employee@123` | Sponsorship & Brand |
| **Creative Producer** | `EMP003` | `Employee@123` | Creative & Design |
| **Technical Specialist** | `EMP004` | `Employee@123` | Stage & Tech Ops |
| **Marketing Manager** | `EMP005` | `Employee@123` | Growth & Marketing |

---

## Corporate Scaling Roadmap

See **[DEPLOYMENT_ROADMAP.md](DEPLOYMENT_ROADMAP.md)** for the 4-phase enterprise roadmap:
- **Phase 1**: Custom Domain, SSL & Hardening
- **Phase 2**: Single Sign-On (Google Workspace, Azure AD) & Slack/Teams Webhooks
- **Phase 3**: Gusto/Deel Payroll API Integration & Mobile PWA Check-In
- **Phase 4**: Multi-Tier RBAC & SOC-2 Compliance
