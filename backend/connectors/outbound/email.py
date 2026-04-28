import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

from backend.perception.connectors.base import DataConnector

class EmailOutbound(DataConnector):
    """邮件发送连接器，使用 SMTP 发送邮件"""
    name = "email_outbound"

    def __init__(self, smtp_host: str = None, smtp_port: int = None, username: str = None, password: str = None):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    async def send_email(self, to: str, subject: str, body: str, from_addr: str = None) -> bool:
        """同步发送邮件，通过线程池执行"""
        # 使用默认配置或传入参数
        host = self.smtp_host
        port = self.smtp_port
        user = self.username
        pwd = self.password

        if not host or not user:
            return False

        msg = MIMEMultipart()
        msg["From"] = from_addr or user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            # 在线程池中运行阻塞的 SMTP 操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._smtp_send, host, port, user, pwd, msg)
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

    def _smtp_send(self, host, port, user, pwd, msg):
        """同步 SMTP 发送函数"""
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """邮件发送器不支持拉取"""
        raise NotImplementedError("Email outbound does not support fetch")

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """实现推送方法，发送邮件"""
        to = config.get("to")
        subject = output_data.get("subject", "No subject")
        body = output_data.get("body", "")
        from_addr = config.get("from")

        if not to:
            return False
        return await self.send_email(to, subject, body, from_addr)