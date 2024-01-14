from datetime import datetime
import json
import pytest
from dotenv import load_dotenv
import responses
from config import Config
from app import create_app, db_client
from app.models import Subscription, Event, load_user

load_dotenv(".flaskenv")


class TestConfig(Config):
    TESTING = True
    MONGO_URI = (
        "mongodb://root:super_secret@localhost:27017/cyber_bike?authSource=admin"
    )
    FLASK_DEBUG = 1


@pytest.fixture(scope="module")
def get_app():
    # monkeypatch.setenv("FLASK_DEBUG", 1)
    app = create_app(TestConfig)
    app_context = app.app_context()
    app_context.push()

    yield app
    app_context.pop()


@pytest.fixture
def alice(get_app):
    alice = load_user(username="alice")
    yield alice


@pytest.fixture
def admin(get_app):
    admin = load_user(username="admin")
    yield admin


@pytest.fixture
def reset_alice():
    reset_data = {
        "strava_id": 0,
        "password": "$argon2id$v=19$m=65536,t=3,p=4$2hSvCDZcDX9ruaQBBLWaBQ$m1FdRnXBo3exRAfDmvRsbvWfI062f+ZYArRA/3Kumso",
        "refresh_token": "",
        "access_token": "",
        "access_token_exp": 0,
        "scope": False,
    }
    return reset_data


@pytest.fixture
def access_token_mock():
    mock = responses.Response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json={
            "token_type": "Bearer",
            "access_token": "a9b723",
            "expires_at": 1568775134,
            "expires_in": 20566,
            "refresh_token": "b5c569",
        },
        status=200,
    )
    return mock


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

    def test_update_user(self, alice):
        alice_attributes_pre = alice.__dict__
        updates = {"access_token": "ABCDEF"}
        alice.update(updates)
        assert alice.access_token == "ABCDEF"
        alice.access_token = ""
        assert alice.__dict__ == alice_attributes_pre

    def test_update_user_in_mongo(self, alice):
        updates = {"access_token": "ABCDEF"}
        update = alice.update_user_in_mongo(updates)
        assert update is True
        assert alice.access_token == "ABCDEF"
        alice_user_from_mongo = db_client.db.users.find_one(
            {"username": alice.username}
        )
        assert alice_user_from_mongo.get("access_token") == "ABCDEF"
        updates = {"access_token": ""}
        update2 = alice.update_user_in_mongo(updates)
        assert update2 is True

    @responses.activate
    def test_check_access_token(self, alice, reset_alice, access_token_mock):
        current_datetime = datetime.now()
        current_timestamp = int(current_datetime.timestamp())
        alice.access_token_exp = current_timestamp - 90
        alice.refresh_token = alice.string_crypto("test", encrypt=True)
        responses.add(access_token_mock)
        alice.check_access_token()
        assert alice.access_token == "a9b723"
        assert alice.access_token_exp == 1568775134
        alice_refresh_token = alice.string_crypto(alice.refresh_token, decrypt=True)
        assert alice_refresh_token == "b5c569"
        alice.update_user_in_mongo(reset_alice)

    @responses.activate
    def test_fail_check_access_token(self, alice):
        current_datetime = datetime.now()
        current_timestamp = int(current_datetime.timestamp())
        alice.access_token_exp = current_timestamp - 90
        alice.refresh_token = alice.string_crypto("test", encrypt=True)
        responses.add(
            method="POST",
            url="https://www.strava.com/oauth/token",
            json={"error": "unauthorized"},
            status=403,
        )
        assert alice.check_access_token() is False

    @responses.activate
    def test_exchange_auth_token_for_refresh_token(self, alice, reset_alice):
        responses.add(
            method="POST",
            url="https://www.strava.com/oauth/token",
            json={
                "token_type": "Bearer",
                "expires_at": 1568775134,
                "expires_in": 21600,
                "refresh_token": "e5n567567",
                "access_token": "a4b945687g",
                "athlete": {
                    "username": "alice_is_a_gee123456",
                    "id": 123,
                    "badge_type_id": 1,
                    "bio": None,
                    "city": "Los Angeles",
                },
            },
            status=200,
        )
        alice.exchange_auth_token_for_refresh_token("abc123")
        assert alice.access_token == "a4b945687g"
        assert alice.access_token_exp == 1568775134
        alice_refresh_token = alice.string_crypto(alice.refresh_token, decrypt=True)
        assert alice_refresh_token == "e5n567567"
        alice.update_user_in_mongo(reset_alice)
        db_client.db.strava_athletes.delete_one({"username": "alice_is_a_gee123456"})

    @responses.activate
    def test_fail_exchange_auth_token_for_refresh_token(self, alice):
        responses.add(
            method="POST",
            url="https://www.strava.com/oauth/token",
            json={"error": "Unauthorized"},
            status=401,
        )
        assert alice.exchange_auth_token_for_refresh_token("abc123") is None

    def test_aggregate_activities(self, admin):
        totals = admin.get_user_commute_totals()
        print(totals)
        
        # assert total[0].get("total") == 34295.3

    def test_fetch_previous_events(self, admin):
        # delete_all = db_client.db.activities.delete_many({})
        admin.fetch_previous_events(retries=1, activities_to_fetch=1000)
        current_activities_count = db_client.db.activities.count_documents({})
        # assert current_activities_count == 50


