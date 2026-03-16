from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from functools import wraps
from datetime import datetime
import sqlite3, hashlib, os, csv, json, secrets

app = Flask(__name__)
app.secret_key = "bagcounter_secret_2026"

DB = "database.db"
UPLOAD_FOLDER = "uploads"
REPORTS_FOLDER = "reports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'operator',
        reset_token TEXT,
        created_at TEXT,
        last_login TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_name TEXT,
        source_type TEXT,
        video_path TEXT,
        total_count INTEGER DEFAULT 0,
        count_in INTEGER DEFAULT 0,
        count_out INTEGER DEFAULT 0,
        csv_path TEXT,
        started_at TEXT,
        ended_at TEXT,
        status TEXT DEFAULT 'running'
    )''')
    # Create default admin if not exists
    admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password, email, role, created_at) VALUES (?,?,?,?,?)",
                  ("admin", admin_pw, "admin@bagcounter.com", "admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except:
        pass
    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Access denied — Admin only!", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def operator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") == "viewer":
            flash("Access denied — Operators and Admins only!", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# ── Auth Routes ───────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND is_active=1",
                            (username, hash_pw(password))).fetchone()
        if user:
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            session["role"]     = user["role"]
            conn.execute("UPDATE users SET last_login=? WHERE id=?",
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
            conn.commit()
            conn.close()
            return redirect(url_for("dashboard"))
        conn.close()
        flash("Invalid username or password!", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()
        conn  = get_db()
        user  = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = secrets.token_hex(16)
            conn.execute("UPDATE users SET reset_token=? WHERE email=?", (token, email))
            conn.commit()
            conn.close()
            # In production send email — for now show token
            flash(f"Reset token generated! Use this token: {token}", "success")
            return redirect(url_for("reset_password", token=token))
        conn.close()
        flash("Email not found!", "error")
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE reset_token=?", (token,)).fetchone()
    if not user:
        conn.close()
        flash("Invalid or expired token!", "error")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        new_pw  = request.form["password"]
        confirm = request.form["confirm"]
        if new_pw != confirm:
            flash("Passwords do not match!", "error")
        elif len(new_pw) < 6:
            flash("Password must be at least 6 characters!", "error")
        else:
            conn.execute("UPDATE users SET password=?, reset_token=NULL WHERE id=?",
                         (hash_pw(new_pw), user["id"]))
            conn.commit()
            conn.close()
            flash("Password reset successfully! Please login.", "success")
            return redirect(url_for("login"))
    conn.close()
    return render_template("reset_password.html", token=token)

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form["current_password"]
        new_pw  = request.form["new_password"]
        confirm = request.form["confirm_password"]
        conn    = get_db()
        user    = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if user["password"] != hash_pw(current):
            flash("Current password is incorrect!", "error")
        elif new_pw != confirm:
            flash("New passwords do not match!", "error")
        elif len(new_pw) < 6:
            flash("Password must be at least 6 characters!", "error")
        else:
            conn.execute("UPDATE users SET password=? WHERE id=?",
                         (hash_pw(new_pw), session["user_id"]))
            conn.commit()
            conn.close()
            flash("Password changed successfully!", "success")
            return redirect(url_for("dashboard"))
        conn.close()
    return render_template("change_password.html")

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    # Filters
    f_year  = request.args.get("year",  "")
    f_month = request.args.get("month", "")
    f_date  = request.args.get("date",  "")

    where, params = [], []
    if f_year:
        where.append("strftime('%Y', started_at) = ?"); params.append(f_year)
    if f_month:
        where.append("strftime('%m', started_at) = ?"); params.append(f_month.zfill(2))
    if f_date:
        where.append("DATE(started_at) = ?"); params.append(f_date)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn     = get_db()
    sessions = conn.execute(
        f"SELECT s.*, u.username FROM sessions s JOIN users u ON s.user_id=u.id {where_sql.replace('started_at', 's.started_at')} ORDER BY s.started_at DESC LIMIT 20",
        params
    ).fetchall()
    total_bags     = conn.execute("SELECT SUM(total_count) FROM sessions WHERE status='done'").fetchone()[0] or 0
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] or 0
    today_bags     = conn.execute(
        "SELECT SUM(total_count) FROM sessions WHERE DATE(started_at)=DATE('now') AND status='done'"
    ).fetchone()[0] or 0

    # Available years for filter dropdown
    years  = [r[0] for r in conn.execute("SELECT DISTINCT strftime('%Y', started_at) FROM sessions ORDER BY 1 DESC").fetchall()]
    conn.close()

    return render_template("dashboard.html",
                           sessions=sessions,
                           total_bags=total_bags,
                           total_sessions=total_sessions,
                           today_bags=today_bags,
                           years=years,
                           f_year=f_year, f_month=f_month, f_date=f_date)

# ── Counting Page ─────────────────────────────────────────────────────────────
@app.route("/count", methods=["GET", "POST"])
@operator_required
def count():
    if request.method == "POST":
        source_type  = request.form.get("source_type", "video")
        session_name = request.form.get("session_name", f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        save_video   = request.form.get("save_video") == "on"
        save_csv     = request.form.get("save_csv") == "on"
        line_pos     = float(request.form.get("line_pos", 0.5))
        conf_thresh  = float(request.form.get("conf_thresh", 0.4))
        rtsp_url     = request.form.get("rtsp_url", "")

        video_path = ""
        if source_type == "video" and "video_file" in request.files:
            f = request.files["video_file"]
            if f.filename:
                video_path = os.path.join(UPLOAD_FOLDER, f.filename)
                f.save(video_path)

        # Save session to DB
        conn = get_db()
        cur  = conn.execute(
            "INSERT INTO sessions (user_id, session_name, source_type, video_path, started_at, status) VALUES (?,?,?,?,?,?)",
            (session["user_id"], session_name, source_type,
             video_path if source_type == "video" else rtsp_url,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "running"))
        session_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Store config in session for live updates
        session["active_session_id"] = session_id
        session["count_config"] = {
            "source": video_path if source_type == "video" else rtsp_url,
            "save_video": save_video,
            "save_csv": save_csv,
            "line_pos": line_pos,
            "conf_thresh": conf_thresh,
            "session_id": session_id,
            "session_name": session_name
        }
        # Auto-launch run_count.py via a temp batch file
        import subprocess, sys
        project_dir = os.path.dirname(os.path.abspath(__file__))
        python      = sys.executable
        script      = os.path.join(project_dir, "run_count.py")
        sv          = "1" if save_video else "0"
        sc          = "1" if save_csv   else "0"
        bat_path    = os.path.join(project_dir, "_launch.bat")
        with open(bat_path, "w") as bat:
            bat.write(f'@echo off\n')
            bat.write(f'cd /d "{project_dir}"\n')
            bat.write(f'"{python}" "{script}" {session_id} {line_pos} {conf_thresh} {sv} {sc}\n')
            bat.write(f'pause\n')
        subprocess.Popen(f'start cmd /k "{bat_path}"', shell=True)
        flash(f"Session '{session_name}' started! Video window opening...", "success")
        return redirect(url_for("live_view", session_id=session_id))

    return render_template("count.html")

@app.route("/live/<int:session_id>")
@operator_required
def live_view(session_id):
    conn    = get_db()
    sess    = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    config  = session.get("count_config", {})
    return render_template("live.html", sess=sess, config=config)

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route("/reports")
@login_required
def reports():
    f_year   = request.args.get("year",   "")
    f_month  = request.args.get("month",  "")
    f_date   = request.args.get("date",   "")
    f_status = request.args.get("status", "")

    where, params = [], []
    if f_year:
        where.append("strftime('%Y', s.started_at) = ?"); params.append(f_year)
    if f_month:
        where.append("strftime('%m', s.started_at) = ?"); params.append(f_month.zfill(2))
    if f_date:
        where.append("DATE(s.started_at) = ?"); params.append(f_date)
    if f_status:
        where.append("s.status = ?"); params.append(f_status)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn     = get_db()
    sessions = conn.execute(
        f"SELECT s.*, u.username FROM sessions s JOIN users u ON s.user_id=u.id {where_sql} ORDER BY s.started_at DESC",
        params
    ).fetchall()
    years = [r[0] for r in conn.execute("SELECT DISTINCT strftime('%Y', started_at) FROM sessions ORDER BY 1 DESC").fetchall()]
    conn.close()
    return render_template("reports.html", sessions=sessions, years=years,
                           f_year=f_year, f_month=f_month, f_date=f_date, f_status=f_status)

@app.route("/reports/download/<int:session_id>")
@login_required
def download_report(session_id):
    conn = get_db()
    sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    if sess and sess["csv_path"] and os.path.exists(sess["csv_path"]):
        return send_file(sess["csv_path"], as_attachment=True)
    flash("Report not found!", "error")
    return redirect(url_for("reports"))

# ── User Management (Admin only) ──────────────────────────────────────────────
@app.route("/users")
@admin_required
def users():
    conn  = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("users.html", users=users)

@app.route("/users/add", methods=["GET", "POST"])
@admin_required
def add_user():
    if request.method == "POST":
        username = request.form["username"].strip()
        email    = request.form["email"].strip()
        password = request.form["password"]
        role     = request.form["role"]
        conn     = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password, email, role, created_at) VALUES (?,?,?,?,?)",
                (username, hash_pw(password), email, role,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash(f"User '{username}' created successfully!", "success")
            return redirect(url_for("users"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists!", "error")
        finally:
            conn.close()
    return render_template("add_user.html")

@app.route("/users/toggle/<int:user_id>")
@admin_required
def toggle_user(user_id):
    if user_id == session["user_id"]:
        flash("Cannot deactivate your own account!", "error")
        return redirect(url_for("users"))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    new_status = 0 if user["is_active"] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
    conn.commit()
    conn.close()
    flash(f"User {'activated' if new_status else 'deactivated'} successfully!", "success")
    return redirect(url_for("users"))

@app.route("/users/delete/<int:user_id>")
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        flash("Cannot delete your own account!", "error")
        return redirect(url_for("users"))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for("users"))


@app.route("/api/session-stats/<int:session_id>")
@login_required
def session_stats(session_id):
    conn = get_db()
    sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    if not sess:
        return jsonify({"total":0,"count_in":0,"count_out":0,"status":"unknown"})
    return jsonify({
        "total":    sess["total_count"],
        "count_in": sess["count_in"],
        "count_out":sess["count_out"],
        "status":   sess["status"]
    })


@app.route("/sessions/delete/<int:session_id>")
@admin_required
def delete_session(session_id):
    conn = get_db()
    sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if sess:
        # Delete CSV file if exists
        if sess["csv_path"] and os.path.exists(sess["csv_path"]):
            os.remove(sess["csv_path"])
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        flash(f"Session #{session_id} deleted!", "success")
    else:
        flash("Session not found!", "error")
    conn.close()
    return redirect(url_for("reports"))

# ── API for live count updates ────────────────────────────────────────────────
@app.route("/api/update-count", methods=["POST"])
@login_required
def update_count():
    data       = request.json
    session_id = data.get("session_id")
    conn       = get_db()
    conn.execute(
        "UPDATE sessions SET total_count=?, count_in=?, count_out=?, csv_path=?, status=?, ended_at=? WHERE id=?",
        (data.get("total", 0), data.get("count_in", 0), data.get("count_out", 0),
         data.get("csv_path", ""), data.get("status", "running"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S") if data.get("status") == "done" else None,
         session_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    print("\n" + "="*45)
    print("  Train Cargo Bag Counter — Web App")
    print("  URL  : http://localhost:5000")
    print("  Login: admin / admin123")
    print("="*45 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
