import os, smtplib
from email.message import EmailMessage
from pathlib import Path


def send(to, subject, body, cv_path: Path, sender_name=""):
    m = EmailMessage()
    m["From"] = f'{sender_name} <{os.environ["SMTP_EMAIL"]}>' if sender_name else os.environ["SMTP_EMAIL"]
    m["To"] = to
    m["Subject"] = subject
    m.set_content(body)
    sub = {".pdf": "pdf", ".docx": "vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(
        cv_path.suffix.lower(), "octet-stream")
    m.add_attachment(cv_path.read_bytes(), maintype="application", subtype=sub, filename=cv_path.name)
    with smtplib.SMTP(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_EMAIL"], os.environ["SMTP_PASSWORD"])
        s.send_message(m)
