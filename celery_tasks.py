from celery import Celery

celery = Celery("tasks", broker="pyamqp://guest:guest@localhost//")


@celery.task
def process_webhook_data(data):
    print("Processing webhook data:", data)
