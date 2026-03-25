import asyncio
from typing import List, Dict, Any
from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.connectors.outbound.email import EmailOutbound

class PaymentAgent(Agent):
    """
    自动催款智能体：
    根据逾期账单信息，向客户发送催款邮件或短信。
    """
    name = "payment_agent"
    description = "自动发送催款通知给逾期客户"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        overdue_invoices = input_data.data.get("overdue_invoices", [])
        if not overdue_invoices:
            return AgentOutput(
                result=[],
                metadata={"error": "No overdue invoices provided"},
                error="No data"
            )

        results = []
        for invoice in overdue_invoices:
            # 根据配置选择通知方式
            method = input_data.config.get("method", "email")  # email, sms
            if method == "email":
                success = await self._send_email(invoice)
            else:
                success = await self._send_sms(invoice)

            results.append({
                "invoice_id": invoice.get("id"),
                "customer": invoice.get("customer_name"),
                "method": method,
                "success": success
            })
            # 避免过快发送
            await asyncio.sleep(0.5)

        return AgentOutput(
            result=results,
            metadata={"count": len(results), "success_count": sum(1 for r in results if r["success"])}
        )

    async def _send_email(self, invoice: Dict[str, Any]) -> bool:
        """发送邮件催款（模拟）"""
        # 实际应使用邮件连接器
        try:
            # 构造邮件内容
            customer_email = invoice.get("email")
            amount = invoice.get("amount")
            due_date = invoice.get("due_date")
            subject = f"【催款提醒】账单 {invoice.get('id')} 已逾期"
            body = f"尊敬的客户，您的账单金额 {amount} 已于 {due_date} 逾期，请尽快处理。"
            # 假设有邮件发送函数
            # await email_client.send(customer_email, subject, body)
            await asyncio.sleep(0.2)  # 模拟网络请求
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

    async def _send_sms(self, invoice: Dict[str, Any]) -> bool:
        """发送短信催款（模拟）"""
        try:
            phone = invoice.get("phone")
            amount = invoice.get("amount")
            # 模拟发送
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            print(f"SMS send failed: {e}")
            return False