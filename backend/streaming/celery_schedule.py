from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "auto-end-dead-streams-every-minute": {
        "task": "streaming.tasks.auto_end_dead_streams",
        "schedule": crontab(minute="*"),
    },
}
