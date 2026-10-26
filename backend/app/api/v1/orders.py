"""订单 API 端点；同步数据库访问，因此使用普通 def"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order
from app.schemas.order import OrderCreate, OrderOut, TxHashSubmit
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_order_or_404(db: Session, order_id: uuid.UUID) -> Order:
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(body: OrderCreate, db: Session = Depends(get_db)) -> OrderOut:
    """创建订单，价格由服务端商品配置决定"""
    try:
        order = order_service.create_order(db, body.product_id)
    except order_service.UnknownProductError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品不存在")
    return order_service.to_order_out(order)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)) -> OrderOut:
    """查询订单状态和付款信息"""
    return order_service.to_order_out(_get_order_or_404(db, order_id))


@router.post("/{order_id}/tx-hash", response_model=OrderOut)
def submit_tx_hash(order_id: uuid.UUID, body: TxHashSubmit, db: Session = Depends(get_db)) -> OrderOut:
    """记录前端提交的交易哈希；不做核验，不改变订单状态"""
    order = _get_order_or_404(db, order_id)
    return order_service.to_order_out(order_service.record_submitted_tx(db, order, body.tx_hash))
