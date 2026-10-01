from datetime import datetime
from flask import Flask, request, abort
from models import *
from policies import can_decide, needs_hr
import notifications

app = Flask(__name__)


@app.route("/leave", methods=["POST"])
@login_required
def create_leave():
    leave = LeaveRequest(employee_id=current_user.id, start=request.form["start"], end=request.form["end"])
    if leave.end < leave.start:
        abort(400, "End date cannot be before start date")
    db.session.add(leave)
    db.session.commit()
    return leave


@app.route("/leave/<int:leave_id>/submit", methods=["POST"])
@login_required
def submit_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    if leave.employee_id != current_user.id or leave.status != STATUS_DRAFT:
        abort(403)
    if leave.days > remaining_balance(current_user):
        abort(422, "Insufficient leave balance")
    leave.status = STATUS_SUBMITTED
    leave.submitted_at = datetime.utcnow()
    db.session.commit()
    notifications.send_mail(leave.employee.manager, "New leave request")
    return leave


@app.route("/leave/<int:leave_id>/approve", methods=["POST"])
@login_required
def approve_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    if not can_decide(current_user, leave):
        abort(403)
    if leave.status == STATUS_SUBMITTED and needs_hr(leave):
        leave.status = STATUS_ESCALATED  # long leave: manager approval is not final
        notifications.send_mail(hr_inbox(), "Long leave requires HR approval")
    else:
        leave.status = STATUS_APPROVED
        leave.approved_at = datetime.utcnow()
        deduct_balance(leave.employee, leave.days)
        notifications.send_mail(leave.employee, "Leave approved")
    db.session.commit()
    return leave


@app.route("/leave/<int:leave_id>/reject", methods=["POST"])
@login_required
def reject_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    if not can_decide(current_user, leave):
        abort(403)
    leave.status = STATUS_REJECTED
    db.session.commit()
    notifications.send_mail(leave.employee, "Leave rejected: " + request.form.get("reason", ""))
    return leave


def remaining_balance(user):
    used = sum(l.days for l in user.leaves if l.status == STATUS_APPROVED and l.start.year == datetime.utcnow().year)
    return ANNUAL_ALLOWANCE_DAYS - used
