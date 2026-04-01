from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Any

from backend.core.database import get_db
from backend.repositories.postgres.data_source_repo import DataSourceRepository
from backend.api.v1.auth import get_current_user
from backend.models.user import UserOut
from backend.models.data_source import DataSourceCreate, DataSourceUpdate
from backend.config.data_source_providers import DATA_SOURCE_TYPES, PROVIDERS_MAP
from backend.utils.crypto import encrypt_password

router = APIRouter(prefix="/data-sources", tags=["数据源"])

class TestConnectionRequest(BaseModel):
    type: str
    config: Dict[str, Any]

# ---------- 辅助函数：敏感字段加密 ----------
def _encrypt_sensitive_fields(data_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """根据数据源类型，加密敏感字段（如 password, cookie, api_key）"""
    config_copy = config.copy()
    if data_type == "email":
        if "password" in config_copy:
            config_copy["encrypted_password"] = encrypt_password(config_copy.pop("password"))
        # 自动补全服务器配置（若使用预设服务商）
        provider = config_copy.get("provider")
        if provider and provider in PROVIDERS_MAP:
            provider_info = PROVIDERS_MAP[provider]
            config_copy["imap_server"] = provider_info["imap_server"]
            config_copy["imap_port"] = provider_info["imap_port"]
            config_copy["use_ssl"] = provider_info["use_ssl"]
    elif data_type in ["weibo", "xiaohongshu", "competitor"]:
        for field in ["cookie", "api_key"]:
            if field in config_copy and config_copy[field]:
                config_copy[f"encrypted_{field}"] = encrypt_password(config_copy.pop(field))
    return config_copy

# ---------- 路由 ----------
@router.get("/types")
async def get_data_source_types():
    """返回所有支持的数据源类型定义（用于前端动态表单）"""
    result = {}
    for key, defn in DATA_SOURCE_TYPES.items():
        result[key] = {
            "name": defn.name,
            "fields": [f.dict() for f in defn.fields]
        }
    return result

@router.post("", status_code=201)
async def create_data_source(
    data: DataSourceCreate,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建数据源，自动处理敏感字段加密"""
    if data.type not in DATA_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的数据源类型")

    # 可选：测试连接
    type_def = DATA_SOURCE_TYPES[data.type]
    if type_def.test_connection:
        try:
            success = await type_def.test_connection(data.config)
            if not success:
                raise HTTPException(status_code=400, detail="连接测试失败")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"连接测试失败: {str(e)}")

    # 加密敏感字段
    encrypted_config = _encrypt_sensitive_fields(data.type, data.config)
    data.config = encrypted_config

    repo = DataSourceRepository(db)
    created = await repo.create(current_user.id, data)
    return created

@router.put("/{source_id}")
async def update_data_source(
    source_id: int,
    data: DataSourceUpdate,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新数据源"""
    repo = DataSourceRepository(db)
    existing = await repo.get(source_id, current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 如果更新了类型，需检查支持性
    if data.type and data.type not in DATA_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的数据源类型")

    # 如果更新了 config，需要加密
    if data.config:
        encrypted_config = _encrypt_sensitive_fields(data.type or existing.type, data.config)
        data.config = encrypted_config

        # 可选：重新测试连接
        type_def = DATA_SOURCE_TYPES[data.type or existing.type]
        if type_def.test_connection:
            try:
                success = await type_def.test_connection(data.config)
                if not success:
                    raise HTTPException(status_code=400, detail="连接测试失败")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"连接测试失败: {str(e)}")

    updated = await repo.update(source_id, current_user.id, data)
    return updated

@router.get("")
async def list_data_sources(
    skip: int = 0,
    limit: int = 100,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """列出当前用户的所有数据源"""
    repo = DataSourceRepository(db)
    sources = await repo.list(current_user.id, skip, limit)
    return sources

@router.get("/{source_id}")
async def get_data_source(
    source_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个数据源详情"""
    repo = DataSourceRepository(db)
    source = await repo.get(source_id, current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return source

@router.delete("/{source_id}")
async def delete_data_source(
    source_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除数据源"""
    repo = DataSourceRepository(db)
    success = await repo.delete(source_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "已删除"}

@router.post("/test")
async def test_connection(
    req: TestConnectionRequest,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试数据源连接（不存储）"""
    if req.type not in DATA_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的数据源类型")

    # 对于邮箱类型，如果 config 中有 encrypted_password 且没有 password，则解密
    if req.type == "email" and "encrypted_password" in req.config and "password" not in req.config:
        from backend.utils.crypto import decrypt_password
        req.config["password"] = decrypt_password(req.config["encrypted_password"])

    type_def = DATA_SOURCE_TYPES[req.type]
    if type_def.test_connection:
        try:
            success = await type_def.test_connection(req.config)
            return {"success": success, "message": "连接成功" if success else "连接失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    else:
        return {"success": True, "message": "该类型不支持测试，已保存配置"}