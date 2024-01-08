from datetime import datetime, timezone, timedelta
import pytest
from app.models import User, Subscription, Event
from app import create_app, db_client
from config import Config
import os


class TestConfig(Config):
    TESTING = True
    MONGO_URI = "mongodb://root:super_secret@localhost:27017/?authSource=admin"


@pytest.fixture
def get_app(monkeypatch, scope="module"):
    monkeypatch.setenv("FLASK_DEBUG", 1)
    app = create_app(TestConfig)
    app_context = app.app_context()
    app_context.push()
    yield app
    app_context.pop()


class TestUserCase:
    def test_password_hashing(self, get_app):
        u = User(username="susan", email="susan@example.com")
        u.set_password("cat")
        assert not u.check_password("dog")
        assert u.check_password("cat")

    def test_user_authenticated_w_strava(self):
        u = User(username="alice", email="alice@example.com")
        assert not u.check_user_is_authenticated_with_strava()
        u.scope = True
        assert not u.check_user_is_authenticated_with_strava()
        u.scope = False
        u.strava_id = 42
        assert not u.check_user_is_authenticated_with_strava()
        u.scope = True
        assert u.check_user_is_authenticated_with_strava()
