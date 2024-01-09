from datetime import datetime, timezone, timedelta
import pytest
from app.models import User, Subscription, Event, load_user, load_user_by_strava_id
from app import create_app, db_client
from config import Config
import os


class TestConfig(Config):
    TESTING = True
    MONGO_URI = "mongodb://root:super_secret@localhost:27017/cyber_bike?authSource=admin"


@pytest.fixture
def get_app(monkeypatch, scope="module"):
    monkeypatch.setenv("FLASK_DEBUG", 1)
    app = create_app(TestConfig)
    app_context = app.app_context()
    app_context.push()
    
    yield app
    app_context.pop()

@pytest.fixture
def alice(get_app):
    alice = load_user(username="alice")
    print(alice)
    yield alice

@pytest.fixture
def admin(get_app):
    admin = load_user(username="admin")
    yield admin


class TestUserCase:
    def test_password_hashing(self, alice):
        alice.set_password("cat")
        assert not alice.check_password("dog")
        assert alice.check_password("cat")

    def test_user_authenticated_w_strava(self, alice):
        assert not alice.check_user_is_authenticated_with_strava()
        alice.scope = True
        assert not alice.check_user_is_authenticated_with_strava()
        alice.scope = False
        alice.strava_id = 42
        assert not alice.check_user_is_authenticated_with_strava()
        alice.scope = True
        assert alice.check_user_is_authenticated_with_strava()

    def test_update_user_in_mongo(self, alice):
        updates = {"updated": True}
