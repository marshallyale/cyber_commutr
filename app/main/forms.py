from flask_wtf import FlaskForm
from wtforms import SubmitField


class SubscriptionForm(FlaskForm):
    subscribe = SubmitField("Create Subscription")
