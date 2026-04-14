# Gym Management System

A role-based Flask + MySQL web application built as a DBMS semester project for managing gym operations end-to-end.

## Project Snapshot

This system manages:
- Members, trainers, and users with role-based access
- Membership plans and subscriptions
- Attendance with both check-in and check-out
- Separate dashboards for Admin, Member, and Trainer

## Tech Stack

- Backend: Flask (Python)
- Database: MySQL
- Frontend: Jinja2 templates, Bootstrap 5, custom CSS
- Auth: Session-based login with password hashing

## Current Features (Final)

### 1) Authentication and Authorization
- Secure signup/login/logout flow
- Role-based navigation and route protection using decorators
- Roles:
  - Admin
  - Member
  - Trainer

### 2) Admin Capabilities
- View dashboard metrics (member count, active subscriptions, revenue)
- Add and view members
- Assign trainers during member creation
- Select membership plan while adding a member
- Add new membership plans from the Plans page
- Log attendance for members:
  - Check-in
  - Check-out
- View recent attendance with check-out status

### 3) Member Capabilities
- View personal subscriptions and attendance history
- Check-in from member dashboard
- Check-out from member dashboard
- Choose and activate a new plan from member dashboard
  - Existing active plan is marked Cancelled
  - Newly selected plan becomes Active

### 4) Trainer Capabilities
- View assigned members on trainer dashboard

### 5) Attendance Enhancements
- Attendance table now supports:
  - check_in_date
  - check_in_time
  - check_out_time (nullable)
- Backward-compatible runtime safeguard:
  - App auto-adds check_out_time column if missing in old DB setups

### 6) UI/UX Improvements
- Refined visual theme with modern gradient + glass look
- Better typography and button styling
- Improved navbar/dropdown layering (z-index fix)
- Logout now redirects users to landing page

## Database Design

### Core Entities
- Trainer
- Member
- Membership_Plan
- Subscription
- Attendance
- User

### Key Relationships
- One Trainer can manage many Members
- One Member can have many Subscriptions (history)
- One Plan can be used in many Subscriptions
- One Member can have many Attendance records
- User links to either Member or Trainer by role

### Normalization
- Relations are designed to satisfy 3NF:
  - Atomic attributes (1NF)
  - No partial dependencies (2NF)
  - No transitive dependencies in non-key attributes (3NF)

## Important Functional Flows

### A) Add Member with Plan (Admin)
1. Admin opens Add Member form
2. Enters member details + optional trainer
3. Selects a membership plan
4. System inserts Member row
5. System inserts Active Subscription with computed end date

### B) Member Plan Change
1. Member selects a plan on dashboard
2. Current active subscription (if any) is set to Cancelled
3. New subscription is inserted as Active

### C) Attendance (Admin/Member)
- Check-in creates a new attendance row with null check_out_time
- Check-out updates latest open row for that member

## Project Structure

- app.py: Flask routes, business logic, DB operations
- config.py: Database configuration
- schema.sql: Database schema
- sample_data.sql: Optional sample records
- database_update.sql: DB update script
- templates/: Jinja HTML pages
- static/style.css: Custom theme styles

## Setup and Run

### 1. Prerequisites
- Python 3.10+
- MySQL Server running
- MySQL user credentials configured

### 2. Create virtual environment and install packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure DB credentials
- Set environment variables before running app:

```powershell
$env:DB_HOST="localhost"
$env:DB_USER="root"
$env:DB_PASSWORD="your_mysql_password"
$env:DB_NAME="gym_db"
```

- If you do not set these, defaults are used:
  - DB_HOST=localhost
  - DB_USER=root
  - DB_PASSWORD="" (empty)
  - DB_NAME=gym_db

### 4. Create schema

```powershell
mysql -u root -p < schema.sql
```

### 5. (Optional) Load sample data

```powershell
mysql -u root -p gym_db < sample_data.sql
```

### 6. Run app

```powershell
python app.py
```

Open in browser:
- http://127.0.0.1:5000

## Verified Final Check

- Flask app starts successfully on local environment.
- Modified templates and Python files show no editor-reported errors.

## Suggested Viva Demo Order

1. Landing page and role-based login
2. Admin adds plan
3. Admin adds member with selected plan
4. Member logs in and changes plan
5. Member check-in and check-out
6. Admin attendance panel showing latest records
7. Explain schema, keys, joins, and normalization

## Credits

Created as a DBMS semester project to demonstrate practical implementation of relational design, SQL operations, and role-based workflow management in a real-world domain.
