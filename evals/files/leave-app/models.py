from datetime import date

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_ESCALATED = "escalated"

STATUS_LABELS = {
    STATUS_DRAFT: "Draft",
    STATUS_SUBMITTED: "Pending manager approval",
    STATUS_ESCALATED: "Pending HR approval",
    STATUS_APPROVED: "Approved",
    STATUS_REJECTED: "Rejected",
}

ANNUAL_ALLOWANCE_DAYS = 12


class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, nullable=False)
    start = db.Column(db.Date, nullable=False)
    end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String, default=STATUS_DRAFT)
    submitted_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)

    @property
    def days(self):
        return (self.end - self.start).days + 1
