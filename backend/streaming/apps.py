from django.apps import AppConfig


class StreamingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'streaming'



def ready(self):
    try:
        from .celery_schedule import (
            setup_minute_deduction_job,
            setup_earnings_job,
        )
        setup_minute_deduction_job()
        setup_earnings_job()
    except Exception:
        pass
