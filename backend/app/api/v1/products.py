"""商品 API 端点"""

from fastapi import APIRouter

from app.schemas.order import ProductOut
from app.services.products import PRODUCTS

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products() -> list[ProductOut]:
    """返回商品与展示价格"""
    return [ProductOut(product_id=p.id, name=p.name, price_wei=str(p.price_wei)) for p in PRODUCTS.values()]
