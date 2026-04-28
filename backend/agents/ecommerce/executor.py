"""
Executor Agent - API执行Agent
负责执行具体API调用、处理执行结果
"""

from typing import Dict, Any, List
from backend.core.state import State
from backend.agents.ecommerce.base import BaseEcommerceAgent
from backend.agents.ecommerce.api_layer import APILayer, APIRequest, APIMethod, get_api_layer


class ExecutorAgent(BaseEcommerceAgent):
    """
    Executor Agent - API执行Agent
    
    职责：
    1. 执行具体API调用指令
    2. 验证API调用参数
    3. 处理API执行结果
    4. 管理API调用错误和重试
    """
    
    def __init__(self):
        """初始化Executor Agent"""
        super().__init__(
            name="ecommerce_executor",
            description="电商API执行Agent，负责执行具体API调用、处理执行结果"
        )
        self.api_layer = get_api_layer()
    
    def run(self, state: State) -> State:
        """
        执行Executor Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行API调用")
        
        try:
            # 验证输入
            if not self.validate_input(state):
                state = self.log_event(state, "error", "输入验证失败")
                state["executor_error"] = "输入数据不完整"
                state = self.add_execution_record(state, False, {"error": "输入验证失败"})
                return state
            
            # 提取执行任务
            execution_task = state.get("execution_task", {})
            parameters = state.get("parameters", {})
            context = state.get("context", {})
            
            # 根据任务类型执行API调用
            task_type = execution_task.get("type", "unknown")
            
            if task_type == "create_product":
                result = self._execute_create_product(parameters, context)
            elif task_type == "update_inventory":
                result = self._execute_update_inventory(parameters, context)
            elif task_type == "process_order":
                result = self._execute_process_order(parameters, context)
            elif task_type == "update_pricing":
                result = self._execute_update_pricing(parameters, context)
            elif task_type == "send_notification":
                result = self._execute_send_notification(parameters, context)
            else:
                result = self._execute_general_api(parameters, context)
            
            # 更新状态
            state["execution_result"] = result
            state["executor_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功完成{task_type}API调用")
            state = self.add_execution_record(state, True, {
                "task_type": task_type,
                "success": result.get("success", False),
                "api_calls": result.get("api_calls", 0)
            })
            
        except Exception as e:
            # 记录错误事件
            state = self.log_event(state, "error", f"API执行失败: {str(e)}")
            state["executor_error"] = str(e)
            state["executor_executed"] = False
            state = self.add_execution_record(state, False, {"error": str(e)})
        
        return state
    
    def get_required_fields(self) -> list:
        """
        获取必需的输入字段
        
        Returns:
            必需字段列表
        """
        return ["execution_task", "parameters"]
    
    def get_output_fields(self) -> list:
        """
        获取输出的字段
        
        Returns:
            输出字段列表
        """
        return ["execution_result", "executor_executed", "executor_error"]
    
    async def _execute_api_request(self, api_name: str, method: str, endpoint: str, 
                                 params: Dict[str, Any] = None, body: Dict[str, Any] = None,
                                 headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        执行API请求
        
        Args:
            api_name: API名称
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            body: 请求体
            headers: 请求头
            
        Returns:
            API响应结果
        """
        import asyncio
        
        # 构建API请求
        request = APIRequest(
            api_name=api_name,
            method=APIMethod(method.upper()),
            url=endpoint,
            params=params or {},
            headers=headers or {},
            body=body,
            metadata={
                "executor_agent": self.name,
                "timestamp": self._get_timestamp()
            }
        )
        
        # 执行API调用
        response = await self.api_layer.execute_api(request)
        
        return {
            "success": response.success,
            "data": response.data,
            "status_code": response.status_code,
            "execution_time": response.execution_time,
            "error_message": response.error_message,
            "metadata": response.metadata
        }
    
    def _execute_create_product(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行创建产品API
        
        Args:
            parameters: 创建产品参数
            context: 上下文信息
            
        Returns:
            创建产品结果
        """
        import asyncio
        import time
        
        # 提取产品信息
        product_data = parameters.get("product_data", {})
        platform = parameters.get("platform", "shopify")
        
        # 验证必要参数
        required_fields = ["name", "price", "description"]
        missing_fields = [field for field in required_fields if field not in product_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"缺少必要字段: {missing_fields}",
                "api_calls": 0,
                "execution_time": 0,
                "product_id": None
            }
        
        # 构建API请求
        api_name = platform  # shopify, woocommerce等
        endpoint = f"/products"
        
        # 构建请求体
        body = {
            "product": {
                "title": product_data.get("name"),
                "body_html": product_data.get("description"),
                "vendor": product_data.get("vendor", "Unknown"),
                "product_type": product_data.get("category", "General"),
                "variants": [
                    {
                        "price": str(product_data.get("price")),
                        "sku": product_data.get("sku", ""),
                        "inventory_quantity": product_data.get("stock", 0)
                    }
                ]
            }
        }
        
        # 添加可选字段
        if "images" in product_data:
            body["product"]["images"] = product_data["images"]
        
        if "tags" in product_data:
            body["product"]["tags"] = product_data["tags"]
        
        # 执行API调用（模拟）
        start_time = time.time()
        
        # 模拟API调用
        success = True  # 模拟成功
        product_id = f"prod_{int(time.time())}"
        
        execution_time = time.time() - start_time
        
        return {
            "success": success,
            "api_calls": 1,
            "execution_time": execution_time,
            "product_id": product_id,
            "platform": platform,
            "product_data": product_data,
            "api_response": {
                "id": product_id,
                "title": product_data.get("name"),
                "status": "active"
            },
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name
            }
        }
    
    def _execute_update_inventory(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行更新库存API
        
        Args:
            parameters: 更新库存参数
            context: 上下文信息
            
        Returns:
            更新库存结果
        """
        import time
        
        # 提取库存信息
        inventory_updates = parameters.get("inventory_updates", [])
        platform = parameters.get("platform", "shopify")
        
        if not inventory_updates:
            return {
                "success": False,
                "error": "没有库存更新数据",
                "api_calls": 0,
                "execution_time": 0,
                "updated_items": 0
            }
        
        # 验证库存更新数据
        valid_updates = []
        for update in inventory_updates:
            if "product_id" in update and "quantity" in update:
                valid_updates.append(update)
        
        if not valid_updates:
            return {
                "success": False,
                "error": "库存更新数据格式不正确",
                "api_calls": 0,
                "execution_time": 0,
                "updated_items": 0
            }
        
        # 执行库存更新（模拟）
        start_time = time.time()
        
        # 模拟批量API调用
        api_calls = len(valid_updates)
        updated_items = []
        
        for update in valid_updates:
            updated_items.append({
                "product_id": update["product_id"],
                "old_quantity": update.get("old_quantity", "unknown"),
                "new_quantity": update["quantity"],
                "success": True
            })
        
        execution_time = time.time() - start_time
        
        return {
            "success": True,
            "api_calls": api_calls,
            "execution_time": execution_time,
            "updated_items": len(updated_items),
            "platform": platform,
            "inventory_updates": updated_items,
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name,
                "batch_size": len(valid_updates)
            }
        }
    
    def _execute_process_order(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行处理订单API
        
        Args:
            parameters: 处理订单参数
            context: 上下文信息
            
        Returns:
            处理订单结果
        """
        import time
        
        # 提取订单信息
        order_data = parameters.get("order_data", {})
        platform = parameters.get("platform", "shopify")
        
        # 验证必要参数
        required_fields = ["customer", "line_items", "total_price"]
        missing_fields = [field for field in required_fields if field not in order_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"缺少必要字段: {missing_fields}",
                "api_calls": 0,
                "execution_time": 0,
                "order_id": None
            }
        
        # 验证订单项
        line_items = order_data.get("line_items", [])
        if not line_items:
            return {
                "success": False,
                "error": "订单没有商品项",
                "api_calls": 0,
                "execution_time": 0,
                "order_id": None
            }
        
        # 执行订单处理（模拟）
        start_time = time.time()
        
        # 模拟API调用
        success = True
        order_id = f"order_{int(time.time())}"
        
        # 模拟支付处理
        payment_success = True
        payment_id = f"pay_{int(time.time())}"
        
        # 模拟库存检查
        inventory_available = True
        for item in line_items:
            if item.get("quantity", 0) > 10:  # 模拟库存不足
                inventory_available = False
                break
        
        if not inventory_available:
            success = False
            error_message = "部分商品库存不足"
        elif not payment_success:
            success = False
            error_message = "支付处理失败"
        else:
            error_message = None
        
        execution_time = time.time() - start_time
        
        return {
            "success": success,
            "api_calls": 3,  # 创建订单、支付处理、库存检查
            "execution_time": execution_time,
            "order_id": order_id if success else None,
            "platform": platform,
            "order_data": order_data,
            "payment_id": payment_id if success else None,
            "inventory_available": inventory_available,
            "error_message": error_message,
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name,
                "line_items_count": len(line_items)
            }
        }
    
    def _execute_update_pricing(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行更新价格API
        
        Args:
            parameters: 更新价格参数
            context: 上下文信息
            
        Returns:
            更新价格结果
        """
        import time
        
        # 提取价格更新信息
        pricing_updates = parameters.get("pricing_updates", [])
        platform = parameters.get("platform", "shopify")
        
        if not pricing_updates:
            return {
                "success": False,
                "error": "没有价格更新数据",
                "api_calls": 0,
                "execution_time": 0,
                "updated_products": 0
            }
        
        # 验证价格更新数据
        valid_updates = []
        for update in pricing_updates:
            if "product_id" in update and "new_price" in update:
                valid_updates.append(update)
        
        if not valid_updates:
            return {
                "success": False,
                "error": "价格更新数据格式不正确",
                "api_calls": 0,
                "execution_time": 0,
                "updated_products": 0
            }
        
        # 执行价格更新（模拟）
        start_time = time.time()
        
        # 模拟批量API调用
        api_calls = len(valid_updates)
        updated_products = []
        
        for update in valid_updates:
            updated_products.append({
                "product_id": update["product_id"],
                "old_price": update.get("old_price", "unknown"),
                "new_price": update["new_price"],
                "success": True
            })
        
        execution_time = time.time() - start_time
        
        return {
            "success": True,
            "api_calls": api_calls,
            "execution_time": execution_time,
            "updated_products": len(updated_products),
            "platform": platform,
            "pricing_updates": updated_products,
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name,
                "batch_size": len(valid_updates)
            }
        }
    
    def _execute_send_notification(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行发送通知API
        
        Args:
            parameters: 发送通知参数
            context: 上下文信息
            
        Returns:
            发送通知结果
        """
        import time
        
        # 提取通知信息
        notification_data = parameters.get("notification_data", {})
        channel = parameters.get("channel", "email")
        
        # 验证必要参数
        required_fields = ["recipient", "subject", "message"]
        missing_fields = [field for field in required_fields if field not in notification_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"缺少必要字段: {missing_fields}",
                "api_calls": 0,
                "execution_time": 0,
                "notification_id": None
            }
        
        # 执行发送通知（模拟）
        start_time = time.time()
        
        # 模拟API调用
        success = True
        notification_id = f"notif_{int(time.time())}"
        
        # 模拟发送过程
        execution_time = time.time() - start_time
        
        return {
            "success": success,
            "api_calls": 1,
            "execution_time": execution_time,
            "notification_id": notification_id,
            "channel": channel,
            "recipient": notification_data["recipient"],
            "subject": notification_data["subject"],
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name,
                "message_length": len(notification_data.get("message", ""))
            }
        }
    
    def _execute_general_api(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行通用API
        
        Args:
            parameters: 通用API参数
            context: 上下文信息
            
        Returns:
            通用API执行结果
        """
        import time
        
        # 提取API配置
        api_config = parameters.get("api_config", {})
        
        # 验证必要参数
        required_fields = ["api_name", "method", "endpoint"]
        missing_fields = [field for field in required_fields if field not in api_config]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"缺少必要API配置字段: {missing_fields}",
                "api_calls": 0,
                "execution_time": 0,
                "response": None
            }
        
        # 执行通用API调用（模拟）
        start_time = time.time()
        
        # 模拟API调用
        success = True
        api_calls = 1
        
        # 构建模拟响应
        response = {
            "status": "success",
            "data": {
                "message": f"模拟{api_config['method']}请求到{api_config['endpoint']}",
                "timestamp": self._get_timestamp()
            },
            "metadata": {
                "api_name": api_config["api_name"],
                "method": api_config["method"],
                "endpoint": api_config["endpoint"]
            }
        }
        
        execution_time = time.time() - start_time
        
        return {
            "success": success,
            "api_calls": api_calls,
            "execution_time": execution_time,
            "response": response,
            "api_config": api_config,
            "metadata": {
                "executed_at": self._get_timestamp(),
                "agent": self.name,
                "api_type": "general"
            }
        }
    
    def validate_api_parameters(self, parameters: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """
        验证API参数
        
        Args:
            parameters: API参数
            api_type: API类型
            
        Returns:
            验证结果
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "missing_fields": []
        }
        
        # 根据API类型定义验证规则
        validation_rules = self._get_validation_rules(api_type)
        
        # 检查必要字段
        for field in validation_rules.get("required", []):
            if field not in parameters:
                validation_result["valid"] = False
                validation_result["missing_fields"].append(field)
                validation_result["errors"].append(f"缺少必要字段: {field}")
        
        # 检查字段类型
        for field, expected_type in validation_rules.get("field_types", {}).items():
            if field in parameters:
                actual_type = type(parameters[field]).__name__
                if actual_type != expected_type:
                    validation_result["warnings"].append(
                        f"字段'{field}'类型不匹配: 期望{expected_type}, 实际{actual_type}"
                    )
        
        # 检查字段值范围
        for field, value_range in validation_rules.get("value_ranges", {}).items():
            if field in parameters:
                value = parameters[field]
                if isinstance(value, (int, float)):
                    min_val, max_val = value_range
                    if value < min_val or value > max_val:
                        validation_result["warnings"].append(
                            f"字段'{field}'值超出范围: {value} (范围: {min_val}-{max_val})"
                        )
        
        return validation_result
    
    def _get_validation_rules(self, api_type: str) -> Dict[str, Any]:
        """
        获取API验证规则
        
        Args:
            api_type: API类型
            
        Returns:
            验证规则
        """
        rules = {
            "create_product": {
                "required": ["product_data", "platform"],
                "field_types": {
                    "product_data": "dict",
                    "platform": "str"
                }
            },
            "update_inventory": {
                "required": ["inventory_updates", "platform"],
                "field_types": {
                    "inventory_updates": "list",
                    "platform": "str"
                }
            },
            "process_order": {
                "required": ["order_data", "platform"],
                "field_types": {
                    "order_data": "dict",
                    "platform": "str"
                }
            },
            "update_pricing": {
                "required": ["pricing_updates", "platform"],
                "field_types": {
                    "pricing_updates": "list",
                    "platform": "str"
                }
            },
            "send_notification": {
                "required": ["notification_data", "channel"],
                "field_types": {
                    "notification_data": "dict",
                    "channel": "str"
                }
            },
            "general": {
                "required": ["api_config"],
                "field_types": {
                    "api_config": "dict"
                }
            }
        }
        
        return rules.get(api_type, rules["general"])
    
    def get_api_audit_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取API审计日志
        
        Args:
            limit: 返回条数限制
            
        Returns:
            API审计日志
        """
        return self.api_layer.get_audit_log(limit=limit)
    
    def set_api_environment(self, environment: str) -> None:
        """
        设置API环境
        
        Args:
            environment: 环境名称 (sandbox, production, staging)
        """
        from backend.agents.ecommerce.api_layer import APIEnvironment
        
        env_mapping = {
            "sandbox": APIEnvironment.SANDBOX,
            "production": APIEnvironment.PRODUCTION,
            "staging": APIEnvironment.STAGING
        }
        
        if environment in env_mapping:
            self.api_layer.set_environment(env_mapping[environment])
        else:
            raise ValueError(f"不支持的API环境: {environment}")
    
    def get_api_status(self, api_name: str = None) -> Dict[str, Any]:
        """
        获取API状态
        
        Args:
            api_name: API名称（可选）
            
        Returns:
            API状态信息
        """
        if api_name:
            return self.api_layer.get_api_status(api_name)
        else:
            # 返回所有API状态
            status = {}
            for api_name in self.api_layer.api_configs.keys():
                status[api_name] = self.api_layer.get_api_status(api_name)
            return status
