from flask import current_app, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import Subscription, Event
from app.strava import bp


@bp.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        # Webhook event received
        print("Webhook event received!", request.args, request.json)
        event = Event(**request.json)
        event.create_update_or_delete_event()
        return "EVENT_RECEIVED", 200
    elif request.method == "GET":
        # Your verify token. Should be a random string.
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        # Checks if a token and mode are in the query string of the request
        if mode and token:
            # Verifies that the mode and token sent are valid
            if mode == "subscribe" and token == current_app.verify_token:
                # Responds with the challenge token from the request
                return jsonify({"hub.challenge": challenge}), 200
            # Responds with '403 Forbidden' if verify tokens do not match
            print("Tokens do not match")
            return "Forbidden", 403


@bp.route("/subscription", methods=["GET"])
@login_required
def create_subscription():
    if not current_user.is_admin:
        abort(403)
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
            return "Created subscription successfully", 200
        return "Couldn't create subscription", 200
