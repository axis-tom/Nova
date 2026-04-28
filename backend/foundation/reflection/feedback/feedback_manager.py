"""
反馈管理器模块。

负责收集、存储和分析用户反馈，
为学习层提供数据支持。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class FeedbackManager:
    """
    反馈管理器：
    管理用户反馈的收集、存储和分析。
    """

    def __init__(self):
        self._feedbacks: List[Dict[str, Any]] = []

    async def collect_feedback(
        self,
        user_id: int,
        feedback_type: str,
        content: Dict[str, Any],
        source: str = "user",
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        收集用户反馈。

        Args:
            user_id: 用户ID
            feedback_type: 反馈类型（如 "explicit", "implicit"）
            content: 反馈内容
            source: 反馈来源
            trace_id: 追踪ID

        Returns:
            反馈记录
        """
        feedback = {
            "id": len(self._feedbacks) + 1,
            "user_id": user_id,
            "type": feedback_type,
            "content": content,
            "source": source,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._feedbacks.append(feedback)
        return feedback

    async def get_feedbacks(
        self,
        user_id: Optional[int] = None,
        feedback_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取反馈列表。

        Args:
            user_id: 按用户筛选
            feedback_type: 按类型筛选
            limit: 返回条数限制

        Returns:
            反馈列表
        """
        result = self._feedbacks
        if user_id is not None:
            result = [f for f in result if f["user_id"] == user_id]
        if feedback_type is not None:
            result = [f for f in result if f["type"] == feedback_type]
        return result[-limit:]

    async def analyze_feedback(
        self,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        分析反馈数据。

        Args:
            user_id: 按用户筛选

        Returns:
            分析结果
        """
        feedbacks = await self.get_feedbacks(user_id=user_id)
        if not feedbacks:
            return {"total": 0, "summary": {}}

        type_counts: Dict[str, int] = {}
        for f in feedbacks:
            ftype = f["type"]
            type_counts[ftype] = type_counts.get(ftype, 0) + 1

        return {
            "total": len(feedbacks),
            "summary": type_counts,
        }
