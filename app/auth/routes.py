from app.auth.forms import RegistrationForm, LoginForm
from flask import (
    current_app,
    request,
    jsonify,
    render_template,
    flash,
    redirect,
    url_for,
)
from flask_login import current_user, login_user, logout_user, login_required
from urllib.parse import urlsplit, urlencode
from app.models import User
from app import db_client
from app.auth import bp


@bp.route("/strava_authorize", methods=["GET"])
def strava_authorize():
    strava_url = "https://www.strava.com/oauth/authorize"
    params = {
        "client_id": current_app.config["STRAVA_CLIENT_ID"],
        "redirect_uri": f"{current_app.host_url}/auth/strava_token",
        "response_type": "code",
        "scope": current_app.config["REQUIRED_SCOPE"],
        "approval_prompt": "force",
    }
    return redirect(f"{strava_url}?{urlencode(params)}")


@bp.route("/strava_token", methods=["GET"])
def strava_token():
    if request.args.get("error") == "access_denied":
        print("Error occured when fetching authorization token")
        # TODO: Tell client they have to authorize the app
        return redirect(url_for("auth.login"))
    if request.args.get("scope") != current_app.config["REQUIRED_SCOPE"]:
        print("Scope doesn't match required scope")
        # TODO: Tell client they have to give the correct scope
        return redirect(url_for("auth.login"))
    code = request.args.get("code")
    if not code:
        # TODO: Handle bad code
        print("No code was retrieved")
        return redirect(url_for("auth.login"))
    current_user.exchange_auth_token_for_refresh_token(code)
    return redirect(url_for("main.index"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db_client.db.users.find_one(
            {"username": form.username.data}
        ) or db_client.db.users.find_one({"email": form.username.data})
        if user_data:
            user = User(**user_data)
        else:
            user = None
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password", "warning")
            return redirect(url_for("auth.login"))
        login_user(user, remember=form.remember_me.data)
        if user.check_user_is_authenticated_with_strava() is False:
            return redirect(url_for("auth.strava_authorize"))
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("main.index")
        return redirect(next_page)
    return render_template("auth/login.html", title="Sign In", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db_client.db.users.insert_one(user.__dict__)
        flash("Congratulations, you are now a registered user!", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", title="Register", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
