# WorkPulse

WorkPulse is a cloud-backed employee attendance, productivity, and task management system for event operations teams.

## Features

- Role-based admin and employee authentication with hashed passwords
- Server-authoritative punch-in, punch-out, working hours, and attendance history
- Daily productivity reports with remaining-task acknowledgement
- Task assignment and completion tracking
- Browser activity heartbeat with active, idle, and offline states
- Admin team pulse, attendance, productivity, and Chart.js analytics views
- Responsive corporate UI and Vercel serverless configuration

## Technology Stack

Flask, PostgreSQL on Supabase, psycopg2, server-rendered HTML, custom CSS, vanilla JavaScript, and Chart.js CDN.

## Architecture

`app.py` contains routing, authorization, business logic, and parameterized SQL. Templates provide the two role-specific workspaces; static assets contain the shared UI and browser heartbeat/timer behavior. No local persistence is used.

## Database

Run `database/schema.sql` in the Supabase SQL Editor. The partial unique index prevents two open attendance sessions for one employee.

## Authentication

Passwords are stored using Werkzeug PBKDF2 hashing. Flask sessions hold only the authenticated user id, role, and display name. Admin routes are protected server-side.

## Local Setup

1. Create a Python virtual environment: `python -m venv .venv`
2. Activate it and install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in Supabase values.
4. Run the schema in Supabase.
5. Seed development data: `python seed.py`
6. Start the app: `python app.py`
7. Open `http://127.0.0.1:5000`

## Environment Variables

- `DATABASE_URL`: Supabase PostgreSQL connection string
- `SECRET_KEY`: long random Flask session secret
- `FLASK_DEBUG`: optional local debug flag

## Supabase Setup

Create a Supabase project, copy the Postgres connection string from Project Settings > Database, and run the schema SQL. Use the pooled connection string for serverless deployments when appropriate.

## Vercel Deployment

Import the GitHub repository into Vercel, set the `DATABASE_URL` and `SECRET_KEY` environment variables, and deploy. `vercel.json` selects the Python runtime and routes all requests to `app.py`.

## Demo Credentials

Development-only credentials created by `seed.py`:

- Admin: `ADMIN001` / `Admin@123`
- Employee: `EMP001` / `Employee@123`
- Other employees: `EMP002` through `EMP005` / `Employee@123`

Change or remove these credentials before production use.

## Screenshots

Add deployment screenshots here after the first Vercel release.

## Future Improvements

CSRF protection, audit logs, richer filters, email delivery, configurable departments, and a dedicated mobile experience.
