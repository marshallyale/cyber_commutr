import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("KEY")
    RABBIT_USER = os.getenv("RABBIT_USER")
    RABBIT_PW = os.getenv("RABBIT_PW")
    MONGO_URI = os.getenv("MONGO_URI")
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    REQUIRED_SCOPE = os.getenv("STRAVA_SCOPE") or "read,activity:read"
    FLASK_DOMAIN = os.getenv("FLASK_DOMAIN")
