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
