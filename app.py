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


@app.route("/create-student", methods=["GET", "POST"])
def create_student():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        father_name = request.form.get("father_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        email = request.form.get("email", "").strip()
        contact = request.form.get("contact", "").strip()
        password = request.form.get("password", "")

        if not all([
            name, father_name, class_name,
            roll_number, email, contact, password
        ]):
            return render_template(
                "create_student.html",
                error="Please fill in all fields."
            )

        try:
            # Check duplicate email
            email_check = (
                supabase
                .table("students")
                .select("id")
                .eq("email", email)
                .execute()
            )

            if email_check.data:
                return render_template(
                    "create_student.html",
                    error="A student with this email already exists."
                )

            # Check duplicate roll number
            roll_check = (
                supabase
                .table("students")
                .select("id")
                .eq("roll_number", roll_number)
                .execute()
            )

            if roll_check.data:
                return render_template(
                    "create_student.html",
                    error="A student with this roll number already exists."
                )

            # Create student account
            supabase.table("students").insert({
                "name": name,
                "father_name": father_name,
                "class_name": class_name,
                "roll_number": roll_number,
                "email": email,
                "contact": contact,
                "password": password
            }).execute()

            return redirect(url_for("dashboard"))

        except Exception as error:
            print("CREATE STUDENT ERROR:", repr(error))
            return render_template(
                "create_student.html",
                error="Unable to create student account. Please try again."
            )

    return render_template("create_student.html")

# ================= GENERATE QR =================

@app.route("/generate-qr")
def generate_qr():

    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:

        # Today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Save QR session
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

        selected_date = request.args.get("selected_date", "")

        # Get students
        students_result = (
            supabase
            .table("students")
            .select("id,name,father_name,class_name,roll_number")
            .order("roll_number")
            .execute()
        )

        students = students_result.data or []

        # Get attendance records
        attendance_result = (
            supabase
            .table("attendance")
            .select("student_id,date,time,status")
            .execute()
        )

        attendance_data = attendance_result.data or []

        # Create date list for selected month
        year = int(month.split("-")[0])
        month_number = int(month.split("-")[1])

        if month_number == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month_number + 1, 1)

        first_day = datetime(year, month_number, 1)
        number_of_days = (next_month - first_day).days

        days = list(range(1, number_of_days + 1))

        # Create attendance register
        records = []

        for student in students:

            daily = {}
            present = 0
            absent = 0

            for day in days:

                date_string = f"{month}-{day:02d}"

                matching_record = None

                for attendance in attendance_data:

                    if (
                        attendance["student_id"] == student["id"]
                        and str(attendance["date"]) == date_string
                    ):
                        matching_record = attendance
                        break

                if matching_record:

                    status = matching_record["status"]
                    daily[day] = status

                    if status == "Present":
                        present += 1

                    elif status == "Absent":
                        absent += 1

                else:
                    daily[day] = None

            total = present + absent

            percentage = (
                round((present / total) * 100, 2)
                if total > 0 else 0
            )

            records.append({
                "roll_number": student["roll_number"],
                "name": student["name"],
                "father_name": student["father_name"],
                "class_name": student["class_name"],
                "daily": daily,
                "present": present,
                "absent": absent,
                "total": total,
                "percentage": percentage
            })

        # Selected date information
        selected_records = []
        selected_present = 0
        selected_absent = 0

        if selected_date:

            for student in students:

                matching_record = None

                for attendance in attendance_data:

                    if (
                        attendance["student_id"] == student["id"]
                        and str(attendance["date"]) == selected_date
                    ):
                        matching_record = attendance
                        break

                if matching_record:
                    status = matching_record["status"]
                    time = matching_record["time"]
                else:
                    status = "Absent"
                    time = "-"

                if status == "Present":
                    selected_present += 1
                else:
                    selected_absent += 1

                selected_records.append({
                    "roll_number": student["roll_number"],
                    "name": student["name"],
                    "status": status,
                    "time": time
                })

        selected_total = selected_present + selected_absent

        selected_percentage = (
            round((selected_present / selected_total) * 100, 2)
            if selected_total > 0 else 0
        )

        return render_template(
            "monthly_record.html",
            records=records,
            month=month,
            days=days,
            selected_date=selected_date,
            selected_records=selected_records,
            selected_present=selected_present,
            selected_absent=selected_absent,
            selected_total=selected_total,
            selected_percentage=selected_percentage
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
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.units import mm
        from flask import send_file
        import calendar

        month = request.args.get(
            "month",
            datetime.now().strftime("%Y-%m")
        )

        # -----------------------------------
        # MONTH INFORMATION
        # -----------------------------------

        year = int(month.split("-")[0])
        month_number = int(month.split("-")[1])

        month_name = calendar.month_name[month_number]
        days_in_month = calendar.monthrange(
            year,
            month_number
        )[1]

        days = list(range(1, days_in_month + 1))

        # -----------------------------------
        # GET STUDENTS
        # -----------------------------------

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

        # -----------------------------------
        # GET ATTENDANCE
        # -----------------------------------

        attendance_result = (
            supabase
            .table("attendance")
            .select(
                "student_id,date,time,status"
            )
            .execute()
        )

        attendance_data = attendance_result.data or []

        # -----------------------------------
        # CREATE ATTENDANCE LOOKUP
        # -----------------------------------

        attendance_map = {}

        for attendance in attendance_data:

            date_value = str(attendance["date"])

            if date_value.startswith(month):

                key = (
                    attendance["student_id"],
                    date_value
                )

                attendance_map[key] = attendance

        # -----------------------------------
        # PDF BUFFER
        # -----------------------------------

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=10 * mm,
            leftMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm
        )

        styles = getSampleStyleSheet()

        # -----------------------------------
        # CUSTOM STYLES
        # -----------------------------------

        brand_style = ParagraphStyle(
            "BrandStyle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            alignment=TA_CENTER,
            textColor=colors.white
        )

        subtitle_style = ParagraphStyle(
            "SubtitleStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.white
        )

        normal_style = ParagraphStyle(
            "NormalSmall",
            parent=styles["Normal"],
            fontSize=7,
            leading=9
        )

        # -----------------------------------
        # PDF ELEMENTS
        # -----------------------------------

        elements = []

        # -----------------------------------
        # SMARTATTENDANCE BRAND HEADER
        # -----------------------------------

        brand_header = Table(
            [
                [
                    Paragraph(
                        "SmartAttendance",
                        brand_style
                    )
                ],
                [
                    Paragraph(
                        "(SA) • Smart School Attendance System",
                        subtitle_style
                    )
                ]
            ],
            colWidths=[277 * mm]
        )

        brand_header.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#111116")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    2,
                    colors.HexColor("#ff3b30")
                ),

                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    1,
                    colors.HexColor("#ff3b30")
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, 0),
                    10
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, 0),
                    4
                ),

                (
                    "TOPPADDING",
                    (0, 1),
                    (-1, 1),
                    2
                ),

                (
                    "BOTTOMPADDING",
                    (0, 1),
                    (-1, 1),
                    9
                )
            ])
        )

        elements.append(brand_header)

        elements.append(
            Spacer(1, 8)
        )

        # -----------------------------------
        # REPORT INFORMATION
        # -----------------------------------

        report_info = Table(
            [
                [
                    Paragraph(
                        "<b>Monthly Attendance Report</b>",
                        styles["Heading2"]
                    ),
                    Paragraph(
                        f"<b>Month:</b> {month_name} {year}",
                        styles["Normal"]
                    )
                ]
            ],
            colWidths=[
                180 * mm,
                97 * mm
            ]
        )

        report_info.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#eeeeee")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    colors.HexColor("#bbbbbb")
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        elements.append(report_info)

        elements.append(
            Spacer(1, 8)
        )

        # -----------------------------------
        # TABLE HEADER
        # -----------------------------------

        table_data = [
            [
                "Roll",
                "Student Name"
            ]
            + [str(day) for day in days]
            + [
                "Present",
                "Absent",
                "Total",
                "%"
            ]
        ]

        # -----------------------------------
        # STUDENT ROWS
        # -----------------------------------

        for student in students:

            present = 0
            absent = 0

            row = [
                str(student["roll_number"]),
                Paragraph(
                    str(student["name"]),
                    normal_style
                )
            ]

            for day in days:

                date_string = (
                    f"{month}-{day:02d}"
                )

                key = (
                    student["id"],
                    date_string
                )

                attendance = attendance_map.get(key)

                if attendance:

                    status = attendance["status"]

                    if status == "Present":

                        row.append("PRESENT")
                        present += 1

                    elif status == "Absent":

                        row.append("ABSENT")
                        absent += 1

                    else:

                        row.append("-")

                else:

                    row.append("-")

            total = present + absent

            percentage = (
                round(
                    (present / total) * 100,
                    2
                )
                if total > 0
                else 0
            )

            row.extend([
                str(present),
                str(absent),
                str(total),
                f"{percentage}%"
            ])

            table_data.append(row)

        # -----------------------------------
        # COLUMN WIDTHS
        # -----------------------------------

        date_width = 7.1 * mm

        column_widths = [
            12 * mm,
            38 * mm
        ]

        column_widths += [
            date_width
            for _ in days
        ]

        column_widths += [
            15 * mm,
            15 * mm,
            15 * mm,
            15 * mm
        ]

        # -----------------------------------
        # ATTENDANCE TABLE
        # -----------------------------------

        attendance_table = Table(
            table_data,
            colWidths=column_widths,
            repeatRows=1
        )

        style_commands = [

            # Header
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#292934")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#aaaaaa")
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f7f7f7")
                ]
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ]

        # -----------------------------------
        # COLOR PRESENT / ABSENT CELLS
        # -----------------------------------

        for row_index in range(
            1,
            len(table_data)
        ):

            for col_index in range(
                2,
                2 + len(days)
            ):

                value = table_data[
                    row_index
                ][col_index]

                if value == "PRESENT":

                    style_commands.append(
                        (
                            "BACKGROUND",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            colors.HexColor("#d9f7df")
                        )
                    )

                    style_commands.append(
                        (
                            "TEXTCOLOR",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            colors.HexColor("#16833a")
                        )
                    )

                    style_commands.append(
                        (
                            "FONTNAME",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            "Helvetica-Bold"
                        )
                    )

                elif value == "ABSENT":

                    style_commands.append(
                        (
                            "BACKGROUND",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            colors.HexColor("#ffe0e0")
                        )
                    )

                    style_commands.append(
                        (
                            "TEXTCOLOR",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            colors.HexColor("#c62828")
                        )
                    )

                    style_commands.append(
                        (
                            "FONTNAME",
                            (
                                col_index,
                                row_index
                            ),
                            (
                                col_index,
                                row_index
                            ),
                            "Helvetica-Bold"
                        )
                    )

        attendance_table.setStyle(
            TableStyle(style_commands)
        )

        elements.append(
            attendance_table
        )

        elements.append(
            Spacer(1, 8)
        )

        # -----------------------------------
        # FOOTER / BRANDING
        # -----------------------------------

        footer = Table(
            [
                [
                    Paragraph(
                        "<b>SmartAttendance (SA)</b> — "
                        "Generated attendance report",
                        normal_style
                    ),
                    Paragraph(
                        f"Generated: "
                        f"{datetime.now().strftime('%d %B %Y, %I:%M %p')}",
                        normal_style
                    )
                ]
            ],
            colWidths=[
                180 * mm,
                97 * mm
            ]
        )

        footer.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#f1f1f1")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#bbbbbb")
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ])
        )

        elements.append(footer)

        # -----------------------------------
        # BUILD PDF
        # -----------------------------------

        document.build(elements)

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"SmartAttendance_{month}.pdf",
            mimetype="application/pdf"
        )

    except Exception as error:

        print(
            "PDF ERROR:",
            repr(error)
        )

        return "Unable to generate PDF report."

