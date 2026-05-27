"""
数据库查询工具 — 安全只读查询
为 Agent 提供对 PostgreSQL 的结构化数据访问能力

安全策略：
- 只允许 SELECT 查询
- 禁止 DDL（CREATE/DROP/ALTER/TRUNCATE）
- 禁止 DML（INSERT/UPDATE/DELETE）
- 查询超时保护（5 秒）
- 结果行数限制（最多 50 行）
- 只读事务（READ ONLY）
"""

from typing import List, Dict, Any, Optional
import re
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 加载 .env 文件
env_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


# ── 安全校验 ──

# 禁止的 SQL 操作关键词
FORBIDDEN_PATTERNS = [
    r'\bCREATE\s+(TABLE|DATABASE|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA)\b',
    r'\bDROP\s+(TABLE|DATABASE|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA)\b',
    r'\bALTER\s+(TABLE|DATABASE|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA)\b',
    r'\bTRUNCATE\b',
    r'\bINSERT\s+INTO\b',
    r'\bUPDATE\s+\w+\s+SET\b',
    r'\bDELETE\s+FROM\b',
    r'\bGRANT\b',
    b'\bREVOKE\b',
    r'\bEXECUTE\b',
    r'\bEXEC\b',
    r'\bCOPY\b',
    r'\bVACUUM\b',
    r'\bANALYZE\b',
    r'\bREINDEX\b',
    r'\bCLUSTER\b',
    r'\b--',  # SQL 注释
    r'/\*',   # 块注释
]

MAX_RESULTS = 50
QUERY_TIMEOUT_SECONDS = 5


def _validate_query(sql: str) -> None:
    """
    验证 SQL 查询的安全性
    
    Raises:
        ValueError: 如果查询包含禁止的操作
    """
    sql_upper = sql.strip().upper()
    
    # 必须以 SELECT 开头
    if not sql_upper.startswith("SELECT"):
        raise ValueError("只允许 SELECT 查询")
    
    # 检查禁止模式
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sql_upper, re.IGNORECASE):
            raise ValueError(f"查询包含禁止的操作: {pattern}")


# ── 数据库连接 ──

_engine = None
_session_factory = None


