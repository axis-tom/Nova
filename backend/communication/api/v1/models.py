from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from backend.communication.model_clients.manager import ModelManager
from backend.communication.api.v1.auth import get_current_user
from backend.config.config import settings
from backend.communication.model_clients.ollama import ollama_client
from backend.communication.model_clients.openai import openai_client

router = APIRouter(prefix="/models", tags=["模型管理"])

# ========== 原有模型文件管理功能（保留） ==========
class FolderCreate(BaseModel):
    name: str
    parent: str = ""

class FolderRename(BaseModel):
    new_name: str

class ModelDownload(BaseModel):
    model_name: str
    folder: str = ""

@router.get("/folders")
async def list_folders(parent: str = "", user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    return manager.list_folders(parent)

@router.post("/folders")
async def create_folder(data: FolderCreate, user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    if manager.create_folder(data.name, data.parent):
        return {"success": True}
    raise HTTPException(status_code=400, detail="创建失败，可能已存在同名文件夹")

@router.put("/folders/{path:path}")
async def rename_folder(path: str, data: FolderRename, user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    if manager.rename_folder(path, data.new_name):
        return {"success": True}
    raise HTTPException(status_code=400, detail="重命名失败")

@router.delete("/folders/{path:path}")
async def delete_folder(path: str, user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    if manager.delete_folder(path):
        return {"success": True}
    raise HTTPException(status_code=400, detail="删除失败")

@router.get("/list")
async def list_models(folder: str = "", user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    return {
        "models": manager.list_models(folder),
        "folders": manager.list_folders(folder)
    }

@router.post("/download")
async def download_model(data: ModelDownload, user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    result = await manager.download_model(data.model_name, data.folder)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "下载失败"))

@router.delete("/{path:path}")
async def delete_model(path: str, user=Depends(get_current_user)):
    manager = ModelManager(user.id)
    if manager.delete_model(path):
        return {"success": True}
    raise HTTPException(status_code=400, detail="删除失败")

# ========== 新增：返回可用的AI模型列表（供前端选择） ==========
@router.get("/available", response_model=List[dict])
async def get_available_models(
    current_user = Depends(get_current_user),
):
    """获取当前可用的AI模型列表（用于对话界面）"""
    models = []
    # 从 Ollama 获取
    try:
        ollama_models = await ollama_client.list_models()
        for m in ollama_models:
            models.append({
                "id": m["name"],
                "name": m["name"],
                "provider": "ollama",
                "model_id": m["name"]
            })
    except Exception:
        pass
    # 从 OpenAI 配置中获取（如果配置了）
    if settings.OPENAI_API_KEY:
        models.append({
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "provider": "openai",
            "model_id": "gpt-3.5-turbo"
        })
    # 如果没有任何模型，返回默认模拟数据（便于前端测试）
    if not models:
        models = [
            {"id": "gpt35", "name": "GPT-3.5 Turbo", "provider": "mock", "model_id": "gpt35"},
            {"id": "llama3", "name": "Llama 3 70B", "provider": "mock", "model_id": "llama3"}
        ]
    return models
