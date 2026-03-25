import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Any
import asyncio
import aioimaplib  # 异步IMAP库，需要安装 aioimaplib
from backend.connectors.base import DataConnector

class IMAPClient(DataConnector):
    """IMAP 邮件客户端，支持异步"""
    name = "imap_client"

    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.client = None

    async def connect(self):
        """建立连接"""
        if self.use_ssl:
            self.client = aioimaplib.IMAP4_SSL(self.host, self.port)
        else:
            self.client = aioimaplib.IMAP4(self.host, self.port)
        await self.client.wait_hello_from_server()
        await self.client.login(self.username, self.password)

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.logout()

    async def fetch_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取未读邮件，返回列表"""
        if not self.client:
            await self.connect()
        # 选择收件箱
        await self.client.select('INBOX')
        # 搜索未读邮件
        status, data = await self.client.search('UNSEEN')
        if status != 'OK':
            return []
        msg_ids = data[0].split()
        # 取最近的 limit 封
        msg_ids = msg_ids[-limit:] if msg_ids else []
        emails = []
        for msg_id in msg_ids:
            status, msg_data = await self.client.fetch(str(msg_id), '(RFC822)')
            if status != 'OK':
                continue
            raw_email = msg_data[1]
            msg = email.message_from_bytes(raw_email)
            # 解析邮件
            subject = self._decode_header(msg.get('Subject', ''))
            from_ = self._decode_header(msg.get('From', ''))
            date = msg.get('Date', '')
            body = self._get_body(msg)
            emails.append({
                'id': msg_id.decode(),
                'subject': subject,
                'from': from_,
                'date': date,
                'body': body
            })
        return emails

    def _decode_header(self, header: str) -> str:
        """解码邮件头部"""
        decoded_parts = decode_header(header)
        decoded = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded.append(part.decode(charset or 'utf-8', errors='ignore'))
                except:
                    decoded.append(part.decode('utf-8', errors='ignore'))
            else:
                decoded.append(part)
        return ''.join(decoded)

    def _get_body(self, msg) -> str:
        """提取邮件正文"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='ignore')
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='ignore')
        return ""

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """实现 DataConnector.fetch 方法"""
        limit = input_data.get('limit', 10)
        try:
            await self.connect()
            emails = await self.fetch_unread(limit)
            await self.disconnect()
            return {'data': emails, 'status': 'success'}
        except Exception as e:
            return {'data': [], 'status': 'error', 'error': str(e)}

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """发送邮件（暂不实现，仅占位）"""
        raise NotImplementedError("Sending email not implemented in this connector")