#-------------------------------------------------------------------------
@app.route("/students")
def students():
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
            "students.html",
            students=students
        )

    except Exception as error:
        print("STUDENTS ERROR:", repr(error))
        return "Unable to load students."


@app.route("/student/<int:student_id>")
def student_profile(student_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:
        result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,"
                "roll_number,email,contact,password"
            )
            .eq("id", student_id)
            .execute()
        )

        if not result.data:
            return "Student profile not found."

        student = result.data[0]

        attendance_result = (
            supabase
            .table("attendance")
            .select("date,time,status")
            .eq("student_id", student_id)
            .order("date", desc=True)
            .execute()
        )

        attendance = attendance_result.data or []

        present_count = sum(
            1
            for record in attendance
            if record["status"] == "Present"
        )

        absent_count = sum(
            1
            for record in attendance
            if record["status"] == "Absent"
        )

        total = present_count + absent_count

        percentage = (
            round((present_count / total) * 100, 2)
            if total > 0
            else 0
        )

        return render_template(
            "student_profile.html",
            student=student,
            attendance=attendance,
            present_count=present_count,
            absent_count=absent_count,
            total=total,
            percentage=percentage
        )

    except Exception as error:
        print("STUDENT PROFILE ERROR:", repr(error))
        return "Unable to load student profile."


