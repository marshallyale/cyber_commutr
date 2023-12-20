from flask import Flask, request, jsonify
from helpers import generate_random_string
from celery_tasks import process_webhook_data

app = Flask(__name__)


# Sets server port and logs message on success
@app.route("/")
def index():
    return "Webhook is listening"


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


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, port=8080)
