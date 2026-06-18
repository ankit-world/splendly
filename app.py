import sqlite3
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # TODO: replace with env var before production

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        name             = request.form.get("name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        try:
            create_user(name, email, password)
            flash("Account created! Please sign in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return render_template("register.html")

    abort(405)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("All fields are required.")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return render_template("login.html")

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    abort(405)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db_user = get_user_by_id(session["user_id"])
    if db_user is None:
        session.clear()
        return redirect(url_for("login"))

    name = db_user["name"]
    parts = name.split()
    initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
    member_since = db_user["created_at"][:7]  # "YYYY-MM"

    user = {
        "name":         name,
        "email":        db_user["email"],
        "member_since": member_since,
        "initials":     initials,
    }
    stats = {
        "total_spent":       3550.0,
        "transaction_count": 8,
        "top_category":      "Bills",
    }
    transactions = [
        {"date": "Jun 17, 2026", "description": "Restaurant dinner",  "category": "Food",          "amount": 180.0},
        {"date": "Jun 14, 2026", "description": "Miscellaneous",       "category": "Other",         "amount": 60.0},
        {"date": "Jun 12, 2026", "description": "Clothes",             "category": "Shopping",      "amount": 890.0},
        {"date": "Jun 10, 2026", "description": "Movie tickets",       "category": "Entertainment", "amount": 250.0},
        {"date": "Jun 07, 2026", "description": "Pharmacy",            "category": "Health",        "amount": 500.0},
        {"date": "Jun 05, 2026", "description": "Electricity bill",    "category": "Bills",         "amount": 1200.0},
        {"date": "Jun 03, 2026", "description": "Metro pass",          "category": "Transport",     "amount": 150.0},
        {"date": "Jun 01, 2026", "description": "Groceries",           "category": "Food",          "amount": 320.0},
    ]
    categories = [
        {"name": "Bills",         "amount": 1200.0, "pct": 33.8},
        {"name": "Shopping",      "amount": 890.0,  "pct": 25.1},
        {"name": "Health",        "amount": 500.0,  "pct": 14.1},
        {"name": "Food",          "amount": 500.0,  "pct": 14.1},
        {"name": "Entertainment", "amount": 250.0,  "pct": 7.0},
        {"name": "Transport",     "amount": 150.0,  "pct": 4.2},
        {"name": "Other",         "amount": 60.0,   "pct": 1.7},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