def _get_engine():
    """获取数据库引擎（懒加载）"""
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL 未配置")
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def _get_session_factory():
    """获取会话工厂（懒加载）"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# ── 表信息查询 ──

async def list_tables() -> List[Dict[str, str]]:
    """
    列出数据库中所有用户表
    
    Returns:
        [{table_name, table_type, description}]
    """
    sql = """
        SELECT 
            tablename AS table_name,
            'TABLE' AS table_type,
            obj_description(c.oid) AS description
        FROM pg_tables
        JOIN pg_class c ON c.relname = tablename
        WHERE schemaname = 'public'
        ORDER BY tablename
    """
    results = await execute_query(sql)
    return results


async def describe_table(table_name: str) -> List[Dict[str, Any]]:
    """
    获取表结构信息
    
    Args:
        table_name: 表名
    
    Returns:
        [{column_name, data_type, is_nullable, column_default, is_pk}]
    """
    sql = f"""
        SELECT 
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            CASE WHEN pk.column_name IS NOT NULL THEN 'YES' ELSE 'NO' END AS is_pk
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = '{table_name}'
        ) pk ON pk.column_name = c.column_name
        WHERE c.table_name = '{table_name}'
        ORDER BY c.ordinal_position
    """
    return await execute_query(sql)


# ── 核心查询接口 ──

async def execute_query(sql: str) -> List[Dict[str, Any]]:
    """
    执行只读 SQL 查询
    
    Args:
        sql: SELECT 查询语句
    
    Returns:
        查询结果列表（每行一个 dict）
    
    Raises:
        ValueError: 查询不合法
        RuntimeError: 数据库连接失败
    """
    _validate_query(sql)
    
    factory = _get_session_factory()
    async with factory() as session:
        # 设置只读事务
        await session.execute(text("SET TRANSACTION READ ONLY"))
        
        # 执行查询
        result = await session.execute(text(sql))
        
        # 获取列名
        columns = result.keys()
        
        # 提取结果（限制行数）
        rows = result.fetchmany(MAX_RESULTS)
        
        return [dict(zip(columns, row)) for row in rows]


async def query_database(natural_query: str) -> str:
    """
    根据自然语言描述查询数据库（供 Agent 直接调用）
    
    这是一个简化接口，Agent 可以直接传入自然语言描述，
    系统会自动查询表结构并返回相关数据。
    
    当前支持：
    - "列出所有表" → 返回表列表
    - "查看 [表名] 的结构" → 返回表结构
    - "查询 [表名] 的前 10 条数据" → 返回数据预览
    - 其他 → 返回可用表列表供用户选择
    
    Args:
        natural_query: 自然语言查询描述
    
    Returns:
        格式化的查询结果文本
    """
    query_lower = natural_query.lower().strip()
    
    try:
        # 1. 列出所有表
        if query_lower in ("列出所有表", "有哪些表", "显示所有表", "list tables", "show tables"):
            tables = await list_tables()
            if not tables:
                return "数据库中暂无用户表。"
            lines = ["📋 数据库中的表：\n"]
            for t in tables:
                desc = f" — {t['description']}" if t.get('description') else ""
                lines.append(f"  - {t['table_name']}{desc}")
            return "\n".join(lines)
        
        # 2. 查看表结构
        table_match = re.match(r"查看\s*(.+?)\s*(?:的)?\s*(?:结构|字段|表结构|schema)", query_lower)
        if not table_match:
            table_match = re.match(r"(?:describe|desc|结构)\s+(.+)", query_lower)
        if table_match:
            table_name = table_match.group(1).strip().strip('"').strip("'")
            columns = await describe_table(table_name)
            if not columns:
                return f"表 '{table_name}' 不存在或没有字段。"
            lines = [f"📋 表 `{table_name}` 的结构：\n"]
            lines.append(f"{'字段名':<25} {'类型':<20} {'可空':<6} {'主键':<6} {'默认值':<20}")
            lines.append("-" * 80)
            for col in columns:
                lines.append(
                    f"{col['column_name']:<25} "
                    f"{col['data_type']:<20} "
                    f"{col['is_nullable']:<6} "
                    f"{col['is_pk']:<6} "
                    f"{str(col.get('column_default', '') or ''):<20}"
                )
            return "\n".join(lines)
        
        # 3. 查询表数据
        data_match = re.match(r"(?:查询|select|查看|预览)\s*(.+?)(?:\s*的)?\s*(?:前\s*(\d+)\s*条)?\s*(?:数据|记录|内容)?", query_lower)
        if data_match:
            table_name = data_match.group(1).strip().strip('"').strip("'")
            limit = int(data_match.group(2)) if data_match.group(2) else 10
            limit = min(limit, MAX_RESULTS)
            
            # 先检查表是否存在
            columns = await describe_table(table_name)
            if not columns:
                return f"表 '{table_name}' 不存在。可用表: {', '.join(t['table_name'] for t in await list_tables())}"
            
            sql = f'SELECT * FROM "{table_name}" LIMIT {limit}'
            rows = await execute_query(sql)
            
            if not rows:
                return f"表 `{table_name}` 中暂无数据。"
            
            # 格式化输出
            col_names = list(rows[0].keys())
            lines = [f"📋 表 `{table_name}` 的前 {len(rows)} 条数据：\n"]
            
            # 列名行
            header = " | ".join(f"{c:<20}" for c in col_names)
            lines.append(header)
            lines.append("-" * len(header))
            
            # 数据行
            for row in rows:
                values = []
                for c in col_names:
                    v = str(row[c]) if row[c] is not None else "NULL"
                    values.append(f"{v:<20}")
                lines.append(" | ".join(values))
            
            return "\n".join(lines)
        
        # 4. 无法识别的查询，返回帮助信息
        tables = await list_tables()
        table_names = [t['table_name'] for t in tables]
        return (
            "📖 数据库查询帮助\n\n"
            "支持的查询格式：\n"
            "  - 列出所有表\n"
            "  - 查看 [表名] 的结构\n"
            "  - 查询 [表名] 的前 N 条数据\n\n"
            f"当前可用表：{', '.join(table_names) if table_names else '暂无'}"
        )
    
    except ValueError as e:
        return f"⚠️ 查询安全校验失败: {e}"
    except Exception as e:
        return f"⚠️ 数据库查询失败: {e}"