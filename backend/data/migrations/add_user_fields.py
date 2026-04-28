"""
数据库迁移脚本：为用户表添加company和phone字段
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.core.database import engine

async def migrate():
    print("开始数据库迁移...")
    
    async with engine.begin() as conn:
        try:
            # 检查company字段是否存在
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'company'
            """))
            company_exists = result.fetchone() is not None
            
            # 检查phone字段是否存在
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'phone'
            """))
            phone_exists = result.fetchone() is not None
            
            # 添加company字段（如果不存在）
            if not company_exists:
                print("添加company字段...")
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN company VARCHAR(200)
                """))
                print("✓ company字段添加成功")
            else:
                print("✓ company字段已存在")
            
            # 添加phone字段（如果不存在）
            if not phone_exists:
                print("添加phone字段...")
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN phone VARCHAR(20)
                """))
                print("✓ phone字段添加成功")
            else:
                print("✓ phone字段已存在")
            
            print("✅ 数据库迁移完成！")
            
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(migrate())