"""
数据语义层 - ContextualData 模块
实现统一的数据结构，解决 sandbox/production 数据污染问题

所有 collector 输出必须转换为：
{
    context: {
        env: "sandbox | production",
        source: "email | rss | social",
        collector: string,
        trace_id: string
    },
    payload: object
}
"""

from typing import Dict, Any, Optional, Union, List
from datetime import datetime
import uuid
import copy
from enum import Enum


class Environment(Enum):
    """环境枚举"""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class DataSource(Enum):
    """数据源枚举"""
    EMAIL = "email"
    RSS = "rss"
    SOCIAL = "social"
    FINANCIAL = "financial"
    NEWS = "news"
    COMPETITOR = "competitor"


class ContextualData:
    """
    上下文数据包装器
    
    确保所有数据都携带完整的上下文信息，防止环境数据污染
    """
    
    def __init__(
        self,
        env: Union[Environment, str],
        source: Union[DataSource, str],
        collector: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        初始化上下文数据
        
        Args:
            env: 环境 (sandbox/production)
            source: 数据源 (email/rss/social等)
            collector: 采集器名称
            payload: 实际数据负载
            trace_id: 追踪ID，如果未提供则自动生成
            metadata: 附加元数据
        """
        # 标准化环境
        if isinstance(env, str):
            env = env.lower()
            if env not in [e.value for e in Environment]:
                raise ValueError(f"Invalid environment: {env}. Must be one of: {[e.value for e in Environment]}")
            self.env = env
        elif isinstance(env, Environment):
            self.env = env.value
        else:
            raise ValueError(f"env must be str or Environment enum, got {type(env)}")
        
        # 标准化数据源
        if isinstance(source, str):
            source = source.lower()
            # 允许自定义数据源，但建议使用预定义枚举
            self.source = source
        elif isinstance(source, DataSource):
            self.source = source.value
        else:
            raise ValueError(f"source must be str or DataSource enum, got {type(source)}")
        
        self.collector = collector
        self.payload = copy.deepcopy(payload) if payload else {}
        
        # 生成或使用提供的trace_id
        self.trace_id = trace_id or str(uuid.uuid4())
        
        # 元数据
        self.metadata = copy.deepcopy(metadata) if metadata else {}
        self.metadata.update({
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为标准字典格式
        
        Returns:
            标准格式字典:
            {
                "context": {
                    "env": "sandbox | production",
                    "source": "email | rss | social",
                    "collector": string,
                    "trace_id": string
                },
                "payload": object
            }
        """
        return {
            "context": {
                "env": self.env,
                "source": self.source,
                "collector": self.collector,
                "trace_id": self.trace_id,
                **self.metadata
            },
            "payload": self.payload
        }
    
    def to_state(self) -> Dict[str, Any]:
        """
        转换为State兼容格式
        
        Returns:
            适合State对象使用的字典格式
        """
        return {
            "contextual_data": self.to_dict(),
            "payload": self.payload,  # 保持向后兼容
            "context": self.get_context()  # 提供便捷访问
        }
    
    def get_context(self) -> Dict[str, Any]:
        """
        获取上下文信息
        
        Returns:
            上下文字典
        """
        return {
            "env": self.env,
            "source": self.source,
            "collector": self.collector,
            "trace_id": self.trace_id
        }
    
    def is_sandbox(self) -> bool:
        """
        检查是否为沙箱环境
        
        Returns:
            True如果是沙箱环境
        """
        return self.env == Environment.SANDBOX.value
    
    def is_production(self) -> bool:
        """
        检查是否为生产环境
        
        Returns:
            True如果是生产环境
        """
        return self.env == Environment.PRODUCTION.value
    
    def get_payload(self, key: str = None, default: Any = None) -> Any:
        """
        安全获取payload数据
        
        Args:
            key: 要获取的键，如果为None则返回整个payload
            default: 默认值
            
        Returns:
            payload中的值或整个payload
        """
        if key is None:
            return self.payload
        return self.payload.get(key, default)
    
    def update_payload(self, updates: Dict[str, Any]) -> 'ContextualData':
        """
        更新payload数据
        
        Args:
            updates: 更新字典
            
        Returns:
            self（支持链式调用）
        """
        self.payload.update(updates)
        return self
    
    def merge(self, other: 'ContextualData') -> 'ContextualData':
        """
        合并另一个ContextualData（仅合并payload）
        
        Args:
            other: 要合并的ContextualData
            
        Returns:
            新的ContextualData实例
        """
        if self.trace_id != other.trace_id:
            raise ValueError("Cannot merge ContextualData with different trace_ids")
        
        if self.env != other.env:
            raise ValueError(f"Cannot merge ContextualData from different environments: {self.env} vs {other.env}")
        
        # 合并payload
        merged_payload = copy.deepcopy(self.payload)
        merged_payload.update(copy.deepcopy(other.payload))
        
        # 合并metadata
        merged_metadata = copy.deepcopy(self.metadata)
        merged_metadata.update(copy.deepcopy(other.metadata))
        
        return ContextualData(
            env=self.env,
            source=self.source,
            collector=self.collector,
            payload=merged_payload,
            trace_id=self.trace_id,
            metadata=merged_metadata
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextualData':
        """
        从字典创建ContextualData
        
        Args:
            data: 字典数据，必须包含context和payload
            
        Returns:
            ContextualData实例
        """
        if "context" not in data or "payload" not in data:
            raise ValueError("Dictionary must contain 'context' and 'payload' keys")
        
        context = data["context"]
        payload = data["payload"]
        
        # 从context中提取必要字段
        env = context.get("env")
        source = context.get("source")
        collector = context.get("collector")
        trace_id = context.get("trace_id")
        
        if not all([env, source, collector]):
            raise ValueError("Context must contain 'env', 'source', and 'collector'")
        
        # 提取metadata（排除核心字段）
        metadata = copy.deepcopy(context)
        for key in ["env", "source", "collector", "trace_id"]:
            metadata.pop(key, None)
        
        return cls(
            env=env,
            source=source,
            collector=collector,
            payload=payload,
            trace_id=trace_id,
            metadata=metadata
        )
    
    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> 'ContextualData':
        """
        从State字典创建ContextualData
        
        Args:
            state: State字典，可能包含contextual_data或直接包含context/payload
            
        Returns:
            ContextualData实例
        """
        # 检查是否有contextual_data字段
        if "contextual_data" in state:
            return cls.from_dict(state["contextual_data"])
        
        # 检查是否有context和payload字段
        if "context" in state and "payload" in state:
            return cls.from_dict({
                "context": state["context"],
                "payload": state["payload"]
            })
        
        # 尝试从State的data中提取
        if "data" in state and isinstance(state["data"], dict):
            data = state["data"]
            if "context" in data and "payload" in data:
                return cls.from_dict(data)
        
        raise ValueError("State does not contain valid contextual data format")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ContextualData(env={self.env}, source={self.source}, collector={self.collector}, trace_id={self.trace_id[:8]}..., payload_keys={list(self.payload.keys())})"
    
    def __repr__(self) -> str:
        """repr表示"""
        return f"ContextualData(env={self.env}, source={self.source}, collector={self.collector})"


class ContextWrapper:
    """
    上下文包装器 - 负责包装collector输出数据，自动注入env/source/trace_id
    
    所有collector必须调用ContextWrapper，禁止直接输出原始数据
    """
    
    @staticmethod
    def wrap(
        env: Union[Environment, str],
        source: Union[DataSource, str],
        collector: str,
        data: Any,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextualData:
        """
        包装数据为ContextualData
        
        Args:
            env: 环境
            source: 数据源
            collector: 采集器名称
            data: 原始数据
            trace_id: 追踪ID
            metadata: 附加元数据
            
        Returns:
            ContextualData实例
        """
        # 确保数据是字典格式
        if not isinstance(data, dict):
            payload = {"raw_data": data}
        else:
            payload = data
        
        return ContextualData(
            env=env,
            source=source,
            collector=collector,
            payload=payload,
            trace_id=trace_id,
            metadata=metadata
        )
    
    @staticmethod
    def wrap_collector_output(
        collector_name: str,
        data: Any,
        env: Optional[Union[Environment, str]] = None,
        source: Optional[Union[DataSource, str]] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextualData:
        """
        包装collector输出（简化版）
        
        Args:
            collector_name: 采集器名称
            data: 采集到的数据
            env: 环境，如果未提供则从collector名称推断
            source: 数据源，如果未提供则从collector名称推断
            trace_id: 追踪ID
            metadata: 附加元数据
            
        Returns:
            ContextualData实例
        """
        # 推断环境（如果未提供）
        if env is None:
            # 根据collector名称推断环境
            if "sandbox" in collector_name.lower() or "test" in collector_name.lower():
                env = Environment.SANDBOX
            else:
                env = Environment.PRODUCTION
        
        # 推断数据源（如果未提供）
        if source is None:
            # 根据collector名称推断数据源
            collector_lower = collector_name.lower()
            if "email" in collector_lower:
                source = DataSource.EMAIL
            elif "rss" in collector_lower:
                source = DataSource.RSS
            elif "social" in collector_lower:
                source = DataSource.SOCIAL
            elif "financial" in collector_lower:
                source = DataSource.FINANCIAL
            elif "news" in collector_lower:
                source = DataSource.NEWS
            elif "competitor" in collector_lower:
                source = DataSource.COMPETITOR
            else:
                source = "unknown"
        
        return ContextWrapper.wrap(
            env=env,
            source=source,
            collector=collector_name,
            data=data,
            trace_id=trace_id,
            metadata=metadata
        )
    
    @staticmethod
    def extract_payload(contextual_data: Union[ContextualData, Dict[str, Any]]) -> Dict[str, Any]:
        """
        从ContextualData中提取payload（供Graph/AI使用）
        
        Args:
            contextual_data: ContextualData实例或字典
            
        Returns:
            payload字典
        """
        if isinstance(contextual_data, ContextualData):
            return contextual_data.payload
        elif isinstance(contextual_data, dict):
            if "payload" in contextual_data:
                return contextual_data["payload"]
            elif "contextual_data" in contextual_data and "payload" in contextual_data["contextual_data"]:
                return contextual_data["contextual_data"]["payload"]
        
        raise ValueError("Cannot extract payload from invalid contextual data")
    
    @staticmethod
    def validate_context(contextual_data: Union[ContextualData, Dict[str, Any]]) -> bool:
        """
        验证上下文数据格式
        
        Args:
            contextual_data: 要验证的数据
            
        Returns:
            是否有效
        """
        try:
            if isinstance(contextual_data, dict):
                # 转换为ContextualData进行验证
                ContextualData.from_dict(contextual_data)
            elif isinstance(contextual_data, ContextualData):
                # 已经是ContextualData，检查必要字段
                if not all([contextual_data.env, contextual_data.source, contextual_data.collector, contextual_data.trace_id]):
                    return False
            else:
                return False
            return True
        except Exception:
            return False


# 全局辅助函数
def create_contextual_data(env: str, source: str, collector: str, payload: Dict[str, Any], **kwargs) -> ContextualData:
    """创建上下文数据的快捷函数"""
    return ContextualData(env=env, source=source, collector=collector, payload=payload, **kwargs)


def is_sandbox_data(data: Union[ContextualData, Dict[str, Any]]) -> bool:
    """检查数据是否来自沙箱环境"""
    if isinstance(data, ContextualData):
        return data.is_sandbox()
    elif isinstance(data, dict):
        try:
            contextual_data = ContextualData.from_dict(data)
            return contextual_data.is_sandbox()
        except Exception:
            return False
    return False


def is_production_data(data: Union[ContextualData, Dict[str, Any]]) -> bool:
    """检查数据是否来自生产环境"""
    if isinstance(data, ContextualData):
        return data.is_production()
    elif isinstance(data, dict):
        try:
            contextual_data = ContextualData.from_dict(data)
            return contextual_data.is_production()
        except Exception:
            return False
    return False
