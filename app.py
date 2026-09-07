from flask import Flask, render_template, request, session, redirect, url_for
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import secrets
import os

load_dotenv()

app = Flask(__name__)

# ================= SESSION =================

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "smart-attendance-teacher-key"
)


# ================= SUPABASE =================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_KEY is missing."
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ================= TEACHER CREDENTIALS =================

TEACHER_EMAIL = "shivapandey1418@gmail.com"

# Keep your existing teacher password here for now.
TEACHER_PASSWORD = "shiva@121929"


# ================= TEACHER LOGIN =================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if email == TEACHER_EMAIL and password == TEACHER_PASSWORD:

            session["teacher_logged_in"] = True

            return redirect(url_for("dashboard"))

        return render_template(
            "index.html",
            error="Invalid email or password."
        )

    return render_template("index.html")


# ================= TEACHER DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:

        result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,roll_number,email,contact"
            )
            .order("roll_number")
            .execute()
        )

        students = result.data or []

        return render_template(
            "dashboard.html",
            students=students
        )

    except Exception as error:

        print("DASHBOARD ERROR:", repr(error))

        return "Unable to load student data."


# ================= GENERATE QR =================

@app.route("/generate-qr")
def generate_qr():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:

        # Deactivate previous QR sessions
        supabase.table("attendance_sessions").update({
            "active": False
        }).eq("active", True).execute()

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Save new QR session
        supabase.table("attendance_sessions").insert({
            "token": token,
            "date": today,
            "active": True
        }).execute()

        # Student website URL
        student_app_url = os.getenv("STUDENT_APP_URL")

        if not student_app_url:
            return "Student application URL is not configured."

        student_url = (
            student_app_url.rstrip("/")
            + "/attendance/"
            + token
        )

        return render_template(
            "qr.html",
            qr_url=student_url,
            token=token,
            date=today
        )

    except Exception as error:

        print("QR ERROR:", repr(error))

        return "Unable to generate QR code. Please try again."


# ================= TODAY'S ATTENDANCE =================

@app.route("/today-attendance")
def today_attendance():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:
        today = datetime.now().strftime("%Y-%m-%d")

        # Get all students
        students_result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,roll_number,email,contact"
            )
            .order("roll_number")
            .execute()
        )

        students = students_result.data or []

        # Get today's attendance
        attendance_result = (
            supabase
            .table("attendance")
            .select("student_id,date,time,status")
            .eq("date", today)
            .execute()
        )

        attendance_data = attendance_result.data or []

        attendance_map = {}

        for record in attendance_data:
            attendance_map[record["student_id"]] = record

        records = []

        for student in students:

            student_id = student["id"]

            if student_id in attendance_map:

                attendance = attendance_map[student_id]

                status = attendance["status"]
                time = attendance["time"]

            else:

                status = "Absent"
                time = "-"

            records.append({
                "roll_number": student["roll_number"],
                "name": student["name"],
                "class_name": student["class_name"],
                "status": status,
                "time": time
            })

        present_count = sum(
            1 for record in records
            if record["status"] == "Present"
        )

        absent_count = len(records) - present_count

        return render_template(
            "today_attendance.html",
            records=records,
            date=today,
            present_count=present_count,
            absent_count=absent_count
        )

    except Exception as error:

        print("TODAY ATTENDANCE ERROR:", repr(error))

        return "Unable to load today's attendance."


# ================= MONTHLY RECORD =================

@app.route("/monthly-record")
def monthly_record():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:

        month = request.args.get(
            "month",
            datetime.now().strftime("%Y-%m")
        )

        # Get all students
        students_result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,roll_number"
            )
            .order("roll_number")
            .execute()
        )

        students = students_result.data or []

        # Get attendance records
        attendance_result = (
            supabase
            .table("attendance")
            .select(
                "student_id,date,time,status"
            )
            .execute()
        )

        attendance_data = attendance_result.data or []

        records = []

        for student in students:

            present = 0
            absent = 0

            for attendance in attendance_data:

                if attendance["student_id"] != student["id"]:
                    continue

                record_date = str(attendance["date"])

                if record_date.startswith(month):

                    if attendance["status"] == "Present":
                        present += 1

                    elif attendance["status"] == "Absent":
                        absent += 1

            total = present + absent

            percentage = 0

            if total > 0:
                percentage = round(
                    (present / total) * 100,
                    2
                )

            records.append({
                "roll_number": student["roll_number"],
                "name": student["name"],
                "father_name": student["father_name"],
                "class_name": student["class_name"],
                "present": present,
                "absent": absent,
                "total": total,
                "percentage": percentage
            })

        return render_template(
            "monthly_record.html",
            records=records,
            month=month
        )

    except Exception as error:

        print("MONTHLY RECORD ERROR:", repr(error))

        return "Unable to load monthly attendance."


# ================= EXPORT PDF =================

@app.route("/export-pdf")
def export_pdf():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:

        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        month = request.args.get(
            "month",
            datetime.now().strftime("%Y-%m")
        )

        # Get students
        students_result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,roll_number"
            )
            .order("roll_number")
            .execute()
        )

        students = students_result.data or []

        # Get attendance
        attendance_result = (
            supabase
            .table("attendance")
            .select(
                "student_id,date,time,status"
            )
            .execute()
        )

        attendance_data = attendance_result.data or []

        pdf_records = []

        for student in students:

            present = 0
            absent = 0

            for attendance in attendance_data:

                if attendance["student_id"] != student["id"]:
                    continue

                record_date = str(attendance["date"])

                if record_date.startswith(month):

                    if attendance["status"] == "Present":
                        present += 1

                    elif attendance["status"] == "Absent":
                        absent += 1

            total = present + absent

            percentage = 0

            if total > 0:
                percentage = round(
                    (present / total) * 100,
                    2
                )

            pdf_records.append([
                student["roll_number"],
                student["name"],
                student["class_name"],
                present,
                absent,
                total,
                f"{percentage}%"
            ])

        # Create PDF
        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        elements = []

        elements.append(
            Paragraph(
                "SmartAttendance - Monthly Attendance Report",
                styles["Title"]
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        elements.append(
            Paragraph(
                f"Month: {month}",
                styles["Normal"]
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        table_data = [
            [
                "Roll No.",
                "Name",
                "Class",
                "Present",
                "Absent",
                "Total",
                "Percentage"
            ]
        ]

        table_data.extend(pdf_records)

        table = Table(
            table_data,
            repeatRows=1
        )

        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (3, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ])
        )

        elements.append(table)

        document.build(elements)

        buffer.seek(0)

        from flask import send_file

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"attendance_{month}.pdf",
            mimetype="application/pdf"
        )

    except Exception as error:

        print("PDF ERROR:", repr(error))

        return "Unable to generate PDF report."





# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ================= RUN APP =================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )