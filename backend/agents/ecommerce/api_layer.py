"""
API执行层
统一管理所有外部API调用，提供限流、审计、重试等功能
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum


class APIEnvironment(Enum):
    """API环境枚举"""
    SANDBOX = "sandbox"
    PRODUCTION = "production"
    STAGING = "staging"


class APIMethod(Enum):
    """API方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class APIRequest:
    """API请求数据类"""
    api_name: str
    method: APIMethod
    url: str
    params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if isinstance(self.method, str):
            self.method = APIMethod(self.method.upper())


@dataclass
class APIResponse:
    """API响应数据类"""
    success: bool
    data: Any
    status_code: int
    headers: Dict[str, str]
    execution_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "status_code": self.status_code,
            "headers": self.headers,
            "execution_time": self.execution_time,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


@dataclass
class APIConfig:
    """API配置数据类"""
    name: str
    base_url: str
    sandbox_url: Optional[str] = None
    default_headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    max_retries: int = 3
    rate_limit: Optional[int] = None  # 每分钟最大请求数
    enabled: bool = True
    requires_auth: bool = False
    auth_type: str = "bearer"  # bearer, api_key, basic, oauth2
    metadata: Dict[str, Any] = field(default_factory=dict)


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, requests_per_minute: int):
        """
        初始化速率限制器
        
        Args:
            requests_per_minute: 每分钟最大请求数
        """
        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        获取请求许可
        
        Raises:
            RateLimitExceeded: 如果超过速率限制
        """
        async with self.lock:
            now = time.time()
            
            # 清理超过1分钟的请求记录
            cutoff = now - 60
            self.request_times = [t for t in self.request_times if t > cutoff]
            
            # 检查是否超过限制
            if len(self.request_times) >= self.requests_per_minute:
                # 计算需要等待的时间
                oldest_request = self.request_times[0]
                wait_time = 60 - (now - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # 重新清理并检查
                    return await self.acquire()
            
            # 记录本次请求
            self.request_times.append(now)


class APILayer:
    """
    API执行层
    统一管理所有外部API调用
    """
    
    def __init__(self, environment: APIEnvironment = APIEnvironment.SANDBOX):
        """
        初始化API执行层
        
        Args:
            environment: API环境
        """
        self.environment = environment
        self.api_configs: Dict[str, APIConfig] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.request_id_counter = 0
        
        # 注册默认API
        self._register_default_apis()
    
    def _register_default_apis(self) -> None:
        """注册默认API配置"""
        # 电商平台API
        self.register_api(APIConfig(
            name="shopify",
            base_url="https://api.shopify.com",
            sandbox_url="https://sandbox.shopify.com",
            default_headers={"Content-Type": "application/json"},
            rate_limit=60,
            requires_auth=True,
            auth_type="bearer"
        ))
        
        self.register_api(APIConfig(
            name="woocommerce",
            base_url="https://example.com/wp-json/wc/v3",
            sandbox_url="https://sandbox.example.com/wp-json/wc/v3",
            default_headers={"Content-Type": "application/json"},
            rate_limit=120,
            requires_auth=True,
            auth_type="basic"
        ))
        
        self.register_api(APIConfig(
            name="payment_gateway",
            base_url="https://api.payment.com",
            sandbox_url="https://sandbox.payment.com",
            default_headers={"Content-Type": "application/json"},
            rate_limit=30,
            requires_auth=True,
            auth_type="api_key"
        ))
        
        self.register_api(APIConfig(
            name="shipping_carrier",
            base_url="https://api.shipping.com",
            sandbox_url="https://sandbox.shipping.com",
            default_headers={"Content-Type": "application/json"},
            rate_limit=100,
            requires_auth=False
        ))
    
    def register_api(self, config: APIConfig) -> None:
        """
        注册API配置
        
        Args:
            config: API配置
            
        Raises:
            ValueError: 如果API名称已存在
        """
        if config.name in self.api_configs:
            raise ValueError(f"API '{config.name}' is already registered")
        
        self.api_configs[config.name] = config
        
        # 创建速率限制器
        if config.rate_limit:
            self.rate_limiters[config.name] = RateLimiter(config.rate_limit)
        
        print(f"✅ 注册API: {config.name} ({self.environment.value})")
    
    def get_base_url(self, api_name: str) -> str:
        """
        获取API的基础URL
        
        Args:
            api_name: API名称
            
        Returns:
            基础URL
            
        Raises:
            KeyError: 如果API未注册
        """
        if api_name not in self.api_configs:
            raise KeyError(f"API '{api_name}' is not registered")
        
        config = self.api_configs[api_name]
        
        if self.environment == APIEnvironment.SANDBOX and config.sandbox_url:
            return config.sandbox_url
        else:
            return config.base_url
    
    def _generate_request_id(self) -> str:
        """生成请求ID"""
        self.request_id_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"req_{timestamp}_{self.request_id_counter}"
    
    def _log_audit(self, request: APIRequest, response: APIResponse, start_time: float) -> None:
        """
        记录审计日志
        
        Args:
            request: API请求
            response: API响应
            start_time: 开始时间
        """
        audit_entry = {
            "request_id": self._generate_request_id(),
            "timestamp": datetime.now().isoformat(),
            "api_name": request.api_name,
            "method": request.method.value,
            "url": request.url,
            "environment": self.environment.value,
            "success": response.success,
            "status_code": response.status_code,
            "execution_time": response.execution_time,
            "error_message": response.error_message,
            "request_metadata": request.metadata,
            "response_metadata": response.metadata
        }
        
        # 安全处理：不记录敏感数据
        safe_request = {
            "params": request.params,
            "headers": {k: "***" if "auth" in k.lower() or "token" in k.lower() else v 
                       for k, v in request.headers.items()}
        }
        
        if request.body:
            # 尝试序列化body，如果失败则记录类型
            try:
                if isinstance(request.body, (dict, list)):
                    safe_request["body"] = json.dumps(request.body)
                else:
                    safe_request["body"] = str(request.body)
            except:
                safe_request["body_type"] = type(request.body).__name__
        
        audit_entry["request_details"] = safe_request
        self.audit_log.append(audit_entry)
        
        # 限制审计日志大小
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    async def _make_http_request(self, request: APIRequest) -> APIResponse:
        """
        执行HTTP请求（模拟实现）
        
        Args:
            request: API请求
            
        Returns:
            API响应
        """
        # 这里应该是实际的HTTP请求实现
        # 为了演示，我们使用模拟实现
        
        import random
        
        # 模拟网络延迟
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # 模拟成功率
        success_rate = 0.95 if self.environment == APIEnvironment.PRODUCTION else 0.99
        success = random.random() < success_rate
        
        if success:
            # 模拟成功响应
            mock_data = {
                "id": f"mock_{int(time.time())}",
                "status": "success",
                "data": {"message": f"Mock response for {request.api_name}"}
            }
            
            return APIResponse(
                success=True,
                data=mock_data,
                status_code=200,
                headers={"Content-Type": "application/json"},
                execution_time=random.uniform(0.2, 0.8),
                metadata={"mock": True}
            )
        else:
            # 模拟失败响应
            error_messages = [
                "Network timeout",
                "Server error",
                "Invalid response",
                "Rate limit exceeded"
            ]
            
            return APIResponse(
                success=False,
                data=None,
                status_code=random.choice([400, 401, 403, 404, 429, 500, 502, 503]),
                headers={"Content-Type": "application/json"},
                execution_time=random.uniform(0.5, 2.0),
                error_message=random.choice(error_messages),
                metadata={"mock": True, "retry_attempt": request.metadata.get("retry_attempt", 0)}
            )
    
    async def execute_api(self, request: APIRequest) -> APIResponse:
        """
        执行API调用
        
        Args:
            request: API请求
            
        Returns:
            API响应
        """
        start_time = time.time()
        
        # 检查API是否已注册
        if request.api_name not in self.api_configs:
            error_response = APIResponse(
                success=False,
                data=None,
                status_code=400,
                headers={},
                execution_time=time.time() - start_time,
                error_message=f"API '{request.api_name}' is not registered"
            )
            self._log_audit(request, error_response, start_time)
            return error_response
        
        # 检查API是否启用
        config = self.api_configs[request.api_name]
        if not config.enabled:
            error_response = APIResponse(
                success=False,
                data=None,
                status_code=400,
                headers={},
                execution_time=time.time() - start_time,
                error_message=f"API '{request.api_name}' is disabled"
            )
            self._log_audit(request, error_response, start_time)
            return error_response
        
        # 应用速率限制
        if request.api_name in self.rate_limiters:
            try:
                await self.rate_limiters[request.api_name].acquire()
            except Exception as e:
                error_response = APIResponse(
                    success=False,
                    data=None,
                    status_code=429,
                    headers={},
                    execution_time=time.time() - start_time,
                    error_message=f"Rate limit exceeded: {str(e)}"
                )
                self._log_audit(request, error_response, start_time)
                return error_response
        
        # 重试逻辑
        max_retries = min(request.retry_count, config.max_retries)
        last_response = None
        
        for attempt in range(max_retries + 1):
            try:
                # 设置重试元数据
                request.metadata["retry_attempt"] = attempt
                request.metadata["total_attempts"] = max_retries + 1
                
                # 执行请求
                response = await self._make_http_request(request)
                last_response = response
                
                # 记录审计日志
                self._log_audit(request, response, start_time)
                
                # 如果成功或达到最大重试次数，返回结果
                if response.success or attempt == max_retries:
                    return response
                
                # 失败但可以重试，等待后继续
                if attempt < max_retries:
                    await asyncio.sleep(request.retry_delay * (2 ** attempt))  # 指数退避
                    
            except Exception as e:
                # 记录异常
                error_response = APIResponse(
                    success=False,
                    data=None,
                    status_code=500,
                    headers={},
                    execution_time=time.time() - start_time,
                    error_message=f"Request failed with exception: {str(e)}",
                    metadata={"exception": str(type(e).__name__)}
                )
                last_response = error_response
                
                # 记录审计日志
                self._log_audit(request, error_response, start_time)
                
                if attempt == max_retries:
                    return error_response
                
                # 等待后重试
                await asyncio.sleep(request.retry_delay * (2 ** attempt))
        
        # 理论上不会执行到这里
        return last_response or APIResponse(
            success=False,
            data=None,
            status_code=500,
            headers={},
            execution_time=time.time() - start_time,
            error_message="Unknown error in execute_api"
        )
    
    def get_audit_log(self, limit: int = 100, api_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取审计日志
        
        Args:
            limit: 返回条数限制
            api_name: 过滤API名称
            
        Returns:
            审计日志列表
        """
        logs = self.audit_log
        
        if api_name:
            logs = [log for log in logs if log["api_name"] == api_name]
        
        return logs[-limit:] if limit > 0 else logs
    
    def clear_audit_log(self) -> None:
        """清空审计日志"""
        self.audit_log.clear()
    
    def set_environment(self, environment: APIEnvironment) -> None:
        """
        设置API环境
        
        Args:
            environment: 新的环境
        """
        self.environment = environment
        print(f"✅ 切换API环境到: {environment}")
    
    def get_api_status(self, api_name: str) -> Dict[str, Any]:
        """
        获取API状态
        
        Args:
            api_name: API名称
            
        Returns:
            API状态信息
        """
        if api_name not in self.api_configs:
            raise KeyError(f"API '{api_name}' is not registered")
        
        config = self.api_configs[api_name]
        
        # 获取最近的审计日志
        recent_logs = self.get_audit_log(limit=10, api_name=api_name)
        
        # 计算成功率
        if recent_logs:
            success_count = sum(1 for log in recent_logs if log["success"])
            success_rate = success_count / len(recent_logs)
        else:
            success_rate = 0.0
        
        return {
            "name": config.name,
            "enabled": config.enabled,
            "environment": self.environment.value,
            "base_url": self.get_base_url(api_name),
            "rate_limit": config.rate_limit,
            "requires_auth": config.requires_auth,
            "recent_success_rate": success_rate,
            "recent_requests": len(recent_logs),
            "metadata": config.metadata
        }


# 全局APILayer实例
_api_layer_instance: Optional[APILayer] = None


def get_api_layer() -> APILayer:
    """
    获取全局APILayer实例
    
    Returns:
        APILayer实例
    """
    global _api_layer_instance
    if _api_layer_instance is None:
        _api_layer_instance = APILayer()
    return _api_layer_instance


def set_api_layer(instance: APILayer) -> None:
    """
    设置全局APILayer实例
    
    Args:
        instance: APILayer实例
    """
    global _api_layer_instance
    _api_layer_instance = instance