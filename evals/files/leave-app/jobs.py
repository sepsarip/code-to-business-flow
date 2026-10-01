from datetime import datetime, timedelta
from celery import shared_task
from models import *
import notifications

ESCALATE_AFTER_DAYS = 5


@shared_task
def escalate_stale_requests():
    """Runs daily: requests the manager has not touched go to HR."""
    cutoff = datetime.utcnow() - timedelta(days=ESCALATE_AFTER_DAYS)
    for leave in LeaveRequest.query.filter(LeaveRequest.status == STATUS_SUBMITTED, LeaveRequest.submitted_at < cutoff):
        leave.status = STATUS_ESCALATED
        notifications.send_mail(hr_inbox(), "Leave request unhandled by manager")
    db.session.commit()
