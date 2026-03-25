from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/market", tags=["场景商店"])

class MarketItem(BaseModel):
    id: str
    name: str
    description: str
    category: str   # ecommerce, saas, agency, etc.
    icon: str
    is_free: bool = True
    price: float = 0.0

# 模拟场景数据
market_items = [
    MarketItem(
        id="ecom-basic",
        name="电商基础版",
        description="为电商创业者定制的数据监控与简报模板",
        category="ecommerce",
        icon="shopping_cart",
        is_free=True
    ),
    MarketItem(
        id="agency-pro",
        name="代理公司专业版",
        description="多客户管理、竞品分析高级功能",
        category="agency",
        icon="business",
        is_free=False,
        price=49.0
    )
]

@router.get("/", response_model=List[MarketItem])
async def list_market_items():
    return market_items

@router.get("/{item_id}", response_model=MarketItem)
async def get_market_item(item_id: str):
    for item in market_items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

@router.post("/{item_id}/install")
async def install_item(item_id: str, user_id: int = 1):
    """安装场景（模拟）"""
    # 实际会复制场景配置到用户环境
    return {"message": f"Item {item_id} installed for user {user_id}"}