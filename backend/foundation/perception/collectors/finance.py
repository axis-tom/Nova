import asyncio
import csv
from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.connectors.financial import CSVImporter  # TODO: update path after full migration

class FinancialAgent(Agent):
    """财务数据采集智能体：从银行CSV、API等获取收支记录"""
    name = "financial_agent"
    description = "采集用户财务数据（银行流水、账单等）"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        sources = input_data.config.get("financial_sources", [])
        if not sources:
            sources = await self._get_user_financial_sources(input_data.user_id)

        if not sources:
            return AgentOutput(
                result=[],
                metadata={"error": "No financial sources configured"},
                error="No sources"
            )

        all_transactions = []
        for src in sources:
            if src["type"] == "csv_import":
                # 假设已有上传的CSV文件路径
                csv_path = src.get("file_path")
                if csv_path:
                    trans = await self._import_csv(csv_path)
                    all_transactions.extend(trans)
            elif src["type"] == "bank_api":
                # 调用银行API
                trans = await self._fetch_bank_api(src)
                all_transactions.extend(trans)

        return AgentOutput(
            result=all_transactions,
            metadata={"source": "financial", "count": len(all_transactions)}
        )

    async def _import_csv(self, file_path: str) -> List[Dict]:
        """解析CSV文件（异步读取）"""
        # 实际使用异步文件读取
        transactions = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                transactions.append(row)
        return transactions

    async def _fetch_bank_api(self, config: Dict) -> List[Dict]:
        """调用银行API获取交易记录"""
        # 模拟API调用
        await asyncio.sleep(0.5)
        return []

    async def _get_user_financial_sources(self, user_id: int) -> List[Dict]:
        """模拟从数据库获取用户财务源配置"""
        return []