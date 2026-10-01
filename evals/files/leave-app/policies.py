from models import STATUS_SUBMITTED, STATUS_ESCALATED

HR_THRESHOLD_DAYS = 3


def can_decide(user, leave):
    """Who may approve or reject a request."""
    if user.id == leave.employee_id:
        return False  # nobody decides on their own request
    if leave.status == STATUS_SUBMITTED:
        return user.role == "manager" and user.id == leave.employee.manager_id
    if leave.status == STATUS_ESCALATED:
        return user.role == "hr"
    return False


def needs_hr(leave):
    return leave.days > HR_THRESHOLD_DAYS
