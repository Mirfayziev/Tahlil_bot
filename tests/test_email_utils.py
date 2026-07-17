"""Email yuborish yordamchisi testlari (haqiqiy SMTP serversiz)."""
from unittest.mock import patch, MagicMock

from app.email_utils import send_email


def test_send_email_no_mail_server_configured_returns_false(app):
    app.config["MAIL_SERVER"] = ""
    with app.app_context():
        result = send_email(["someone@example.com"], "Sarlavha", "Matn")
    assert result is False


def test_send_email_no_recipients_returns_false(app):
    app.config["MAIL_SERVER"] = "smtp.example.com"
    with app.app_context():
        result = send_email([], "Sarlavha", "Matn")
    assert result is False


def test_send_email_success_with_mocked_smtp(app):
    app.config["MAIL_SERVER"] = "smtp.example.com"
    app.config["MAIL_USERNAME"] = "user@example.com"
    app.config["MAIL_PASSWORD"] = "secret"

    fake_smtp = MagicMock()
    with app.app_context():
        with patch("smtplib.SMTP", return_value=fake_smtp) as smtp_cls:
            fake_smtp.__enter__.return_value = fake_smtp
            result = send_email(["to@example.com"], "Sarlavha", "Matn")

    assert result is True
    fake_smtp.sendmail.assert_called_once()


def test_send_email_handles_smtp_exception(app):
    app.config["MAIL_SERVER"] = "smtp.example.com"
    with app.app_context():
        with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
            result = send_email(["to@example.com"], "Sarlavha", "Matn")
    assert result is False