@app.route("/student/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:
        student_result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,"
                "roll_number,email,contact"
            )
            .eq("id", student_id)
            .single()
            .execute()
        )

        student = student_result.data

        if not student:
            return "Student not found."

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            father_name = request.form.get("father_name", "").strip()
            class_name = request.form.get("class_name", "").strip()
            roll_number = request.form.get("roll_number", "").strip()
            email = request.form.get("email", "").strip()
            contact = request.form.get("contact", "").strip()

            if not all([
                name,
                father_name,
                class_name,
                roll_number,
                email,
                contact
            ]):
                return render_template(
                    "edit_student.html",
                    student=student,
                    error="All fields are required."
                )

            supabase.table("students").update({
                "name": name,
                "father_name": father_name,
                "class_name": class_name,
                "roll_number": roll_number,
                "email": email,
                "contact": contact
            }).eq(
                "id", student_id
            ).execute()

            return redirect(
                url_for(
                    "student_profile",
                    student_id=student_id
                )
            )

        return render_template(
            "edit_student.html",
            student=student
        )

    except Exception as error:
        print("EDIT STUDENT ERROR:", repr(error))
        return "Unable to update student information."


@app.route("/student/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    try:
        supabase.table("students").delete().eq(
            "id", student_id
        ).execute()

        return redirect(url_for("students"))

    except Exception as error:
        print("DELETE STUDENT ERROR:", repr(error))
        return "Unable to delete student."


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
