from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.connectors.email.imap_client import IMAPClient
from backend.repositories.postgres.data_source_repo import DataSourceRepository
from backend.repositories.postgres.raw_email_repo import RawEmailRepository
from backend.utils.crypto import decrypt_password

class EmailAgent(Agent):
    def __init__(self, db: AsyncSession):
        self.db = db
        self.data_source_repo = DataSourceRepository(db)
        self.raw_email_repo = RawEmailRepository(db)

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        # print(f"[EmailAgent] Starting for user {user_id}")

        data_sources = await self.data_source_repo.list(
            user_id,
            filters={"type": "email", "enabled": True}
        )
        if not data_sources:
            # print("[EmailAgent] No active email data source found")
            return AgentOutput(result=[], metadata={"error": "No active email data source"})

        # print(f"[EmailAgent] Found {len(data_sources)} active email data sources")

        all_emails = []
        for ds in data_sources:
            # print(f"[EmailAgent] Processing data source: {ds.name} (id={ds.id})")
            config = ds.config.copy()
            if "encrypted_password" in config:
                try:
                    config["password"] = decrypt_password(config["encrypted_password"])
                    # print(f"  Decrypted password (length={len(config['password'])})")
                except Exception as e:
                    # print(f"  Failed to decrypt password: {e}")
                    continue
            else:
                # print("  No encrypted_password field, skipping")
                continue

            host = config.get("imap_server")
            port = config.get("imap_port")
            username = config.get("email")
            password = config.get("password")
            use_ssl = config.get("use_ssl", True)
            if not all([host, port, username, password]):
                # print(f"  Missing IMAP config: host={host}, port={port}, user={username}")
                continue

            try:
                client = IMAPClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl
                )
                # print(f"  Connecting to {host}:{port} SSL={use_ssl}")
                await client.connect()

                # 统一使用 fetch_since，计算起始日期
                if ds.last_collected_at:
                    since = ds.last_collected_at.strftime("%d-%b-%Y")
                    # print(f"  Incremental collection since {since}")
                else:
                    # 首次采集：获取最近7天的邮件
                    since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
                    # print(f"  First collection since {since}")

                emails = await client.fetch_since(since, limit=100)
                # print(f"  Fetched {len(emails)} emails")

                await client.disconnect()

                for email in emails:
                    try:
                        await self.raw_email_repo.create(
                            user_id=user_id,
                            data_source_id=ds.id,
                            email_data=email
                        )
                        # print(f"    Stored email: {email.get('subject')[:50]}...")
                    except Exception as e:
                        print(f"    Failed to store raw email: {e}")

                all_emails.extend(emails)

                # 更新最后采集时间（取最新邮件的日期）
                if emails:
                    latest_dt = None
                    for email in emails:
                        date_str = email.get('date')
                        if date_str:
                            try:
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(date_str)
                                if latest_dt is None or dt > latest_dt:
                                    latest_dt = dt
                            except Exception as e:
                                print(f"      Failed to parse date {date_str}: {e}")
                    if latest_dt:
                        await self.data_source_repo.update_last_collected(ds.id, user_id, latest_dt)
                        # print(f"  Updated last_collected_at to {latest_dt}")
                    else:
                        await self.data_source_repo.update_last_collected(ds.id, user_id, datetime.now())
                        # print(f"  Updated last_collected_at to current time (no date in emails)")
                else:
                    await self.data_source_repo.update_last_collected(ds.id, user_id, datetime.now())
                    # print("  No new emails, updated last_collected_at to current time")

            except Exception as e:
                # print(f"  Error fetching from {ds.name}: {e}")
                continue

        # print(f"[EmailAgent] Total emails collected: {len(all_emails)}")
        return AgentOutput(result=all_emails, metadata={"count": len(all_emails)})