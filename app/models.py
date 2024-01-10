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
    access_token_exp: int = 0
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
        # First update the user in our model
        self.update(update_data)
        result = db_client.db.users.update_one(
            {"username": self.username},  # Use the user's _id for identification
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

    def update(self, updates):
        for key, value in updates.items():
            setattr(self, key, value)

    def string_crypto(self, data, encrypt=False, decrypt=False):
        if encrypt and decrypt:
            raise ValueError("Please specify either encrypt or decrypt")
        if encrypt:
            return current_app.ENCRYPTOR.encrypt(data.encode("utf-8"))
        if decrypt:
            return current_app.ENCRYPTOR.decrypt(data).decode("utf-8")

    def exchange_auth_token_for_refresh_token(self, code):
        url = "https://www.strava.com/oauth/token"
        data = {
            "client_id": current_app.config["STRAVA_CLIENT_ID"],
            "client_secret": current_app.config["STRAVA_CLIENT_SECRET"],
            "code": code,
            "grant_type": "authorization_code",
        }
        response = self._request(url, method="POST", payload=data)
        # If lookup fails, return None
        if not response:
            return None
        athlete_info = response.get("athlete")
        self.strava_id = athlete_info.get("id")
        user_data = {
            "access_token": response.get("access_token"),
            "access_token_exp": response.get("expires_at"),
            "strava_id": self.strava_id,
            "refresh_token": self.string_crypto(
                response.get("refresh_token"),
                encrypt=True,
            ),
            "scope": True,
        }
        self.update_user_in_mongo(user_data)
        db_client.db.strava_athletes.update_one(
            {"id": self.strava_id}, {"$set": athlete_info}, upsert=True
        )
        # TODO: Handle a failed code lookup in app
        return True

    def refresh_access_token(self):
        url = "https://www.strava.com/oauth/token"
        data = {
            "client_id": current_app.config["STRAVA_CLIENT_ID"],
            "client_secret": current_app.config["STRAVA_CLIENT_SECRET"],
            "refresh_token": self.string_crypto(self.refresh_token, decrypt=True),
            "grant_type": "refresh_token",
        }
        response = self._request(url, method="POST", payload=data)
        if not response:
            return False
        access_data = {
            "access_token": response.get("access_token"),
            "access_token_exp": response.get("expires_at"),
            "refresh_token": self.string_crypto(
                response.get("refresh_token"), encrypt=True
            ),
        }
        success = self.update_user_in_mongo(access_data)
        if not success:
            return False
        return True

    def check_access_token(self):
        current_datetime = datetime.now()
        current_timestamp = int(current_datetime.timestamp())
        # If the timestamp is within a minute of
        if current_timestamp - 60 >= self.access_token_exp:
            success = self.refresh_access_token()
            if success:
                return True
            # TODO: Add error handling on the frontend if it fails
            return False

    def fetch_user_strava_profile(self):
        profile = db_client.db.strava_athletes.find_one({"id": self.strava_id})
        return profile

    def get_user_strava_url(self):
        profile_data = self.fetch_user_strava_profile()
        url = profile_data.get("profile")
        return url

    def _request(self, url, method="GET", payload=None, params=None, headers=None):
        try:
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
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve access code. {e}")
            return None


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
        try:
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
        except requests.exceptions.RequestException as e:
            print(f"Failed to send request. {e}")
            return None

    def get_subscriptions(self):
        params = {
            "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
            "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
        }
        response = self.send_request(self.strava_url, method="GET", params=params)
        if not response:
            return None
        return response.json()

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
        random_string = "".join(secrets.choice(characters) for _ in range(length))

        return random_string


@dataclass
class Event:
    """
    Class to handle events received from Strava. These are always update from the webhook api.
    Create: Should always be an activity. Just fetch the activity and insert to mongo
    Update: Only updates for change in title, type, privacy, or deauthorization
    Delete:
    """

    object_type: str  # activity or athlete
    object_id: int  # For activity, activity id. For athlete, athlete id
    aspect_type: str  # Create, update, or delete
    updates: dict  # Title or type, for deauth, authorized = false
    owner_id: int  # Athlete id
    subscription_id: int  # Subscription id
    event_time: int  # Time event occured
    collection: str = "activities"

    def create_update_or_delete_event(self):
        if self.object_type == "athlete":
            self.collection = "strava_athletes"
        if self.aspect_type == "create":
            # This should always be an activity
            object_info = self.fetch_object()
            if not object_info:
                return False
            self.upsert_to_mongo("id", object_info)
            return True
        if self.aspect_type == "update":
            update_success = self.update_activity_or_athlete()
            if not update_success:
                return False
            return True
        if self.aspect_type == "delete":
            success = self.delete_activity_or_athlete()
            if not success:
                return False
            return True

    def update_activity_or_athlete(self):
        if self.object_type == "athlete":
            if self.updates.get("authorized") == "false":
                db_client.db.users.update_one(
                    {"strava_id": self.owner_id}, {"scope": False}
                )
                return True
            id_key = "strava_id"
        else:
            id_key = "id"
        object_info = self.fetch_object()
        if not object_info:
            return False
        upsert_success = self.upsert_to_mongo(id_key, object_info)
        if not upsert_success:
            return False
        return True

    def upsert_to_mongo(self, object_id, data):
        collection = db_client.db.get_collection(self.collection)
        result = collection.update_one(
            {object_id: self.object_id}, {"$set": data}, upsert=True
        )
        if result.matched_count == 1:
            return True
        return False

    def delete_activity_or_athlete(self):
        collection = db_client.db.get_collection(self.collection)
        if self.object_type == "athlete":
            # Doubt this ever gets called
            id_key = "owner_id"
        else:
            id_key = "id"
        result = collection.delete_one({id_key: self.object_id})
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
            data = self._request(url, method="GET", params=params, headers=headers)
            if data:
                return data
        return None

    def _request(self, url, method="GET", payload=None, params=None, headers=None):
        try:
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
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve object id. {e}")
            return None
