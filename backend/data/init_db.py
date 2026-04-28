# backend/core/init_db.py
async def init_user_defaults(user_id: int):
    """为用户创建默认模型文件夹"""
    folder_repo = ModelFolderRepository()
    # 检查是否已有文件夹
    folders = await folder_repo.list(user_id)
    if not folders:
        await folder_repo.create(user_id, ModelFolderCreate(name="基础模型"))