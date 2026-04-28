from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.collector.base_collector import BaseCollector
from backend.common.core import AgentInput
from backend.connectors.email.imap_client import IMAPClient
from backend.repositories.postgres.raw_email_repo import RawEmailRepository
from backend.utils.crypto import decrypt_password
from backend.utils.logger import logger

class EmailAgent(BaseCollector):
    """邮件数据采集器"""
    
    name = "email_agent"
    description = "采集邮件数据"
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.raw_email_repo = RawEmailRepository(db)
    
    async def _collect_data(
        self, 
        config: Dict[str, Any],
        last_collected_at: Optional[datetime],
        input_data: AgentInput
    ) -> Dict[str, Any]:
        """
        采集邮件数据
        """
        try:
            # 解密密码
            config_copy = config.copy()
            if "encrypted_password" in config_copy:
                try:
                    config_copy["password"] = decrypt_password(config_copy["encrypted_password"])
                except Exception as e:
                    return {
                        "success": False,
                        "data": [],
                        "error": f"Failed to decrypt password: {e}",
                        "metadata": {}
                    }
            else:
                return {
                    "success": False,
                    "data": [],
                    "error": "No encrypted_password in config",
                    "metadata": {}
                }
            
            # 获取IMAP配置
            host = config_copy.get("imap_server")
            port = config_copy.get("imap_port")
            username = config_copy.get("email")
            password = config_copy.get("password")
            use_ssl = config_copy.get("use_ssl", True)
            
            if not all([host, port, username, password]):
                return {
                    "success": False,
                    "data": [],
                    "error": f"Missing IMAP config: host={host}, port={port}, user={username}",
                    "metadata": {}
                }
            
            # 连接IMAP服务器
            client = IMAPClient(
                host=host,
                port=port,
                username=username,
                password=password,
                use_ssl=use_ssl
            )
            
            await client.connect()
            
            # 计算起始时间（增量采集）
            if last_collected_at:
                since = last_collected_at.strftime("%d-%b-%Y")
                logger.info(f"[EmailAgent] Incremental collection since {since}")
            else:
                # 首次采集：获取最近7天的邮件
                since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
                logger.info(f"[EmailAgent] First collection since {since}")
            
            # 获取邮件
            emails = await client.fetch_since(since, limit=100)
            await client.disconnect()
            
            logger.info(f"[EmailAgent] Fetched {len(emails)} emails")
            
            return {
                "success": True,
                "data": emails,
                "error": None,
                "metadata": {
                    "host": host,
                    "username": username,
                    "fetched_count": len(emails)
                }
            }
            
        except Exception as e:
            logger.error(f"[EmailAgent] Collection error: {e}")
            return {
                "success": False,
                "data": [],
                "error": str(e),
                "metadata": {"exception": e.__class__.__name__}
            }
    
    async def _store_collected_data(
        self,
        user_id: int,
        data_source_id: int,
        data: List[Dict[str, Any]]
    ) -> int:
        """
        存储采集到的邮件数据
        """
        if not data:
            return 0
        
        stored_count = 0
        for email in data:
            try:
                await self.raw_email_repo.create(
                    user_id=user_id,
                    data_source_id=data_source_id,
                    email_data=email
                )
                stored_count += 1
            except Exception as e:
                logger.error(f"[EmailAgent] Failed to store email: {e}")
        
        logger.info(f"[EmailAgent] Stored {stored_count} emails for user {user_id}, source {data_source_id}")
        return stored_count
