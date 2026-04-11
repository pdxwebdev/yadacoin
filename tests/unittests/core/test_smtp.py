"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import smtplib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.smtp import Email

from ..test_setup import AsyncTestCase


class TestEmail(AsyncTestCase):
    async def test_init(self):
        email = Email()
        self.assertIsNotNone(email)

    async def test_send_mail_success(self):
        email = Email()
        mock_config = MagicMock()
        mock_config.email.smtp_server = "smtp.example.com"
        mock_config.email.smtp_port = 587
        mock_config.email.username = "user@example.com"
        mock_config.email.password = "password"
        email.config = mock_config

        with patch("smtplib.SMTP") as mock_smtp:
            mock_conn = MagicMock()
            mock_smtp.return_value = mock_conn
            await email.send_mail(
                "from@example.com",
                "to@example.com",
                "Test Subject",
                "Test Body",
            )
            mock_smtp.assert_called_once_with(host="smtp.example.com", port=587)
            mock_conn.starttls.assert_called_once()
            mock_conn.login.assert_called_once_with("user@example.com", "password")
            mock_conn.send_message.assert_called_once()
            mock_conn.quit.assert_called_once()

    async def test_send_mail_logs_exception_on_failure(self):
        email = Email()
        mock_config = MagicMock()
        mock_config.email.smtp_server = "smtp.example.com"
        mock_config.email.smtp_port = 587
        mock_config.email.username = "user@example.com"
        mock_config.email.password = "password"
        mock_config.mongo.async_site_db.failed_emails.insert_one = AsyncMock()
        email.config = mock_config

        with patch("smtplib.SMTP") as mock_smtp:
            mock_conn = MagicMock()
            mock_conn.login.side_effect = smtplib.SMTPAuthenticationError(
                535, "Auth failed"
            )
            mock_smtp.return_value = mock_conn

            await email.send_mail(
                "from@example.com",
                "to@example.com",
                "Test Subject",
                "Test Body",
            )
            mock_config.mongo.async_site_db.failed_emails.insert_one.assert_called_once()


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
