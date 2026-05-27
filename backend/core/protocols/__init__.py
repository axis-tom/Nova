"""Protocol 接口定义 — 为多 Agent 协作预留扩展点

当前实现：
- StateBackend: SQLite (DurableSession)
- MessageBus: asyncio.Queue (InMemoryBus)
- AgentRegistry: 静态列表 (list_agents)

未来可替换为：
- StateBackend: PostgreSQL + Redis 分布式锁
- MessageBus: Redis Streams / Kafka
- AgentRegistry: Consul / etcd 服务注册中心
"""

from typing import Protocol, Dict, Optional, Any, Callable, AsyncContextManager, List
from contextlib import asynccontextmanager


class StateBackend(Protocol):
    """状态存储后端接口

    职责：
    - 持久化 Agent 会话状态（State.data）
    - 支持按 conv_id + agent_id 分区存储
    - 提供写锁机制防止并发冲突
    """

    async def load_state(
        self,
        conv_id: str,
        agent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """加载会话状态

        Args:
            conv_id: 会话 ID
            agent_id: Agent ID，None 表示加载共享区

        Returns:
            状态字典，不存在返回 None
        """
        ...

    async def save_state(
        self,
        conv_id: str,
        state_data: Dict[str, Any],
        agent_id: Optional[str] = None,
        expected_version: Optional[int] = None
    ) -> None:
        """保存会话状态

        Args:
            conv_id: 会话 ID
            state_data: 要保存的状态字典
            agent_id: Agent ID，None 表示保存到共享区
            expected_version: 乐观锁版本号，不匹配则抛异常

        Raises:
            ValueError: 版本冲突（多 Agent 并发写）
        """
        ...

    def lock(
        self,
        conv_id: str,
        timeout: float = 5.0
    ) -> AsyncContextManager:
        """获取会话写锁（上下文管理器）

        Args:
            conv_id: 会话 ID
            timeout: 超时时间（秒）

        Returns:
            异步上下文管理器

        Example:
            async with backend.lock(conv_id):
                state = await backend.load_state(conv_id)
                state['key'] = 'value'
                await backend.save_state(conv_id, state)
        """
        ...


class MessageBus(Protocol):
    """Agent 间通信总线接口

    职责：
    - 发布/订阅事件（Agent 完成任务、状态变更等）
    - 解耦 Agent 之间的直接依赖
    """

    async def publish(
        self,
        topic: str,
        event: Dict[str, Any]
    ) -> None:
        """发布事件

        Args:
            topic: 主题名（如 'agent.product_collector.completed'）
            event: 事件数据字典
        """
        ...

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """订阅主题

        Args:
            topic: 主题名，支持通配符（如 'agent.*.completed'）
            handler: 事件处理函数
        """
        ...


class AgentRegistry(Protocol):
    """Agent 注册与发现接口

    职责：
    - 列出可用 Agent 及其能力
    - 查询 Agent 状态（运行中/空闲/故障）
    """

    def list_available(
        self,
        capability: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出可用 Agent

        Args:
            capability: 筛选条件（如 'data_collection'）

        Returns:
            Agent 信息列表，每项包含 name/description/input_example 等
        """
        ...

    def get_agent_status(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """查询 Agent 状态

        Args:
            agent_id: Agent ID

        Returns:
            状态字典，包含 status/last_active/error 等字段
        """
        ...
