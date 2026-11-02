import os
import re
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from .database import query
    from .geofence import check as check_geofence
except ImportError:  # Supports running app.py directly from backend/ as well.
    from database import query
    from geofence import check as check_geofence


# app.py is inside backend/, so its parent directory is the project root.
BASE = Path(__file__).resolve().parent.parent
ENV_FILE = BASE / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

app = Flask(
    __name__,
    static_folder=str(BASE / "frontend"),
    static_url_path="/static",
)

secret_key = os.getenv("FLASK_SECRET_KEY", "").strip()
if len(secret_key) < 32:
    raise RuntimeError(
        f"FLASK_SECRET_KEY is missing or too short. Add a random key "
        f"of at least 32 characters to: {ENV_FILE}"
    )

app.secret_key = secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
)

UPLOAD_FOLDER = BASE / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

try:
    CAMPUS_LAT = float(os.getenv("CAMPUS_LAT", "16.9951463487529"))
    CAMPUS_LON = float(os.getenv("CAMPUS_LON", "81.79950858287084"))
    CAMPUS_RADIUS_M = float(os.getenv("CAMPUS_RADIUS_M", "100"))
    MAX_GPS_ACCURACY_M = float(os.getenv("MAX_GPS_ACCURACY_M", "50"))
    PORT = int(os.getenv("PORT", "5000"))
except ValueError as exc:
    raise RuntimeError("Campus GPS settings and PORT must contain valid numbers.") from exc

if not (-90 <= CAMPUS_LAT <= 90 and -180 <= CAMPUS_LON <= 180):
    raise RuntimeError("CAMPUS_LAT or CAMPUS_LON is outside the valid GPS range.")
if CAMPUS_RADIUS_M <= 0 or MAX_GPS_ACCURACY_M <= 0:
    raise RuntimeError("Campus radius and maximum GPS accuracy must be positive.")
if not (1 <= PORT <= 65535):
    raise RuntimeError("PORT must be between 1 and 65535.")

print(f"Project folder: {BASE}")
print(f"Environment file: {ENV_FILE}")
print(f"Environment file exists: {ENV_FILE.is_file()}")
print("Secret key loaded:", bool(secret_key))
print(f"Starting Attendance-Snap on http://127.0.0.1:{PORT}")


def require_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("uid"):
            return jsonify(error="Please sign in."), 401
        return view(*args, **kwargs)
    return wrapped


def serve_page(filename):
    return send_from_directory(app.static_folder, filename)


@app.get("/")
def home():
    return serve_page("index.html")


@app.get("/login")
def login_page():
    return serve_page("login.html")


@app.get("/register")
def register_page():
    return serve_page("register.html")


@app.get("/dashboard")
def dashboard_page():
    return serve_page("dashboard.html")


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = data.get("role")
    avatar = data.get("avatar")
    class_name = str(data.get("class_name", "")).strip()[:80]

    if not name or len(name) > 100:
        return jsonify(error="Enter a name of up to 100 characters."), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Password must contain at least 8 characters."), 400
    if role not in ("student", "teacher"):
        return jsonify(error="Choose Student or Teacher as the account type."), 400
    if avatar not in ("male", "female", "neutral"):
        return jsonify(error="Choose a valid avatar style."), 400

    try:
        query(
            "INSERT INTO users (name, email, password_hash, role, avatar, class_name) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (name, email, generate_password_hash(password), role, avatar, class_name or None),
        )
    except IntegrityError:
        return jsonify(error="This email is already registered."), 409

    users = query(
        "SELECT id, name, role, avatar, class_name FROM users WHERE email = %s",
        (email,),
        fetch=True,
    )
    if not users:
        return jsonify(error="Account was created but could not be loaded. Please sign in."), 500

    user = users[0]
    session.clear()
    session["uid"] = user["id"]
    session["role"] = user["role"]
    return jsonify(user=user), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    users = query(
        "SELECT id, name, email, password_hash, role, avatar, class_name "
        "FROM users WHERE email = %s",
        (email,),
        fetch=True,
    )

    if not users or not check_password_hash(users[0]["password_hash"], password):
        return jsonify(error="Incorrect email or password."), 401

    user = users[0]
    session.clear()
    session["uid"] = user["id"]
    session["role"] = user["role"]
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@require_login
def current_user():
    users = query(
        "SELECT id, name, role, avatar, class_name FROM users WHERE id = %s",
        (session["uid"],),
        fetch=True,
    )
    if not users:
        session.clear()
        return jsonify(error="Account not found. Please sign in again."), 404
    return jsonify(user=users[0])


