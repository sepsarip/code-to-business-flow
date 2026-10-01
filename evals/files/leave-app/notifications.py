import smtplib


def send_mail(to, subject):
    with smtplib.SMTP("smtp.internal") as s:
        s.sendmail("hr@example.test", to.email, subject)
