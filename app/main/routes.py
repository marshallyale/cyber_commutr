from app import db_client
from flask import render_template, abort, current_app, flash
from flask_login import current_user, login_required
from app.models import User, Subscription
from app.main.forms import SubscriptionForm
from app.main import bp


@bp.route("/")
@bp.route("/index")
def index():
    return render_template("index.html", title="Home")


@bp.route("/user/<username>")
@login_required
def user(username):
    user = User(**db_client.db.users.find_one_or_404({"username": username}))
    user_weekly_totals = user.get_user_commute_totals()
    return render_template("user.html", user=user, weekly_totals=user_weekly_totals)


@bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    form = SubscriptionForm()
    if form.validate_on_submit():
        subscription = Subscription()
        subscriptions = subscription.get_subscriptions()
        if subscriptions:
            subscription_url = subscriptions[0].get("callback_url")
            subscription_url.replace("/webhook", "")
        else:
            subscription_url = None
        if current_app.host_url != subscription_url or subscription_url is None:
            if subscription_url != None:
                subscription.delete_subscription()
            response = subscription.create_subscription().json()
            if response.get("id"):
                flash("Created subscription successfully", "success")
            else:
                flash(f"Couldn't create subscription: {response}", "warning")
    return render_template("admin.html", form=form)


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.set_last_seen()
