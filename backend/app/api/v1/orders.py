"""订单 API 端点；同步数据库访问，因此使用普通 def。所有接口都要求钱包登录，只能访问自己的订单"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_address
from app.core.config import get_settings
from app.database import get_db
from app.models import Order
from app.schemas.order import OrderCreate, OrderOut, TxHashSubmit
from app.services import orders as order_service
from app.services.rate_limit import order_create_limiter

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_owned_order_or_404(db: Session, order_id: uuid.UUID, address: str) -> Order:
    # 他人的订单也返回 404 而不是 403：不向调用者透露该订单是否存在
    order = order_service.get_owned_order(db, order_id, address)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderCreate,
    db: Session = Depends(get_db),
    address: str = Depends(get_current_address),
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=128),
) -> OrderOut:
    """
    创建订单，价格由服务端商品配置决定，订单归属当前登录账户
    请求头 Idempotency-Key 可选：重试时带上同一个键，返回的是第一次创建的订单
    """
    if not order_create_limiter.allow(address, get_settings().ORDER_CREATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="下单过于频繁，请稍后再试")
    try:
        order = order_service.create_order(db, body.product_id, idempotency_key, owner_address=address)
    except order_service.UnknownProductError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品不存在")
    except order_service.IdempotencyConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该幂等键已用于内容不同的请求")
    return order_service.to_order_out(order)


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), address: str = Depends(get_current_address)) -> list[OrderOut]:
    """当前账户最近的订单"""
    return [order_service.to_order_out(o) for o in order_service.list_orders(db, address)]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID, db: Session = Depends(get_db), address: str = Depends(get_current_address)
) -> OrderOut:
    """查询订单状态和付款信息"""
    return order_service.to_order_out(_get_owned_order_or_404(db, order_id, address))


@router.post("/{order_id}/tx-hash", response_model=OrderOut)
def submit_tx_hash(
    order_id: uuid.UUID,
    body: TxHashSubmit,
    db: Session = Depends(get_db),
    address: str = Depends(get_current_address),
) -> OrderOut:
    """记录前端提交的交易哈希；不做核验，不改变订单状态"""
    order = _get_owned_order_or_404(db, order_id, address)
    return order_service.to_order_out(order_service.record_submitted_tx(db, order, body.tx_hash))
