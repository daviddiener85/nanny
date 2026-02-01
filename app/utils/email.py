import os
import smtplib
from email.message import EmailMessage
from typing import List, Optional


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def get_admin_emails() -> List[str]:
    raw = _env("ADMIN_EMAILS", "")
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def send_email(to_email: str, subject: str, body: str) -> None:
    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587") or "587")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    from_email = _env("FROM_EMAIL", user)

    if not host or not from_email:
        raise RuntimeError("SMTP_HOST and FROM_EMAIL (or SMTP_USER) must be set")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        if _env("SMTP_STARTTLS", "1") == "1":
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)