@pytest.fixture
def sub(get_app):
    subscription = Subscription()
    yield subscription


class TestSubscription:
    @responses.activate
    def test_get_subscriptions(self, sub):
        responses.add(
            method="GET",
            url="https://www.strava.com/api/v3/push_subscriptions",
            json=[
                {
                    "id": 253727,
                    "resource_state": 2,
                    "application_id": 118435,
                    "callback_url": "https://3fce-172-222-128-127.ngrok-free.app/strava/webhook",
                    "created_at": "2024-01-08T01:10:06+00:00",
                    "updated_at": "2024-01-08T01:10:06+00:00",
                }
            ],
            status=200,
        )
        response = sub.get_subscriptions()
        assert response[0]["id"] == 253727

    @responses.activate
    def test_failed_get_subscriptions(self, sub):
        responses.add(
            method="GET",
            url="https://www.strava.com/api/v3/push_subscriptions",
            json=[{"error": "unauthorized"}],
            status=401,
        )
        response = sub.get_subscriptions()
        assert response is None


@pytest.fixture
def activity():
    """Loads an example activity"""
    file_path = "tests/example_activity.json"
    try:
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
            yield data
    except FileNotFoundError:
        print(f"File not found {file_path}")
    except json.JSONDecodeError:
        print(f"Invalid JSON format in file: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


@pytest.fixture
def create_event():
    """An example create event"""
    event = {
        "aspect_type": "create",
        "event_time": 1703865498,
        "object_id": 10,
        "object_type": "activity",
        "owner_id": 8587070,
        "subscription_id": 253500,
        "updates": {},
    }
    return Event(**event)


@pytest.fixture
def update_event():
    """An example update event"""
    event = {
        "aspect_type": "update",
        "event_time": 1703865569,
        "object_id": 10,
        "object_type": "activity",
        "owner_id": 8587070,
        "subscription_id": 253500,
        "updates": {"title": "Test iz new test"},
    }
    return Event(**event)


@pytest.fixture
def delete_event():
    """An example update event"""
    event = {
        "aspect_type": "delete",
        "event_time": 1703865603,
        "object_id": 10,
        "object_type": "activity",
        "owner_id": 8587070,
        "subscription_id": 253500,
        "updates": {},
    }
    return Event(**event)


class TestEvents:
    @responses.activate
    def test_create_event(self, admin, activity, access_token_mock, create_event):
        responses.add(access_token_mock)
        responses.add(
            method="GET",
            url=f"https://www.strava.com/api/v3/activities/{create_event.object_id}",
            json=activity,
            status=200,
        )
        create_event.create_update_or_delete_event()
        mongo_result = db_client.db.activities.find_one({"id": create_event.object_id})

        assert mongo_result.get("id") == 10
        assert mongo_result.get("name") == "Barley Flats and Dissapointment"

    def test_failed_create_event(self, admin, create_event, access_token_mock):
        responses.add(access_token_mock)
        responses.add(
            method="GET",
            url=f"https://www.strava.com/api/v3/activities/{create_event.object_id}",
            status=404,
        )
        success = create_event.create_update_or_delete_event()
        assert success is False

    @responses.activate
    def test_update_event(self, admin, activity, access_token_mock, update_event):
        """When we update, we just fetch the activity again because multiple things could have changed

        Args:
            admin (User): User needed for access token
            activity (json): Activity json
            access_token_mock (responses.Response): Mock request to get access token
            update_event (Event): Update event json
        """
        responses.add(access_token_mock)
        responses.add(
            method="GET",
            url=f"https://www.strava.com/api/v3/activities/{update_event.object_id}",
            json=activity,
            status=200,
        )
        update_event.create_update_or_delete_event()
        mongo_result = db_client.db.activities.find_one({"id": update_event.object_id})
        assert mongo_result.get("id") == 10
        assert mongo_result.get("name") == "Barley Flats and Dissapointment"
        db_client.db.activities.delete_one({"id": update_event.object_id})

    def test_failed_update_event(self, admin, update_event, access_token_mock):
        responses.add(access_token_mock)
        responses.add(
            method="GET",
            url=f"https://www.strava.com/api/v3/activities/{update_event.object_id}",
            status=404,
        )
        success = update_event.create_update_or_delete_event()
        assert success is False
