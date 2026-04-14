from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from config import DB_CONFIG
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'gym_management_super_secret_key'

# Authentication Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Administrator access required.", "danger")
            if 'user_id' in session:
                return redirect(url_for('member_dashboard') if session.get('role') == 'member' else url_for('trainer_dashboard'))
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Helper function to get database connection
def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn


def ensure_attendance_checkout_column(cursor, conn):
    """Adds check_out_time if missing so older databases keep working."""
    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Attendance'
          AND COLUMN_NAME = 'check_out_time'
        """
    )
    if cursor.fetchone()['column_count'] == 0:
        cursor.execute("ALTER TABLE Attendance ADD COLUMN check_out_time TIME NULL")
        conn.commit()

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    # Fetch top stats for the dashboard using aggregations
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total_members FROM Member")
    total_members = cursor.fetchone()['total_members']
    
    cursor.execute("SELECT COUNT(*) as active_subscriptions FROM Subscription WHERE status = 'Active'")
    active_subscriptions = cursor.fetchone()['active_subscriptions']
    
    # Calculate total revenue using grouping/aggregation
    cursor.execute("""
        SELECT SUM(p.price) as total_revenue
        FROM Subscription s
        JOIN Membership_Plan p ON s.plan_id = p.plan_id
        WHERE s.status = 'Active'
    """)
    res = cursor.fetchone()
    total_revenue = res['total_revenue'] if res['total_revenue'] else 0

    cursor.close()
    conn.close()
    return render_template('index.html', total_members=total_members, 
                           active_subscriptions=active_subscriptions, total_revenue=total_revenue)

@app.route('/members')
@admin_required
def members():
    # Fetch members along with their assigned trainer using a JOIN query
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT m.member_id, m.first_name, m.last_name, m.email, m.phone, m.join_date,
               t.first_name AS trainer_fname, t.last_name AS trainer_lname,
               (
                   SELECT p.name
                   FROM Subscription s
                   JOIN Membership_Plan p ON s.plan_id = p.plan_id
                   WHERE s.member_id = m.member_id AND s.status = 'Active'
                   ORDER BY s.end_date DESC, s.subscription_id DESC
                   LIMIT 1
               ) AS active_plan_name,
               (
                   SELECT s.end_date
                   FROM Subscription s
                   WHERE s.member_id = m.member_id AND s.status = 'Active'
                   ORDER BY s.end_date DESC, s.subscription_id DESC
                   LIMIT 1
               ) AS active_plan_end_date
        FROM Member m
        LEFT JOIN Trainer t ON m.trainer_id = t.trainer_id
    """
    cursor.execute(query)
    members_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('members.html', members=members_list)

