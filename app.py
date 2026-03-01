import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ================== LOAD ENV ==================
# ================== ENV VARIABLES ==================
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ================== MONGODB ==================
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    print("MongoDB Connected Successfully")
except Exception as e:
    print("MongoDB Connection Failed:", e)

db = client["change_management_db"]
requests_collection = db["change_requests"]
users_collection = db["users"]

# ================== EMAIL FUNCTION ==================
def send_email(to_email, subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Email credentials missing")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        print("Email sent to:", to_email)
        return True

    except Exception as e:
        print("Email Error:", e)
        return False

# ================== HOME ==================
@app.route("/")
def home():
    if "username" not in session:
        return redirect("/login")

    if session["role"] == "admin":
        requests_data = list(requests_collection.find().sort("date", -1))
    else:
        requests_data = list(requests_collection.find(
            {"created_by": session["username"]}
        ).sort("date", -1))

    return render_template("index.html",
                           requests=requests_data,
                           role=session["role"],
                           username=session["username"])

# ================== REGISTER ==================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not username or not email or not phone or not password:
            flash("All fields are required!", "danger")
            return redirect("/register")

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect("/register")

        if users_collection.find_one({"username": username}):
            flash("Username already exists!", "danger")
            return redirect("/register")

        users_collection.insert_one({
            "username": username,
            "email": email,
            "phone": phone,
            "password": generate_password_hash(password),
            "role": "user"
        })

        flash("Registration Successful! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")

# ================== LOGIN ==================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect("/")

        flash("Invalid Username or Password!", "danger")
        return redirect("/login")

    return render_template("login.html")

# ================== ADD REQUEST ==================
@app.route("/add", methods=["POST"])
def add_request():
    if "username" not in session:
        return redirect("/login")

    user = users_collection.find_one({"username": session["username"]})

    data = {
        "category": request.form.get("category"),
        "title": request.form["title"],
        "description": request.form["description"],
        "risk": request.form["risk"],
        "status": "Pending",
        "created_by": session["username"],
        "created_by_email": user["email"],
        "date": datetime.now()
    }

    requests_collection.insert_one(data)

    subject = "New Change Request Submitted"
    body = f"""
    <h3>New Change Request Submitted</h3>
    <p><b>Title:</b> {data['title']}</p>
    <p><b>Risk:</b> {data['risk']}</p>
    <p><b>Submitted By:</b> {data['created_by']}</p>
    """

    send_email(ADMIN_EMAIL, subject, body)

    flash("Request submitted successfully!", "success")
    return redirect("/")

# ================== UPDATE STATUS ==================
@app.route("/update/<id>/<status>")
def update_status(id, status):
    if "username" not in session or session["role"] != "admin":
        return redirect("/")

    request_data = requests_collection.find_one({"_id": ObjectId(id)})

    if not request_data:
        flash("Request not found!", "danger")
        return redirect("/")

    requests_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"status": status}}
    )

    user_email = request_data.get("created_by_email")

    if user_email:
        subject = "Your Change Request Status Updated"
        body = f"""
        <h3>Status Updated</h3>
        <p><b>Title:</b> {request_data['title']}</p>
        <p><b>New Status:</b> {status}</p>
        """
        send_email(user_email, subject, body)

    flash("Status updated successfully!", "success")
    return redirect("/")

# ================== LOGOUT ==================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================== CREATE ADMIN ==================
def create_admin():
    if not users_collection.find_one({"username": "admin"}):
        users_collection.insert_one({
            "username": "admin",
            "email": ADMIN_EMAIL,
            "phone": "9999999999",
            "password": generate_password_hash("admin123"),
            "role": "admin"
        })

create_admin()

if __name__ == "__main__":
    if __name__ == "__main__":
     app.run()