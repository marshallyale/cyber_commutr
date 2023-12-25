import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("key")
    RABBIT_USER = os.getenv("rabbit_user")
    RABBIT_PW = os.getenv("rabbit_pw")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    MONGO_URI = os.getenv("mongo_uri")