@app.route('/add_member', methods=('GET', 'POST'))
@admin_required
def add_member():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        trainer_id = request.form['trainer_id'] if request.form['trainer_id'] else None
        plan_id = request.form['plan_id'] if request.form.get('plan_id') else None

        if not plan_id:
            flash('Please select a membership plan.', 'warning')
            return redirect(url_for('add_member'))
        
        try:
            cursor.execute("""
                INSERT INTO Member (first_name, last_name, email, phone, join_date, trainer_id)
                VALUES (%s, %s, %s, %s, CURDATE(), %s)
            """, (first_name, last_name, email, phone, trainer_id))

            member_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO Subscription (member_id, plan_id, start_date, end_date, status)
                SELECT %s, p.plan_id, CURDATE(), DATE_ADD(CURDATE(), INTERVAL p.duration_months MONTH), 'Active'
                FROM Membership_Plan p
                WHERE p.plan_id = %s
            """, (member_id, plan_id))

            if cursor.rowcount == 0:
                raise ValueError('Invalid membership plan selected.')

            conn.commit()
            flash('Member and subscription added successfully!', 'success')
            return redirect(url_for('members'))
        except Exception as e:
            conn.rollback()
            flash(f"Error adding member: {e}", 'danger')
    
    # Fetch active trainers for the dropdown
    cursor.execute("SELECT trainer_id, first_name, last_name FROM Trainer")
    trainers = cursor.fetchall()

    # Fetch available membership plans for the dropdown
    cursor.execute("SELECT plan_id, name, duration_months, price FROM Membership_Plan ORDER BY duration_months ASC, price ASC")
    plans = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('add_member.html', trainers=trainers, plans=plans)

@app.route('/plans', methods=('GET', 'POST'))
@admin_required
def plans():
    if request.method == 'POST':
        plan_name = request.form.get('name', '').strip()
        duration_raw = request.form.get('duration_months', '').strip()
        price_raw = request.form.get('price', '').strip()

        if not plan_name or not duration_raw or not price_raw:
            flash('All plan fields are required.', 'warning')
            return redirect(url_for('plans'))

        try:
            duration_months = int(duration_raw)
            price = float(price_raw)
            if duration_months <= 0 or price <= 0:
                raise ValueError
        except ValueError:
            flash('Duration and price must be positive numbers.', 'warning')
            return redirect(url_for('plans'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                INSERT INTO Membership_Plan (name, duration_months, price)
                VALUES (%s, %s, %s)
                """,
                (plan_name, duration_months, price),
            )
            conn.commit()
            flash('Membership plan added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f"Error adding membership plan: {e}", 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('plans'))

    # Simple SELECT operation
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Membership_Plan")
    plans_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('plans.html', plans=plans_list)

@app.route('/attendance', methods=('GET', 'POST'))
@admin_required
def attendance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    ensure_attendance_checkout_column(cursor, conn)
    
    if request.method == 'POST':
        action = request.form.get('action', 'checkin')
        member_id = request.form['member_id']
        try:
            if action == 'checkout':
                cursor.execute("""
                    UPDATE Attendance
                    SET check_out_time = CURTIME()
                    WHERE member_id = %s
                      AND check_out_time IS NULL
                    ORDER BY check_in_date DESC, check_in_time DESC
                    LIMIT 1
                """, (member_id,))

                if cursor.rowcount == 0:
                    flash('No active check-in found for this member.', 'warning')
                else:
                    conn.commit()
                    flash('Check-out recorded successfully!', 'success')
            else:
                cursor.execute("""
                    INSERT INTO Attendance (member_id, check_in_date, check_in_time, check_out_time)
                    VALUES (%s, CURDATE(), CURTIME(), NULL)
                """, (member_id,))
                conn.commit()
                flash('Check-in recorded successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f"Error updating attendance: {e}", 'danger')
        return redirect(url_for('attendance'))

    # Fetch recent attendance records WITH member info via JOIN
    cursor.execute("""
        SELECT a.attendance_id, m.first_name, m.last_name, a.check_in_date, a.check_in_time, a.check_out_time
        FROM Attendance a
        JOIN Member m ON a.member_id = m.member_id
        ORDER BY a.check_in_date DESC, a.check_in_time DESC
        LIMIT 20
    """)
    records = cursor.fetchall()

    # Fetch simple list of members for dropdown
    cursor.execute("SELECT member_id, first_name, last_name FROM Member ORDER BY first_name ASC")
    members_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('attendance.html', records=records, members=members_list)

@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role'] # 'admin', 'member', 'trainer'

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Check if username exists
            cursor.execute("SELECT user_id FROM User WHERE username = %s", (username,))
            if cursor.fetchone():
                flash("Username already exists.", "danger")
                return redirect(url_for('signup'))
            
            password_hash = generate_password_hash(password)
            member_id = None
            trainer_id = None

            if role == 'member':
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                email = request.form['email']
                phone = request.form['phone']
                
                cursor.execute("""
                    INSERT INTO Member (first_name, last_name, email, phone, join_date)
                    VALUES (%s, %s, %s, %s, CURDATE())
                """, (first_name, last_name, email, phone))
                member_id = cursor.lastrowid
                
                # Auto-assign a default active subscription (Plan ID 1 - Monthly)
                cursor.execute("""
                    INSERT INTO Subscription (member_id, plan_id, start_date, end_date, status)
                    VALUES (%s, 1, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 1 MONTH), 'Active')
                """, (member_id,))
                
                # Log a default initial class attendance
                cursor.execute("""
                    INSERT INTO Attendance (member_id, check_in_date, check_in_time)
                    VALUES (%s, CURDATE(), CURTIME())
                """, (member_id,))
                
            elif role == 'trainer':
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                specialization = request.form['specialization']
                phone = request.form['phone']
                
                cursor.execute("""
                    INSERT INTO Trainer (first_name, last_name, specialization, phone)
                    VALUES (%s, %s, %s, %s)
                """, (first_name, last_name, specialization, phone))
                trainer_id = cursor.lastrowid
            
            # Insert User
            cursor.execute("""
                INSERT INTO User (username, password_hash, role, member_id, trainer_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, password_hash, role, member_id, trainer_id))
            
            conn.commit()
            flash(f"Signup successful as {role.capitalize()}! Please log in.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error during signup: {e}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['member_id'] = user.get('member_id')
            session['trainer_id'] = user.get('trainer_id')
            
            flash(f"Welcome back, {user['username']}!", "success")
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'member':
                return redirect(url_for('member_dashboard'))
            elif user['role'] == 'trainer':
                return redirect(url_for('trainer_dashboard'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/member_dashboard', methods=('GET', 'POST'))
@login_required
def member_dashboard():
    if session.get('role') != 'member':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    ensure_attendance_checkout_column(cursor, conn)
    
    member_id = session.get('member_id')

    if request.method == 'POST':
        action = request.form.get('action', '')
        try:
            if action == 'checkin':
                cursor.execute(
                    """
                    SELECT attendance_id
                    FROM Attendance
                    WHERE member_id = %s
                      AND check_out_time IS NULL
                    ORDER BY check_in_date DESC, check_in_time DESC
                    LIMIT 1
                    """,
                    (member_id,),
                )
                open_attendance = cursor.fetchone()

                if open_attendance:
                    flash('You are already checked in. Please check out first.', 'warning')
                else:
                    cursor.execute(
                        """
                        INSERT INTO Attendance (member_id, check_in_date, check_in_time, check_out_time)
                        VALUES (%s, CURDATE(), CURTIME(), NULL)
                        """,
                        (member_id,),
                    )
                    conn.commit()
                    flash('Checked in successfully!', 'success')

            elif action == 'checkout':
                cursor.execute(
                    """
                    UPDATE Attendance
                    SET check_out_time = CURTIME()
                    WHERE member_id = %s
                      AND check_out_time IS NULL
                    ORDER BY check_in_date DESC, check_in_time DESC
                    LIMIT 1
                    """,
                    (member_id,),
                )

                if cursor.rowcount == 0:
                    flash('No active check-in found. Please check in first.', 'warning')
                else:
                    conn.commit()
                    flash('Checked out successfully!', 'success')

            elif action == 'subscribe_plan':
                selected_plan_id = request.form.get('plan_id', '').strip()
                if not selected_plan_id:
                    flash('Please choose a plan first.', 'warning')
                else:
                    cursor.execute(
                        """
                        SELECT plan_id, duration_months
                        FROM Membership_Plan
                        WHERE plan_id = %s
                        """,
                        (selected_plan_id,),
                    )
                    selected_plan = cursor.fetchone()

                    if not selected_plan:
                        flash('Selected plan is not available.', 'danger')
                    else:
                        cursor.execute(
                            """
                            UPDATE Subscription
                            SET status = 'Cancelled'
                            WHERE member_id = %s AND status = 'Active'
                            """,
                            (member_id,),
                        )

                        cursor.execute(
                            """
                            INSERT INTO Subscription (member_id, plan_id, start_date, end_date, status)
                            VALUES (
                                %s,
                                %s,
                                CURDATE(),
                                DATE_ADD(CURDATE(), INTERVAL %s MONTH),
                                'Active'
                            )
                            """,
                            (member_id, selected_plan['plan_id'], selected_plan['duration_months']),
                        )
                        conn.commit()
                        flash('Your plan has been updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f"Action failed: {e}", 'danger')

        cursor.close()
        conn.close()
        return redirect(url_for('member_dashboard'))
    
    # get active subscriptions
    cursor.execute("""
        SELECT p.name AS Plan_Name, s.start_date, s.end_date, s.status
        FROM Subscription s
        JOIN Membership_Plan p ON s.plan_id = p.plan_id
        WHERE s.member_id = %s
    """, (member_id,))
    subscriptions = cursor.fetchall()

    cursor.execute(
        """
        SELECT plan_id, name, duration_months, price
        FROM Membership_Plan
        ORDER BY duration_months ASC, price ASC
        """
    )
    available_plans = cursor.fetchall()

    # get attendance
    cursor.execute(
        """
        SELECT check_in_date, check_in_time, check_out_time
        FROM Attendance
        WHERE member_id = %s
        ORDER BY check_in_date DESC, check_in_time DESC
        LIMIT 10
        """,
        (member_id,),
    )
    attendance = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template(
        'member_dashboard.html',
        subscriptions=subscriptions,
        attendance=attendance,
        available_plans=available_plans,
    )

@app.route('/trainer_dashboard')
@login_required
def trainer_dashboard():
    if session.get('role') != 'trainer':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    trainer_id = session.get('trainer_id')
    cursor.execute("""
        SELECT first_name, last_name, email, phone, join_date
        FROM Member
        WHERE trainer_id = %s
    """, (trainer_id,))
    assigned_members = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('trainer_dashboard.html', members=assigned_members)

if __name__ == '__main__':
    # Run the application in debug mode for local deployment
    app.run(debug=True, host='0.0.0.0', port=5000)
