import os
import sqlite3
from datetime import date
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id
from database.helpers import parse_date, months_ago
from database.queries import (
    get_user_by_id as get_user_profile,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret")

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

    user_id = session["user_id"]
    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    date_from = parse_date(request.args.get("date_from"))
    date_to   = parse_date(request.args.get("date_to"))

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.")
        date_from = date_to = None

    date_from_str = date_from.isoformat() if date_from else None
    date_to_str   = date_to.isoformat()   if date_to   else None

    today          = date.today()
    first_of_month = today.replace(day=1)
    presets = [
        {"label": "This Month",    "date_from": first_of_month.isoformat(),         "date_to": today.isoformat()},
        {"label": "Last 3 Months", "date_from": months_ago(today, 3).isoformat(),   "date_to": today.isoformat()},
        {"label": "Last 6 Months", "date_from": months_ago(today, 6).isoformat(),   "date_to": today.isoformat()},
        {"label": "All Time",      "date_from": None,                               "date_to": None},
    ]

    user         = get_user_profile(user_id)
    stats        = get_summary_stats(user_id, date_from=date_from_str, date_to=date_to_str)
    transactions = get_recent_transactions(user_id, date_from=date_from_str, date_to=date_to_str)
    categories   = get_category_breakdown(user_id, date_from=date_from_str, date_to=date_to_str)
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_from=date_from_str or "",
        date_to=date_to_str or "",
        presets=presets,
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
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5001)