@app.post("/api/attendance")
@require_login
def mark_attendance():
    if session.get("role") != "student":
        return jsonify(error="Only student accounts can mark attendance."), 403

    photo = request.files.get("photo")
    if not photo or not photo.filename:
        return jsonify(error="Capture a photo before submitting attendance."), 400

    extension = Path(secure_filename(photo.filename)).suffix.lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp"):
        return jsonify(error="Photo must be JPG, PNG or WEBP."), 400

    try:
        latitude = float(request.form["latitude"])
        longitude = float(request.form["longitude"])
        accuracy = float(request.form["accuracy"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Valid GPS coordinates and accuracy are required."), 400

    accepted, distance_m, message = check_geofence(
        latitude,
        longitude,
        accuracy,
        CAMPUS_LAT,
        CAMPUS_LON,
        CAMPUS_RADIUS_M,
        MAX_GPS_ACCURACY_M,
    )
    if not accepted:
        return jsonify(error=message), 403

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    attendance_date = now.date()
    existing = query(
        "SELECT id FROM attendance WHERE user_id = %s AND attendance_date = %s",
        (session["uid"], attendance_date),
        fetch=True,
    )
    if existing:
        return jsonify(error="Attendance has already been marked today."), 409

    filename = f"{session['uid']}_{uuid.uuid4().hex}{extension}"
    saved_path = UPLOAD_FOLDER / filename
    photo.save(saved_path)

    try:
        query(
            "INSERT INTO attendance "
            "(user_id, attendance_date, attendance_time, photo_filename, latitude, "
            "longitude, gps_accuracy_m, distance_m) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session["uid"],
                attendance_date,
                now.time().replace(microsecond=0),
                filename,
                latitude,
                longitude,
                accuracy,
                distance_m,
            ),
        )
    except IntegrityError:
        saved_path.unlink(missing_ok=True)
        return jsonify(error="Attendance has already been marked today."), 409
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise

    return jsonify(
        message="Attendance marked successfully. Your avatar is celebrating!",
        distance_m=round(distance_m, 1),
    ), 201


@app.get("/api/attendance/mine")
@require_login
def my_attendance():
    if session.get("role") != "student":
        return jsonify(error="Student account required."), 403

    records = query(
        "SELECT attendance_date, attendance_time, distance_m "
        "FROM attendance WHERE user_id = %s ORDER BY attendance_date DESC",
        (session["uid"],),
        fetch=True,
    )
    return jsonify(records=[
        {
            "date": str(row["attendance_date"]),
            "time": str(row["attendance_time"]),
            "distance_m": float(row["distance_m"]),
        }
        for row in records
    ])


@app.get("/api/teacher/records")
@require_login
def teacher_records():
    if session.get("role") != "teacher":
        return jsonify(error="Teacher account required."), 403

    class_name = request.args.get("class_name", "").strip()
    if class_name:
        records = query(
            "SELECT u.name AS student_name, u.class_name, "
            "a.attendance_date, a.attendance_time "
            "FROM attendance a JOIN users u ON u.id = a.user_id "
            "WHERE u.class_name = %s ORDER BY a.attendance_date DESC",
            (class_name,),
            fetch=True,
        )
    else:
        records = query(
            "SELECT u.name AS student_name, u.class_name, "
            "a.attendance_date, a.attendance_time "
            "FROM attendance a JOIN users u ON u.id = a.user_id "
            "ORDER BY a.attendance_date DESC LIMIT 100",
            fetch=True,
        )

    return jsonify(records=[
        {
            "student_name": row["student_name"],
            "class_name": row["class_name"] or "",
            "date": str(row["attendance_date"]),
            "time": str(row["attendance_time"]),
        }
        for row in records
    ])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False)
