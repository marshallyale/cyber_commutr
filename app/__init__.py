from flask import Flask, flash
from config import Config
from flask_pymongo import PyMongo
from flask_login import LoginManager

# from flask_admin import Admin, UserView
from logging.handlers import RotatingFileHandler
import logging
import base64
import os
from cryptography.fernet import Fernet
from argon2 import PasswordHasher
import ngrok

db_client = PyMongo()
login = LoginManager()
# admin = Admin(name="Commutr", template_mode="bootstrap-3")
login.login_view = "auth.login"
login.login_message = "Please login to view this page"
login.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)
    db_client.init_app(app)
    login.init_app(app)
    from app.errors import bp as errors_bp

    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.strava import bp as strava_bp

    app.register_blueprint(strava_bp, url_prefix="/strava")

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.PH = PasswordHasher()
    app.ENCRYPTOR = Fernet(base64.b64decode(app.config.get("SECRET_KEY")))
    if not app.debug:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        file_handler = RotatingFileHandler(
            "logs/cyber_bike.log", maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("CyberBike startup")
        listener = ngrok.werkzeug_develop()
        app.host_url = listener.url()
        print(f"Application running at {app.host_url}")
        print(
            f"Update the authorization domain at https://www.strava.com/settings/api to \n {app.host_url.replace('https://', '')}"
        )
        updated = input(
            "Have you updated the authorization callback domain at https://www.strava.com/settings/api (Y/N) "
        )
        if updated.lower() != "y":
            print("You have to update the authorization domain for this to work")
            return (
                "You have to update the authorization domain for this to work",
                400,
            )

    if app.debug:
        app.host_url = "127.0.0.1:8080"

    return app


from app import models
