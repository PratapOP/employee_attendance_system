# WorkPulse Enterprise Deployment & Corporate Readiness Roadmap

This guide provides an end-to-end walkthrough for deploying **WorkPulse** to **Vercel serverless infrastructure** and executing the strategic roadmap to transform it into a full-scale corporate enterprise operations platform.

---

## Part 1: Fast-Track Vercel Production Deployment (Under 5 Minutes)

### Step 1: Provision a Cloud PostgreSQL Database

WorkPulse runs on standard PostgreSQL. We recommend **Supabase** or **Neon** (both offer generous free tiers with serverless connection pooling).

#### Option A: Supabase (Recommended)
1. Go to [supabase.com](https://supabase.com) and create a free project.
2. Navigate to **Project Settings** > **Database** > **Connection Pooling**.
3. Copy the **Transaction Mode** connection string (Port `6543`).
   > Example: `postgresql://postgres.your-project:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require`
4. In the Supabase Dashboard, open the **SQL Editor**, paste the contents of `database/schema.sql`, and click **Run**.
5. (Optional) Run `python seed.py` locally after setting `DATABASE_URL` in `.env` to populate realistic demo accounts.

#### Option B: Neon
1. Go to [neon.tech](https://neon.tech) and create a project.
2. Copy the pooled connection string (includes `-pooler` in the host).
3. Run `database/schema.sql` in the Neon SQL Editor.

---

### Step 2: Push Code to GitHub

Initialize your repository (if not already done) and push to GitHub:
```bash
git init
git add .
git commit -m "feat: enterprise workpulse with vercel serverless support"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/employee_attendance_system.git
git push -u origin main
```

---

### Step 3: Deploy to Vercel

1. Log in to [vercel.com](https://vercel.com) and click **"Add New..."** > **"Project"**.
2. Select your `employee_attendance_system` repository and click **Import**.
3. In the **Environment Variables** section, add the following keys:

| Key | Value | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | Your Supabase / Neon pooled connection string with `?sslmode=require` |
| `SECRET_KEY` | `[64-character hex string]` | Cryptographically random secret key (see generator below) |
| `FLASK_ENV` | `production` | Enables production security cookie flags |
| `VERCEL` | `1` | Enforces HTTPS secure cookies |

> **Generate a secure SECRET_KEY in your terminal:**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

4. Click **Deploy**. Vercel will build and deploy the Python serverless functions in ~30 seconds.
5. Visit your generated `https://[your-app].vercel.app` URL. Test `/health` to verify database connectivity.

---

## Part 2: Vercel Architecture & Technical Blueprint

```
┌─────────────────────────────────────────────────────────────┐
│                       Vercel Edge CDN                       │
│    (Static Asset Caching: CSS, JS, Google Fonts, Chart.js)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Vercel Serverless Function                  │
│       Python 3.11 Runtime / WSGI Micro-Instance             │
│            (app.py - Auth, Sessions, API, UI)               │
└──────────────────────────────┬──────────────────────────────┘
                               │
               (SSL Encrypted Connection Pooler)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              Managed Cloud PostgreSQL (Supabase/Neon)       │
│  - Users & Roles (ADMIN, EMPLOYEE)                          │
│  - Server-Authoritative Attendance & Real-Time Stopwatch    │
│  - Breaks & Pauses (Lunch, Coffee, Meeting)                 │
│  - Leave Applications & Approvals                           │
│  - Task Delivery Queue with Priorities                      │
│  - Daily Asynchronous Standup Reports                       │
│  - Immutable Enterprise Audit Trail                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 3: Corporate Readiness Roadmap (Phased Execution)

```mermaid
gantt
    title Corporate Readiness Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Hardening
    Custom Domain & SSL          :p1_1, 2026-08-21, 2d
    Rate Limiting & CSRF         :p1_2, after p1_1, 3d
    section Phase 2: Integrations
    Google / Azure SSO (SAML)    :p2_1, 2026-08-26, 5d
    Slack & Teams Webhooks       :p2_2, after p2_1, 4d
    Email Alerts (SendGrid)      :p2_3, after p2_2, 3d
    section Phase 3: Operations
    Payroll Sync (Gusto/Deel)    :p3_1, 2026-09-07, 7d
    Geo-fencing & Mobile PWA     :p3_2, after p3_1, 7d
    section Phase 4: Enterprise
    RBAC & Department Tiers      :p4_1, 2026-09-21, 7d
    SOC-2 Audit Compliance       :p4_2, after p4_1, 10d
```

### Phase 1: Production Launch & Hardening (Week 1)
- [x] **Database connection pooling** configured for serverless scalability.
- [x] **Authoritative server timers** with automatic pause/break subtraction.
- [x] **One-click CSV exports** for timesheets, standups, and workforce rosters.
- [ ] **Custom Domain Setup**: Configure `ops.yourcompany.com` in Vercel DNS.
- [ ] **Automated DB Backups**: Enable daily snapshot retention in Supabase/Neon.
- [ ] **Error Monitoring**: Add Sentry SDK to catch unhandled exceptions in real time.

---

### Phase 2: Corporate Identity & Communication (Weeks 2–3)
- [ ] **Enterprise Single Sign-On (SSO)**:
  - Integrate OAuth 2.0 / SAML 2.0 with **Google Workspace** and **Microsoft Azure Active Directory**.
  - One-click employee onboarding without manual password management.
- [ ] **Slack & Microsoft Teams Notifications**:
  - Webhook dispatch when an employee submits an EOD standup report with blockers.
  - Morning punch-in reminders in team channels.
  - Instant leave approval requests routed to manager channels.
- [ ] **Automated Email Dispatch (Resend / SendGrid)**:
  - Weekly manager summary email detailing team hours and productivity scores.
  - Leave approval/rejection decision receipts.

---

### Phase 3: Payroll Automation & Mobile PWA (Weeks 4–5)
- [ ] **Payroll & HRIS Integration**:
  - Direct API connector for **Gusto**, **Rippling**, **Deel**, and **QuickBooks Payroll**.
  - Automatic calculation of overtime, weekend differentials, and leave deductions.
- [ ] **Progressive Web App (PWA) & Mobile Check-in**:
  - Add `manifest.json` and service worker for home screen installation on iOS/Android.
  - Optional Geo-fence verification: Validate GPS coordinates against approved venue / office radius upon punch-in.

---

### Phase 4: Enterprise Security & SOC-2 Compliance (Month 2+)
- [ ] **Granular Multi-Tier RBAC**:
  - Roles: `SUPER_ADMIN`, `OPERATIONS_LEAD`, `SHIFT_SUPERVISOR`, `STAFF_MEMBER`, `AUDITOR`.
- [ ] **Compliance Audit Trail**:
  - Enforce 365-day immutable retention on `audit_logs`.
  - Export audit logs to Datadog or CloudWatch.
- [ ] **IP Whitelisting**:
  - Option to restrict admin panel access to corporate VPN IP ranges.

---

## Demo Accounts Reference

| Role | Employee ID | Default Password | Department | Focus |
|---|---|---|---|---|
| **Director of Operations** | `ADMIN001` | `Admin@123` | Executive Operations | Team Pulse, Approvals, Analytics |
| **Shift Lead** | `EMP001` | `Employee@123` | Event Production | Live Timer, Shift Standups |
| **Partnerships Lead** | `EMP002` | `Employee@123` | Sponsorship & Brand | On-Break State, Contract Tasks |
| **Creative Producer** | `EMP003` | `Employee@123` | Creative & Design | Timesheet History, Approvals |
| **Tech Operations** | `EMP004` | `Employee@123` | Stage & Tech Ops | Pending Leave Requests |
| **Marketing Manager** | `EMP005` | `Employee@123` | Growth & Marketing | Task Board & Reporting |
