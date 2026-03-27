import os
import shutil
import json
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend.core.config import settings

class ModelManager:
    """模型文件管理器（支持文件夹、下载、删除）"""
    
    def __init__(self, user_id: int):
        # 每个用户独立的模型目录
        self.base_dir = Path(settings.MODEL_STORAGE_PATH) / f"user_{user_id}"
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def list_models(self, folder_path: str = "") -> List[Dict[str, Any]]:
        """列出指定文件夹下的模型（.bin/.gguf/.safetensors 等）"""
        target = self.base_dir / folder_path if folder_path else self.base_dir
        if not target.exists():
            return []
        models = []
        for item in target.iterdir():
            if item.is_file() and item.suffix in ['.bin', '.gguf', '.safetensors', '.pt']:
                models.append({
                    "name": item.name,
                    "path": str(item.relative_to(self.base_dir)),
                    "size_mb": round(item.stat().st_size / (1024 * 1024), 2),
                    "type": "model"
                })
        return models
    
    def list_folders(self, folder_path: str = "") -> List[Dict[str, Any]]:
        """列出子文件夹"""
        target = self.base_dir / folder_path if folder_path else self.base_dir
        if not target.exists():
            return []
        folders = []
        for item in target.iterdir():
            if item.is_dir():
                folders.append({
                    "name": item.name,
                    "path": str(item.relative_to(self.base_dir)),
                })
        return folders
    
    def create_folder(self, folder_name: str, parent_path: str = "") -> bool:
        """新建文件夹"""
        try:
            parent = self.base_dir / parent_path if parent_path else self.base_dir
            new_dir = parent / folder_name
            new_dir.mkdir(parents=True, exist_ok=False)
            return True
        except Exception as e:
            return False
    
    def rename_folder(self, old_path: str, new_name: str) -> bool:
        """重命名文件夹"""
        try:
            old_dir = self.base_dir / old_path
            new_dir = old_dir.parent / new_name
            old_dir.rename(new_dir)
            return True
        except Exception:
            return False
    
    def delete_folder(self, folder_path: str) -> bool:
        """删除文件夹（非空需递归）"""
        try:
            target = self.base_dir / folder_path
            if target.is_dir():
                shutil.rmtree(target)
                return True
            return False
        except Exception:
            return False
    
    def delete_model(self, model_path: str) -> bool:
        """删除模型文件"""
        try:
            target = self.base_dir / model_path
            if target.is_file():
                target.unlink()
                return True
            return False
        except Exception:
            return False
    
    async def download_model(self, model_name: str, folder_path: str = "") -> Dict[str, Any]:
        """模拟下载模型（实际可对接 HuggingFace 或内部 CDN）"""
        # 这里预设模型列表，实际可从配置文件读取
        preset_models = {
            "qwen2.5-3b-instruct": {
                "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
                "size_mb": 2100
            },
            "llama3-8b-instruct": {
                "url": "https://huggingface.co/meta-llama/Llama-3-8B-Instruct-GGUF/resolve/main/llama3-8b-instruct-q4_k_m.gguf",
                "size_mb": 4400
            }
        }
        if model_name not in preset_models:
            return {"success": False, "error": "Unknown model"}
        
        info = preset_models[model_name]
        target_dir = self.base_dir / folder_path if folder_path else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{model_name}.gguf"
        filepath = target_dir / filename
        
        # 模拟异步下载（实际使用 aiohttp）
        # await self._download_file(info["url"], filepath)
        await asyncio.sleep(2)  # 模拟耗时
        return {"success": True, "path": str(filepath.relative_to(self.base_dir)), "name": filename}