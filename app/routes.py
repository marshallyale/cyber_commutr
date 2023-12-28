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
from urllib.parse import urlsplit, urlencode
from app.models import User


# Sets server port and logs message on success
@app.route("/")
@app.route("/index")
@login_required
def index():
    current_user.refresh_access_token()
    return render_template("index.html", title="Home")


@app.route("/user/<username>")
@login_required
def user(username):
    user = User(**db.users.find_one_or_404({"username": username}))
    posts = [
        {"author": user, "body": "Test post #1"},
        {"author": user, "body": "Test post #2"},
    ]

    return render_template("user.html", user=user, posts=posts)


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


@app.route("/strava_authorize", methods=["GET"])
def strava_authorize():
    strava_url = "https://www.strava.com/oauth/authorize"
    params = {
        "client_id": app.config["STRAVA_CLIENT_ID"],
        "redirect_uri": f"{app.config.get('FLASK_DOMAIN')}/strava_token",
        "response_type": "code",
        "scope": app.config["REQUIRED_SCOPE"],
        "approval_prompt": "force",
    }
    url = f"{strava_url}?{urlencode(params)}"
    return redirect(f"{strava_url}?{urlencode(params)}")


@app.route("/strava_token", methods=["GET"])
def strava_token():
    if request.args.get("error") == "access_denied":
        print("Error occured when fetching authorization token")
        # TODO: Tell client they have to authorize the app
        return redirect(url_for("login"))
    if request.args.get("scope") != app.config["REQUIRED_SCOPE"]:
        print("Scope doesn't match required scope")
        # TODO: Tell client they have to give the correct scope
        return redirect(url_for("login"))
    code = request.args.get("code")
    if not code:
        # TODO: Handle bad code
        print("No code was retrieved")
        return redirect(url_for("login"))
    current_user.exchange_auth_token_for_refresh_token(code)
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        print("User already authenticated")
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db.users.find_one(
            {"username": form.username.data}
        ) or db.users.find_one({"email": form.username.data})
        if user_data:
            user = User(**user_data)
        else:
            user = None
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            print("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        if user.check_user_is_authenticated_with_strava() is False:
            print("Redirecting to Strava")
            return redirect(url_for("strava_authorize"))
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
        db.users.insert_one(user.__dict__)
        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.set_last_seen()
