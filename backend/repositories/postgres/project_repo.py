from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from backend.models.db import Project
from backend.models.project import ProjectInDB, ProjectOut

class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user(self, user_id: int) -> List[ProjectOut]:
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        return [ProjectOut.model_validate(p, from_attributes=True) for p in projects]

    async def get_by_id(self, project_id: int) -> Optional[ProjectOut]:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return ProjectOut.model_validate(project, from_attributes=True)
        return None

    async def create(self, user_id: int, name: str) -> ProjectOut:
        project = Project(user_id=user_id, name=name)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return ProjectOut.model_validate(project, from_attributes=True)

    async def update(self, project_id: int, data: Dict[str, Any]) -> Optional[ProjectOut]:
        if not data:
            return await self.get_by_id(project_id)
        stmt = update(Project).where(Project.id == project_id).values(**data).returning(Project)
        result = await self.db.execute(stmt)
        await self.db.commit()
        project = result.scalar_one_or_none()
        if project:
            return ProjectOut.model_validate(project, from_attributes=True)
        return None

    async def delete(self, project_id: int) -> bool:
        stmt = delete(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0