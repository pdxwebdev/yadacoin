import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from yadacoin.core.config import get_config
from traceback import format_exc


class Email:
    def __init__(self):
        self.config = get_config()

    async def send_mail(self, mail_from, mail_to, mail_subject, mail_body):
        mimemsg = MIMEMultipart()
        mimemsg["From"] = mail_from
        mimemsg["To"] = mail_to
        mimemsg["Subject"] = mail_subject
        mimemsg.attach(MIMEText(mail_body, "plain"))
        connection = smtplib.SMTP(
            host=self.config.email.smtp_server, port=self.config.email.smtp_port
        )
        connection.starttls()
        try:
            connection.login(self.config.email.username, self.config.email.password)
            connection.send_message(mimemsg)
            connection.quit()
        except Exception as e:
            await self.config.mongo.async_site_db.failed_emails.insert_one(
                {
                    "from": mail_from,
                    "to": mail_to,
                    "subject": mail_subject,
                    "body": mail_body,
                    "exception": format_exc(),
                }
            )
