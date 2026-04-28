"""
Dependency Resolver - 依赖解析器
解析图节点之间的依赖关系，确定执行顺序
"""

from typing import Dict, Any, List, Set, Optional, Tuple
from collections import defaultdict, deque


class DependencyResolver:
    """
    依赖解析器
    
    解析图节点之间的依赖关系，支持：
    1. 拓扑排序
    2. 循环依赖检测
    3. 并行执行分组
    """
    
    def __init__(self):
        self.dependencies = defaultdict(set)
        self.dependents = defaultdict(set)
    
    def add_dependency(self, node: str, depends_on: str):
        """添加依赖关系"""
        self.dependencies[node].add(depends_on)
        self.dependents[depends_on].add(node)
    
    def add_dependencies(self, node: str, depends_on: List[str]):
        """添加多个依赖关系"""
        for dep in depends_on:
            self.add_dependency(node, dep)
    
    def resolve(self) -> List[List[str]]:
        """
        解析依赖关系，返回拓扑排序后的执行分组
        
        Returns:
            按执行顺序分组的节点列表
        """
        # 检测循环依赖
        cycle = self._detect_cycle()
        if cycle:
            raise ValueError(f"Circular dependency detected: {' -> '.join(cycle)}")
        
        # 拓扑排序（Kahn算法）
        in_degree = defaultdict(int)
        all_nodes = set()
        
        for node, deps in self.dependencies.items():
            all_nodes.add(node)
            for dep in deps:
                all_nodes.add(dep)
                in_degree[node] += 1
        
        # 入度为0的节点（无依赖）
        queue = deque([n for n in all_nodes if in_degree.get(n, 0) == 0])
        
        result = []
        while queue:
            # 当前层所有节点（可并行执行）
            level = list(queue)
            result.append(level)
            
            for _ in range(len(queue)):
                node = queue.popleft()
                
                for dependent in self.dependents.get(node, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        # 检查是否所有节点都被处理
        processed = set()
        for level in result:
            processed.update(level)
        
        if processed != all_nodes:
            raise ValueError(f"Unresolved dependencies: {all_nodes - processed}")
        
        return result
    
    def get_execution_order(self) -> List[str]:
        """
        获取线性执行顺序
        
        Returns:
            线性执行顺序列表
        """
        groups = self.resolve()
        order = []
        for group in groups:
            order.extend(group)
        return order
    
    def get_parallel_groups(self) -> List[List[str]]:
        """
        获取并行执行分组
        
        Returns:
            可并行执行的节点分组
        """
        return self.resolve()
    
    def _detect_cycle(self) -> Optional[List[str]]:
        """
        检测循环依赖
        
        Returns:
            循环路径，如果没有循环则返回None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = defaultdict(int)
        parent = {}
        
        all_nodes = set(self.dependencies.keys())
        for deps in self.dependencies.values():
            all_nodes.update(deps)
        
        def dfs(node, path):
            color[node] = GRAY
            for dep in self.dependencies.get(node, set()):
                if color[dep] == GRAY:
                    # 找到循环
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]
                elif color[dep] == WHITE:
                    parent[dep] = node
                    result = dfs(dep, path + [dep])
                    if result:
                        return result
            color[node] = BLACK
            return None
        
        for node in all_nodes:
            if color[node] == WHITE:
                result = dfs(node, [node])
                if result:
                    return result
        
        return None
    
    def clear(self):
        """清除所有依赖关系"""
        self.dependencies.clear()
        self.dependents.clear()
