from flask import Flask, render_template, request, redirect, session, flash
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ================== MONGODB ==================

MONGO_URI = "mongodb+srv://amir:amir7890@cluster0.mb7ruie.mongodb.net/change_management_db?retryWrites=true&w=majority"

client = MongoClient(MONGO_URI)

db = client["change_management_db"]
requests_collection = db["change_requests"]
users_collection = db["users"]

print("MongoDB Connected")

# ================== EMAIL CONFIG ==================

ADMIN_EMAIL = "amirkhan91522@gmail.com"
EMAIL_SENDER = "amirkhan91522@gmail.com"
EMAIL_PASSWORD = "hvwdtkowejgjhpww"

# ================== EMAIL FUNCTION ==================

def send_email(to_email, subject, body):
    try:

        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()

        print("Email sent to:", to_email)

    except Exception as e:
        print("Email Error:", e)

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

    return render_template(
        "index.html",
        requests=requests_data,
        role=session["role"],
        username=session["username"],
        admin_email=ADMIN_EMAIL
    )

# ================== REGISTER ==================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

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

        flash("Registration Successful!", "success")
        return redirect("/login")

    return render_template("register.html")

# ================== LOGIN ==================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):

            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect("/")

        flash("Invalid Username or Password!", "danger")

    return render_template("login.html")

# ================== ADD REQUEST ==================

@app.route("/add", methods=["POST"])
def add_request():

    if "username" not in session:
        return redirect("/login")

    user = users_collection.find_one({"username": session["username"]})

    user_email = user.get("email", "")

    data = {
        "category": request.form.get("category"),
        "title": request.form.get("title"),
        "description": request.form.get("description"),
        "risk": request.form.get("risk"),
        "status": "Pending",
        "created_by": session["username"],
        "created_by_email": user_email,
        "date": datetime.now()
    }

    requests_collection.insert_one(data)

    subject = "New Change Request Submitted"

    body = f"""
    <h3>New Change Request</h3>
    <p><b>Title:</b> {data['title']}</p>
    <p><b>Risk:</b> {data['risk']}</p>
    <p><b>User:</b> {data['created_by']}</p>
    """

    send_email(ADMIN_EMAIL, subject, body)

    flash("Request Submitted Successfully!", "success")

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
        <p><b>Status:</b> {status}</p>
        """

        send_email(user_email, subject, body)

    flash("Status Updated!", "success")

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
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
