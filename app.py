from flask import Flask, render_template, request, redirect, send_file, session, flash, url_for
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mysecretkey123"

# ------------------ DATABASE SETUP ------------------
def create_db():
    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    # Students table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            subject1 TEXT, marks1 INTEGER,
            subject2 TEXT, marks2 INTEGER,
            subject3 TEXT, marks3 INTEGER,
            total INTEGER,
            percentage REAL,
            result TEXT
        )
    """)

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)

    # Default admin
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username, password) VALUES (?,?)", ("admin", "admin"))

    # -------- NEW TABLE FOR JOIN ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            class TEXT,
            section TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    # -------- TRIGGER AFTER INSERT ----------
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trig_after_insert_students
        AFTER INSERT ON students
        FOR EACH ROW
        BEGIN
            UPDATE students SET 
                total = NEW.marks1 + NEW.marks2 + NEW.marks3,
                percentage = (NEW.marks1 + NEW.marks2 + NEW.marks3) * 100.0 / 300,
                result = CASE 
                            WHEN ((NEW.marks1 + NEW.marks2 + NEW.marks3) * 100.0 / 300) >= 35 
                            THEN 'Pass' 
                            ELSE 'Fail' 
                         END
            WHERE id = NEW.id;

            -- default class info for join
            INSERT INTO class_info(student_id, class, section)
            VALUES (NEW.id, 'BCA', 'A');
        END;
    """)

    # -------- TRIGGER AFTER UPDATE ----------
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trig_after_update_students
        AFTER UPDATE ON students
        FOR EACH ROW
        BEGIN
            UPDATE students SET 
                total = NEW.marks1 + NEW.marks2 + NEW.marks3,
                percentage = (NEW.marks1 + NEW.marks2 + NEW.marks3) * 100.0 / 300,
                result = CASE 
                            WHEN ((NEW.marks1 + NEW.marks2 + NEW.marks3) * 100.0 / 300) >= 35 
                            THEN 'Pass' 
                            ELSE 'Fail' 
                         END
            WHERE id = NEW.id;
        END;
    """)

    conn.commit()
    conn.close()


create_db()

# ------------------ LOGIN PAGE ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("students.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password!", "error")
            return redirect("/login")

    return render_template("login.html")

# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------ HOME PAGE ------------------
@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM students")
    total_students = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM students WHERE (marks1>=35 AND marks2>=35 AND marks3>=35)")
    passed = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM students WHERE (marks1<35 OR marks2<35 OR marks3<35)")
    failed = cur.fetchone()[0]

    cur.execute("SELECT AVG(percentage) FROM students")
    avg = cur.fetchone()[0]
    avg_score = round(avg, 2) if avg else 0

    conn.close()

    return render_template(
        "index.html",
        student=None,
        total_students=total_students,
        passed=passed,
        failed=failed,
        avg_score=avg_score
    )

# ------------------ ADD STUDENT ------------------
@app.route("/add", methods=["POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/login")

    name = request.form["name"]
    s1 = request.form["subject1"]
    m1 = int(request.form["marks1"])
    s2 = request.form["subject2"]
    m2 = int(request.form["marks2"])
    s3 = request.form["subject3"]
    m3 = int(request.form["marks3"])

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO students 
        (name, subject1, marks1, subject2, marks2, subject3, marks3)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, s1, m1, s2, m2, s3, m3))

    conn.commit()
    conn.close()

    return redirect("/display")

# ------------------ DISPLAY (WITH JOIN) ------------------
@app.route("/display")
def display():
    if not session.get("logged_in"):
        return redirect("/login")

    search = request.args.get("search", "")

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    if search:
        cur.execute("""
            SELECT students.*, class_info.class, class_info.section
            FROM students
            LEFT JOIN class_info ON students.id = class_info.student_id
            WHERE students.name LIKE ?
        """, ('%' + search + '%',))
    else:
        cur.execute("""
            SELECT students.*, class_info.class, class_info.section
            FROM students
            LEFT JOIN class_info ON students.id = class_info.student_id
        """)

    students = cur.fetchall()
    conn.close()

    return render_template("display.html", students=students)

# ------------------ EDIT STUDENT ------------------
@app.route("/edit/<int:id>")
def edit(id):
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE id=?", (id,))
    student = cur.fetchone()
    conn.close()

    return render_template(
        "index.html",
        student=student,
        total_students=0,
        passed=0,
        failed=0,
        avg_score=0
    )

# ------------------ UPDATE STUDENT ------------------
@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if not session.get("logged_in"):
        return redirect("/login")

    name = request.form["name"]
    s1 = request.form["subject1"]
    m1 = int(request.form["marks1"])
    s2 = request.form["subject2"]
    m2 = int(request.form["marks2"])
    s3 = request.form["subject3"]
    m3 = int(request.form["marks3"])

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE students 
        SET name=?, subject1=?, marks1=?, subject2=?, marks2=?, subject3=?, marks3=?
        WHERE id=?
    """, (name, s1, m1, s2, m2, s3, m3, id))

    conn.commit()
    conn.close()

    return redirect("/display")

# ------------------ DELETE ------------------
@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM students WHERE id=?", (id,))
    cur.execute("DELETE FROM class_info WHERE student_id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/display")

# ------------------ PDF DOWNLOAD ------------------
@app.route("/download/<int:id>")
def download_pdf(id):
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("students.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.*, class_info.class, class_info.section
        FROM students
        LEFT JOIN class_info ON students.id = class_info.student_id
        WHERE students.id=?
    """, (id,))
    s = cur.fetchone()
    conn.close()

    filename = f"report_{s[1]}.pdf"
    pdf = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Amrita Vishwa Vidyapeetham Mysuru</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        f"<b>Student Name:</b> {s[1]}<br/>"
        f"<b>Class:</b> {s[11]} - {s[12]}<br/>"
        f"<b>Date:</b> {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))

    table_data = [
        ["Subject", "Marks"],
        [s[2], s[3]],
        [s[4], s[5]],
        [s[6], s[7]],
    ]

    table = Table(table_data, colWidths=[250, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B79A1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        f"<b>Total Marks:</b> {s[8]}<br/>"
        f"<b>Percentage:</b> {round(s[9], 2)}%<br/>"
        f"<b>Result:</b> {s[10]}",
        styles["Normal"]
    ))

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Signature</b>", styles["Normal"]))

    pdf.build(elements)

    return send_file(filename, as_attachment=True)

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
