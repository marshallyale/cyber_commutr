from dataclasses import dataclass, field, InitVar
from typing import Optional
import requests
from app import app, db, login
from datetime import datetime
from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
from flask_login import UserMixin
from cryptography.fernet import Fernet
import base64

PH = PasswordHasher()
ENCRYPTOR = Fernet(base64.b64decode(app.config.get("SECRET_KEY")))


@dataclass
class User(UserMixin):
    username: str
    email: str
    strava_id: int = field(default=0)
    password: str = field(default="")
    refresh_token: str = field(default="")
    access_token: str = field(default="")
    access_token_exp: str = field(default="")
    scope: bool = field(default=False)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_admin: bool = field(default=False)
    # Internal mongo id
    _id: InitVar[Optional[int]] = None

    def set_password(self, password):
        self.password = PH.hash(password)

    def check_password(self, password):
        try:
            PH.verify(self.password, password)
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
        result = db.users.update_one(
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
            return ENCRYPTOR.encrypt(data.encode("utf-8"))
        if decrypt:
            return ENCRYPTOR.decrypt(data).decode("utf-8")

    def exchange_auth_token_for_refresh_token(self, code):
        strava_request = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": app.config["STRAVA_CLIENT_ID"],
                "client_secret": app.config["STRAVA_CLIENT_SECRET"],
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
        db.strava_athletes.update_one(
            {"id": athlete_id}, {"$set": athlete_info}, upsert=True
        )

    def refresh_access_token(self):
        strava_request = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": app.config["STRAVA_CLIENT_ID"],
                "client_secret": app.config["STRAVA_CLIENT_SECRET"],
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

    def fetch_user_strava_profile(self):
        profile = db.strava_athletes.find_one({"id": self.strava_id})
        return profile

    def get_user_strava_url(self):
        profile_data = self.fetch_user_strava_profile()
        url = profile_data.get("profile")
        return url


@login.user_loader
def load_user(username):
    user = db.users.find_one({"username": username})
    if not user:
        return None
    return User(**user)
