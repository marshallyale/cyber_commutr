from dataclasses import dataclass, field, InitVar
from typing import Optional
import requests
from app import db_client, login
from flask import current_app
from datetime import datetime
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
from flask_login import UserMixin
import secrets
import string


@dataclass
class User(UserMixin):
    username: str
    email: str
    strava_id: int = 0
    password: str = ""
    refresh_token: str = ""
    access_token: str = ""
    access_token_exp: str = ""
    scope: bool = False
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    last_seen: datetime = datetime.utcnow()
    is_admin: bool = False
    # Internal mongo id
    _id: InitVar[Optional[int]] = None

    def set_password(self, password):
        self.password = current_app.PH.hash(password)

    def check_password(self, password):
        try:
            current_app.PH.verify(self.password, password)
            return True
        except VerifyMismatchError:
            # Passwords don't match
            return False
        except VerificationError:
            print("Issue with argon2 password hash verification")
            return False
        except InvalidHashError:
            print("Hash is not valid")
            return False

    def check_user_is_authenticated_with_strava(self):
        if self.scope is False or self.strava_id == 0:
            return False
        return True

    def update_user_in_mongo(self, update_data):
        result = db_client.db.users.update_one(
            {
                "username": self.username
            },  # Use the user's _id for identification
            {"$set": update_data},
        )

        if result.matched_count == 1:
            return True
        return False

    def set_last_seen(self):
        login_data = {"last_seen": datetime.utcnow()}
        update = self.update_user_in_mongo(login_data)
        if update is False:
            # TODO: Print failed login
            print("Failed to set last seen")

    def get_id(self):
        return self.username

    def string_crypto(self, data, encrypt=False, decrypt=False):
        if encrypt and decrypt:
            raise ValueError("Please specify either encrypt or decrypt")
        if encrypt:
            return current_app.ENCRYPTOR.encrypt(data.encode("utf-8"))
        if decrypt:
            return current_app.ENCRYPTOR.decrypt(data).decode("utf-8")

    def exchange_auth_token_for_refresh_token(self, code):
        strava_request = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": current_app.config["STRAVA_CLIENT_ID"],
                "client_secret": current_app.config["STRAVA_CLIENT_SECRET"],
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        user_info = strava_request.json()
        athlete_info = user_info.get("athlete")
        athlete_id = athlete_info.get("id")
        user_info["strava_id"] = athlete_id
        user_info["access_token_exp"] = user_info.pop("expires_at")
        user_info["refresh_token"] = self.string_crypto(
            user_info.get("refresh_token"), encrypt=True
        )
        # Set scope equal to true, since they gave correct scope
        user_info["scope"] = True
        # Don't need the following fields
        del user_info["athlete"]
        del user_info["token_type"]
        del user_info["expires_in"]
        self.update_user_in_mongo(user_info)
        db_client.db.strava_athletes.update_one(
            {"id": athlete_id}, {"$set": athlete_info}, upsert=True
        )

    def refresh_access_token(self):
        strava_request = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": current_app.config["STRAVA_CLIENT_ID"],
                "client_secret": current_app.config["STRAVA_CLIENT_SECRET"],
                "refresh_token": self.string_crypto(
                    self.refresh_token, decrypt=True
                ),
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        access_data = strava_request.json()
        access_data["access_token_exp"] = access_data.pop("expires_at")
        access_data["refresh_token"] = self.string_crypto(
            access_data.get("refresh_token"), encrypt=True
        )
        del access_data["token_type"]
        del access_data["expires_in"]
        success = self.update_user_in_mongo(access_data)
        if success:
            return True
        return False

    def check_access_token(self):
        current_datetime = datetime.now()
        current_timestamp = int(current_datetime.timestamp())
        # If the timestamp is within a minute of
        if current_timestamp - 60 >= self.access_token_exp:
            success = self.refresh_access_token()
            if success:
                print("Successfully refreshed access token")
            else:
                print("Failed to refresh access token")

    def fetch_user_strava_profile(self):
        profile = db_client.db.strava_athletes.find_one({"id": self.strava_id})
        return profile

    def get_user_strava_url(self):
        profile_data = self.fetch_user_strava_profile()
        url = profile_data.get("profile")
        return url


