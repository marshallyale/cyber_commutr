from app import db_client
from flask import render_template, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from app.models import User
from app.main import bp


@bp.route("/")
@bp.route("/index")
@login_required
def index():
    return render_template("index.html", title="Home")


@bp.route("/user/<username>")
@login_required
def user(username):
    user = User(**db_client.db.users.find_one_or_404({"username": username}))
    posts = [
        {"author": user, "body": "Test post #1"},
        {"author": user, "body": "Test post #2"},
    ]

    return render_template("user.html", user=user, posts=posts)


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.set_last_seen()
