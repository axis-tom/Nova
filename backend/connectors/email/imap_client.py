import asyncio
import aioimaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any
from datetime import datetime, timedelta
from backend.connectors.base import DataConnector

class IMAPClient(DataConnector):
    name = "imap_client"

    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.client = None

    async def connect(self, max_retries=3, base_delay=5):
        for attempt in range(max_retries):
            try:
                if self.use_ssl:
                    self.client = aioimaplib.IMAP4_SSL(self.host, self.port)
                else:
                    self.client = aioimaplib.IMAP4(self.host, self.port)
                await self.client.wait_hello_from_server()
                status, data = await self.client.login(self.username, self.password)
                # print(f"  [DEBUG] Login status: {status}, data: {data}")
                if status == 'OK':
                    return
                else:
                    error_msg = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
                    if any(k in error_msg.lower() for k in ['frequency', 'limited', 'abnormal']):
                        wait_time = base_delay * (2 ** attempt)
                        # print(f"  [DEBUG] Frequency limit, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"登录失败: {error_msg}")
            except Exception as e:
                if attempt < max_retries - 1 and 'frequency' in str(e).lower():
                    wait_time = base_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                else:
                    raise
        raise Exception("登录失败，已达最大重试次数")

    async def disconnect(self):
        if self.client:
            try:
                await self.client.logout()
            except:
                pass

    async def _fetch_messages(self, search_criteria: str, limit: int) -> List[Dict[str, Any]]:
        if not self.client:
            await self.connect()
        await self.client.select('INBOX')
        status, data = await self.client.search(search_criteria)
        if status != 'OK':
            return []
        msg_ids = data[0].split()
        msg_ids = msg_ids[-limit:] if msg_ids else []
        emails = []
        for msg_id in msg_ids:
            msg_id_str = msg_id.decode()
            # 完全按照 test_fetch2.py 的方式调用 fetch
            status, msg_data = await self.client.fetch(msg_id_str, '(RFC822)')
            # print(f"  [DEBUG] Fetch status: {status}, msg_data: {repr(msg_data)}")
            if status != 'OK':
                # print(f"  [DEBUG] Fetch failed for {msg_id_str}: {status}, {msg_data}")
                continue
            # 从 test_fetch2.py 的输出看，邮件内容在 msg_data[1] 中
            if len(msg_data) >= 2 and isinstance(msg_data[1], (bytes, bytearray)):
                raw_email = msg_data[1]
            else:
                # print(f"  [DEBUG] Unexpected msg_data format for {msg_id_str}: {msg_data}")
                continue
            try:
                msg = email.message_from_bytes(raw_email)
            except Exception as e:
                # print(f"  [DEBUG] Failed to parse email: {e}")
                continue
            subject = self._decode_header(msg.get('Subject', ''))
            from_ = self._decode_header(msg.get('From', ''))
            date = msg.get('Date', '')
            body = self._get_body(msg)
            headers = {k: v for k, v in msg.items()}
            emails.append({
                'id': msg_id_str,
                'subject': subject,
                'from': from_,
                'date': date,
                'body': body,
                'headers': headers
            })
            # print(f"  [DEBUG] Successfully parsed email: {subject[:50]}")
        return emails

    async def fetch_recent(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        return await self._fetch_messages(f'(SINCE {since_date})', limit)

    async def fetch_since(self, since_date_str: str, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._fetch_messages(f'(SINCE {since_date_str})', limit)

    def _decode_header(self, header: str) -> str:
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
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='ignore')
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='ignore')
        return ""

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        days = input_data.get('days', 7)
        limit = input_data.get('limit', 100)
        try:
            await self.connect()
            emails = await self.fetch_recent(days, limit)
            await self.disconnect()
            return {'data': emails, 'status': 'success'}
        except Exception as e:
            return {'data': [], 'status': 'error', 'error': str(e)}

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        raise NotImplementedError("Sending email not implemented in this connector")