"""
统一State系统
本质：增强版dict，用于Agent之间数据传递
升级为结构化State，包含data、meta、events三个部分
保持向后兼容dict用法
"""

from typing import Any, Dict, Optional, Union, List
import copy
import json
from datetime import datetime


class State:
    """
    结构化State类
    包含data（主数据）、meta（元数据）、events（事件）三个部分
    保持向后兼容dict用法
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化State
        
        Args:
            *args: 传递给dict的args（用于向后兼容）
            **kwargs: 传递给dict的kwargs（用于向后兼容）
        """
        # 初始化三个核心部分
        self.data = {}
        self.meta = {
            "trace_id": None,
            "step": 0
        }
        self.events = []
        
        # 处理传入的初始数据
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                # 如果传入的是字典，将其作为data
                self.data = copy.deepcopy(args[0])
            elif len(args) == 1 and isinstance(args[0], State):
                # 如果传入的是State对象，复制其所有数据
                other = args[0]
                self.data = copy.deepcopy(other.data)
                self.meta = copy.deepcopy(other.meta)
                self.events = copy.deepcopy(other.events)
        
        # 处理kwargs，将其作为data的一部分
        if kwargs:
            self.data.update(kwargs)
    
    def set(self, key: str, value: Any) -> 'State':
        """
        设置data中的键值
        
        Args:
            key: 键名
            value: 值
            
        Returns:
            self（支持链式调用）
        """
        self.data[key] = value
        return self
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取data中的值
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            键对应的值，如果不存在则返回默认值
        """
        return self.data.get(key, default)
    
    def add_event(self, event: str) -> 'State':
        """
        添加事件
        
        Args:
            event: 事件描述
            
        Returns:
            self（支持链式调用）
        """
        self.events.append(event)
        return self
    
    def log(self, msg: str) -> 'State':
        """
        添加日志（向后兼容方法）
        注意：新代码应该使用 add_event() 方法
        
        Args:
            msg: 日志消息
            
        Returns:
            self（支持链式调用）
        """
        # 为了向后兼容，将日志作为事件添加
        timestamp = datetime.now().isoformat()
        self.events.append(f"[LOG][{timestamp}] {msg}")
        return self
    
    def set_meta(self, key: str, value: Any) -> 'State':
        """
        设置meta中的键值
        
        Args:
            key: 键名
            value: 值
            
        Returns:
            self（支持链式调用）
        """
        self.meta[key] = value
        return self
    
    def get_meta(self, key: str, default: Any = None) -> Any:
        """
        获取meta中的值
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            键对应的值，如果不存在则返回默认值
        """
        return self.meta.get(key, default)
    
    # 向后兼容dict的方法
    def __getitem__(self, key: str) -> Any:
        """支持dict样式的获取（从data中获取）"""
        return self.data[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持dict样式的设置（设置到data中）"""
        self.data[key] = value
    
    def __delitem__(self, key: str) -> None:
        """支持dict样式的删除（从data中删除）"""
        del self.data[key]
    
    def __contains__(self, key: str) -> bool:
        """支持in操作符（检查data中是否存在）"""
        return key in self.data
    
    def __len__(self) -> int:
        """返回data的长度"""
        return len(self.data)
    
    def __iter__(self):
        """迭代data的键"""
        return iter(self.data)
    
    def keys(self):
        """返回data的键"""
        return self.data.keys()
    
    def values(self):
        """返回data的值"""
        return self.data.values()
    
    def items(self):
        """返回data的键值对"""
        return self.data.items()
    
    def update(self, other: Dict[str, Any]) -> 'State':
        """
        更新data（向后兼容方法）
        
        Args:
            other: 要更新的字典
            
        Returns:
            self（支持链式调用）
        """
        self.data.update(other)
        return self
    
    def get_nested(self, key_path: str, default: Any = None, delimiter: str = '.') -> Any:
        """
        获取嵌套键值（从data中获取）
        
        Args:
            key_path: 键路径，如 'user.profile.name'
            default: 默认值
            delimiter: 路径分隔符，默认为'.'
            
        Returns:
            嵌套键对应的值，如果路径不存在则返回默认值
        """
        keys = key_path.split(delimiter)
        value = self.data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set_nested(self, key_path: str, value: Any, delimiter: str = '.') -> 'State':
        """
        设置嵌套键值（设置到data中）
        
        Args:
            key_path: 键路径，如 'user.profile.name'
            value: 要设置的值
            delimiter: 路径分隔符，默认为'.'
            
        Returns:
            self（支持链式调用）
        """
        keys = key_path.split(delimiter)
        current = self.data
        
        # 遍历到倒数第二个键，确保路径存在
        for i, key in enumerate(keys[:-1]):
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        
        # 设置最后一个键的值
        current[keys[-1]] = value
        return self
    
    def update_nested(self, updates: Dict[str, Any], delimiter: str = '.') -> 'State':
        """
        批量更新嵌套键值
        
        Args:
            updates: 更新字典，键为路径
            delimiter: 路径分隔符，默认为'.'
            
        Returns:
            self（支持链式调用）
        """
        for key_path, value in updates.items():
            self.set_nested(key_path, value, delimiter)
        return self
    
    def has_key(self, key: str) -> bool:
        """
        检查键是否存在（兼容性方法）
        
        Args:
            key: 要检查的键
            
        Returns:
            键是否存在
        """
        return key in self.data
    
    def copy(self) -> 'State':
        """
        创建深拷贝
        
        Returns:
            新的State实例
        """
        new_state = State()
        new_state.data = copy.deepcopy(self.data)
        new_state.meta = copy.deepcopy(self.meta)
        new_state.events = copy.deepcopy(self.events)
        return new_state
    
    def merge(self, other: Union[Dict[str, Any], 'State'], overwrite: bool = True) -> 'State':
        """
        合并另一个字典或State对象
        
        Args:
            other: 要合并的字典或State对象
            overwrite: 是否覆盖已存在的键
            
        Returns:
            self（支持链式调用）
        """
        if isinstance(other, State):
            # 合并data
            for key, value in other.data.items():
                if overwrite or key not in self.data:
                    self.data[key] = value
            # 合并meta
            for key, value in other.meta.items():
                if overwrite or key not in self.meta:
                    self.meta[key] = value
            # 合并events
            self.events.extend(other.events)
        else:
            # 合并字典到data
            for key, value in other.items():
                if overwrite or key not in self.data:
                    self.data[key] = value
        return self
    
    def to_plain_dict(self) -> Dict[str, Any]:
        """
        转换为普通字典（只包含data部分，用于向后兼容）
        
        Returns:
            普通字典
        """
        return dict(self.data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为完整字典表示
        
        Returns:
            包含data、meta、events的字典
        """
        return {
            'data': copy.deepcopy(self.data),
            'meta': copy.deepcopy(self.meta),
            'events': copy.deepcopy(self.events)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'State':
        """
        从字典创建State
        
        Args:
            data: 源字典
            
        Returns:
            新的State实例
        """
        state = cls()
        if 'data' in data:
            state.data = copy.deepcopy(data['data'])
        else:
            # 向后兼容：如果没有data键，假设整个字典是data
            state.data = copy.deepcopy(data)
        
        if 'meta' in data:
            state.meta = copy.deepcopy(data['meta'])
        
        # 处理 events 或 logs（向后兼容）
        if 'events' in data:
            state.events = copy.deepcopy(data['events'])
        elif 'logs' in data:
            # 将旧格式的 logs 转换为 events（添加 [LOG] 前缀）
            for log_msg in data['logs']:
                if isinstance(log_msg, str):
                    # 如果日志消息已经有时间戳格式，保持原样
                    if log_msg.startswith('[') and ']' in log_msg:
                        state.events.append(log_msg)
                    else:
                        # 添加 [LOG] 前缀
                        state.events.append(f"[LOG] {log_msg}")
        
        return state
    
    def clear(self) -> None:
        """清空所有数据"""
        self.data.clear()
        self.meta.clear()
        self.events.clear()
    
    def clear_events(self) -> 'State':
        """清空事件"""
        self.events.clear()
        return self
    
    def get_event_summary(self) -> str:
        """获取事件摘要"""
        if not self.events:
            return "No events"
        return f"{len(self.events)} events, last: {self.events[-1][:50]}..."
    
    def __str__(self) -> str:
        """字符串表示"""
        data_str = json.dumps(self.data, ensure_ascii=False, indent=2)
        meta_str = json.dumps(self.meta, ensure_ascii=False, indent=2)
        events_count = len(self.events)
        return f"State(data={data_str}, meta={meta_str}, events={events_count} items)"
    
    def __repr__(self) -> str:
        """repr表示"""
        return f"State(data={repr(self.data)}, meta={repr(self.meta)}, events={len(self.events)} items)"


# 使用示例
if __name__ == "__main__":
    # 创建State
    state = State({
        "user": {
            "id": 123,
            "name": "Alice"
        },
        "task": "processing"
    })
    
    print("初始State:", state)
    print("data部分:", state.data)
    print("meta部分:", state.meta)
    print("events部分:", state.events)
    
    # 基本操作
    state["status"] = "active"
    state.set("priority", "high")
    print("\n添加status和priority后:")
    print("data:", state.data)
    
    # 元数据操作
    state.set_meta("created_at", "2024-01-01")
    state.set_meta("source", "test")
    print("\n添加元数据后:")
    print("meta:", state.meta)
    
    # 事件操作
    state.add_event("开始处理任务")
    state.add_event("任务处理中...")
    state.add_event("任务完成")
    print("\n添加事件后:")
    print("events:", state.events)
    
    # 嵌套操作
    print("\n获取嵌套值 user.name:", state.get_nested("user.name"))
    
    state.set_nested("user.profile.age", 30)
    print("设置嵌套值后:", state.get_nested("user.profile.age"))
    
    # 批量更新
    state.update_nested({
        "user.profile.city": "Beijing",
        "task.progress": 50
    })
    print("\n批量更新后:")
    print("user.profile.city:", state.get_nested("user.profile.city"))
    print("task.progress:", state.get_nested("task.progress"))
    
    # 合并
    other_data = {"new_key": "new_value", "status": "updated"}
    state.merge(other_data)
    print("\n合并后 status:", state.get("status"))
    
    # 拷贝
    state_copy = state.copy()
    state_copy["copied"] = True
    print("\n原始State是否有copied键:", "copied" in state)
    print("拷贝State是否有copied键:", "copied" in state_copy)
    
    # 转换为字典
    print("\n转换为普通字典:", state.to_plain_dict())
    print("转换为完整字典:", state.to_dict())
    
    # 从字典创建
    new_state = State.from_dict({
        "data": {"test": "value"},
        "meta": {"type": "test"},
        "events": ["event1", "event2"]
    })
    print("\n从字典创建的State:")
    print("data:", new_state.data)
    print("meta:", new_state.meta)
    print("events:", new_state.events)
    
    print("\n✅ State系统升级完成，工作正常！")
