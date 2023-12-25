from app import app, db
from app.forms import RegistrationForm, LoginForm
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    flash,
    redirect,
    url_for,
)
from helpers import generate_random_string
from app.celery_tasks import process_webhook_data
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from urllib.parse import urlsplit
from app import db
from app.models import User


# Sets server port and logs message on success
@app.route("/")
@app.route("/index")
@login_required
def index():
    user = {"username": "Marshall"}
    return render_template("index.html", title="Home", user=user)


# Creates the endpoint for our webhook
@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        # Webhook event received
        print("Webhook event received!", request.args, request.json)
        data = request.json
        process_webhook_data.delay(data)
        return "EVENT_RECEIVED", 200
    elif request.method == "GET":
        # Your verify token. Should be a random string.
        verify_token = "strava_test"

        # Parses the query params
        print(request)
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        # Checks if a token and mode are in the query string of the request
        if mode and token:
            # Verifies that the mode and token sent are valid
            if mode == "subscribe" and token == verify_token:
                # Responds with the challenge token from the request
                print("WEBHOOK_VERIFIED")
                return jsonify({"hub.challenge": challenge}), 200
            # Responds with '403 Forbidden' if verify tokens do not match
            print("Forbidden!")
            return "Forbidden", 403


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("index")
        return redirect(next_page)
    return render_template("login.html", title="Sign In", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))
