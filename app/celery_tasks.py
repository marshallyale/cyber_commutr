import os
from celery import Celery
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import base64

load_dotenv()
broker = f'amqp://{os.getenv("rabbit_user")}:{os.getenv("rabbit_pw")}@localhost:5672/dev_host'
app = Celery(
    "tasks",
    broker=broker,
)
# print("Who ami i")

ENCRYPTOR = Fernet(base64.b64decode(os.getenv("key")))


@app.task
def process_webhook_data(data):
    parsed_data = parse_webhook_data(data)
    print("Processing webhook data:", data)


def parse_webhook_data(data):
    parsed_data = {}
    if data.get("aspect_type") == "create":
        # Get refresh token, get access token, retrieve activity
        pass
    if data.get("aspect_type") == "update":
        # Push new update to Mongo
        pass
    if data.get("aspect_type") == "delete":
        # Delete from mongo
        pass

    return parsed_data


def _get_access_token(user_id):
    pass


def store_refresh_token(user_id, refresh_token):
    refresh_token_encrypted = string_crypto(refresh_token, encrypt=True)


def string_crypto(data, encrypt=False, decrypt=False):
    if encrypt and decrypt:
        raise ValueError("Please specify either encrypt or decrypt")
    if encrypt:
        return ENCRYPTOR.encrypt(data.encode("utf-8"))
    if decrypt:
        return ENCRYPTOR.decrypt(data).decode("utf-8")
