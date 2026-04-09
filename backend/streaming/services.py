from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from .models import ViewerSessionEvent


RATE_PER_VIEWER_PER_MINUTE = Decimal("2.0")


def calculate_session_earnings(session):
    """
    Earnings = sum of all real watch time from ViewerSessionEvent logs.
    This is source-of-truth, audit-safe, and fraud-proof.
    """

    if not session.actual_end:
        raise ValueError("Session must be ended before calculating earnings")

    total_watch_seconds = 0

    events = ViewerSessionEvent.objects.filter(
        session=session
    ).only("joined_at", "left_at")

    for event in events:
        end_time = event.left_at or session.actual_end

        # Safety: ignore broken data
        if end_time <= event.joined_at:
            continue

        duration = (end_time - event.joined_at).total_seconds()
        total_watch_seconds += duration

    # Convert to minutes
    total_watch_minutes = Decimal(total_watch_seconds) / Decimal(60)

    earnings = total_watch_minutes * RATE_PER_VIEWER_PER_MINUTE

    # Optional: round to 2 decimals like money
    earnings = earnings.quantize(Decimal("0.01"))

    session.total_earned = earnings
    session.save(update_fields=["total_earned"])

    return earnings
