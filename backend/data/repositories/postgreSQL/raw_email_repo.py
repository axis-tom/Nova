from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from backend.data.models.db import RawEmail
from datetime import datetime, timedelta
from typing import List, Dict, Any

class RawEmailRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data_source_id: int, email_data: dict) -> RawEmail:
        msg_id = email_data.get('id')
        if msg_id:
            stmt = select(RawEmail).where(
                RawEmail.user_id == user_id,
                RawEmail.data_source_id == data_source_id,
                RawEmail.message_id == msg_id
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # 解析日期
        date_str = email_data.get('date')
        parsed_date = None
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                parsed_date = parsedate_to_datetime(date_str)
            except:
                pass

        raw = RawEmail(
            user_id=user_id,
            data_source_id=data_source_id,
            message_id=msg_id,
            subject=email_data.get('subject'),
            from_address=email_data.get('from'),
            date=parsed_date,
            body=email_data.get('body'),
            raw_headers=email_data.get('headers')
        )
        self.db.add(raw)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            if msg_id:
                stmt = select(RawEmail).where(
                    RawEmail.user_id == user_id,
                    RawEmail.data_source_id == data_source_id,
                    RawEmail.message_id == msg_id
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    return existing
            raise
        await self.db.refresh(raw)
        return raw

    async def get_recent_emails(self, user_id: int, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(hours=hours)
        stmt = select(RawEmail).where(
            RawEmail.user_id == user_id,
            RawEmail.date >= cutoff
        ).order_by(desc(RawEmail.date)).limit(limit)
        result = await self.db.execute(stmt)
        emails = result.scalars().all()
        return [{
            'subject': e.subject,
            'from': e.from_address,
            'date': e.date.isoformat() if e.date else None,
            'body_preview': e.body[:200] if e.body else ""
        } for e in emails]