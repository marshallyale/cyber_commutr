import os
from celery import Celery

broker = f'amqp://{os.getenv("rabbit_user")}:{os.getenv("rabbit_pw")}@localhost:5672/dev_host'
app = Celery(
    "tasks",
    broker=broker,
)