@login.user_loader
def load_user(username=None):
    user = db_client.db.users.find_one({"username": username})
    if not user:
        return None
    return User(**user)


def load_user_by_strava_id(strava_id):
    user = db_client.db.users.find_one({"strava_id": strava_id})
    if not user:
        return None
    return User(**user)


class Subscription:
    def __init__(self):
        self.strava_url = "https://www.strava.com/api/v3/push_subscriptions"
        self.webhook_url = (f"{current_app.host_url}/strava/webhook",)

    def send_request(
        self,
        url,
        method="GET",
        payload=None,
        params=None,
        headers=None,
        create=False,
    ):
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            data=payload,
            timeout=10,
        )
        if create:
            return response
        response.raise_for_status()
        return response

    def get_subscriptions(self):
        params = {
            "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
            "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
        }
        return self.send_request(
            self.strava_url, method="GET", params=params
        ).json()

    def create_subscription(self):
        current_app.verify_token = self._generate_random_string()
        payload = {
            "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
            "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
            "callback_url": self.webhook_url,
            "verify_token": current_app.verify_token,
        }
        return self.send_request(
            self.strava_url, method="POST", payload=payload, create=True
        )

    def delete_subscription(self):
        current_subscription = self.get_subscriptions()
        current_subscription_id = current_subscription[0].get("id")
        params = {
            "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
            "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
        }
        response = self.send_request(
            f"{self.strava_url}/{current_subscription_id}",
            method="DELETE",
            params=params,
        )
        if response.status_code == 204:
            return True
        return False

    def _generate_random_string(self, length=10):
        characters = string.ascii_letters + string.digits
        random_string = "".join(
            secrets.choice(characters) for _ in range(length)
        )

        return random_string


@dataclass
class Event:
    object_type: str  # activity or athlete
    object_id: int  # For activity, activity id. For athlete, athlete id
    aspect_type: str  # Create, update, or delete
    updates: dict  # Title or type, for deauth, authorized = false
    owner_id: int  # Athlete id
    subscription_id: int  # Subscription id
    event_time: int  # Time event occured

    def get_collection_for_event(self):
        if self.object_type == "athlete":
            return db_client.db.get_collection("strava_athletes")
        return db_client.db.get_collection("activities")

    def create_update_or_delete_event(self):
        collection = self.get_collection_for_event()
        if self.aspect_type == "create":
            # This should always be an activity
            object_info = self.fetch_object()
            collection.insert_one(object_info)
            return
        if self.aspect_type == "update":
            self.update_activity_or_athelete(collection)
            return
        if self.aspect_type == "delete":
            self.delete_activity_or_athlete(collection)
            return

    def update_activity_or_athelete(self, collection):
        if self.object_type == "athlete":
            if self.updates.get("authorized") == "false":
                db_client.db.users.update_one(
                    {"strava_id": self.owner_id}, {"scope": False}
                )
                return True
            id_key = "strava_id"
        else:
            id_key = "id"
        result = collection.update_one(
            {id_key: self.object_id}, {"$set": self.updates}
        )
        if result.matched_count == 1:
            return True
        return False

    def delete_activity_or_athlete(self, collection):
        if self.object_type == "athlete":
            # Doubt this ever gets called
            id_key = "id"
        else:
            id_key = "athlete.id"
        result = collection.delete_one({id_key: self.owner_id})

        if result.deleted_count == 1:
            return True
        return False

    def fetch_object(self):
        user = load_user_by_strava_id(self.owner_id)
        user.check_access_token()
        headers = {"Authorization": f"Bearer {user.access_token}"}
        if self.object_type == "activity":
            url = f"https://www.strava.com/api/v3/activities/{self.object_id}"
            params = {"include_all_efforts": False}
            data = self.send_request(
                url, method="GET", params=params, headers=headers
            )
            return data
        return None

    def send_request(
        self,
        url,
        method="GET",
        payload=None,
        params=None,
        headers=None,
    ):
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            data=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
