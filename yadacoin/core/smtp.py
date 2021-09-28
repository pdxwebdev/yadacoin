import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from yadacoin.core.config import get_config


class Email():
    def __init__(self):
        self.config = get_config()
    
    async def send_mail(
      self,
      mail_from,
      mail_to,
      mail_subject,
      mail_body
    ):
        mimemsg = MIMEMultipart()
        mimemsg['From']=mail_from
        mimemsg['To']=mail_to
        mimemsg['Subject']=mail_subject
        mimemsg.attach(MIMEText(mail_body, 'plain'))
        connection = smtplib.SMTP(host=self.config.email.smtp_server, port=self.config.email.smtp_port)
        connection.starttls()
        connection.login(self.config.email.username, self.config.email.password)
        connection.send_message(mimemsg)
        connection.quit()
