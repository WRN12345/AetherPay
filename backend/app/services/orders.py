"""订单业务：创建、查询、记录前端提交的交易哈希"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Order
from app.models.order import STATUS_PENDING_PAYMENT
from app.schemas.order import OrderOut
from app.services.products import get_product


class UnknownProductError(Exception):
    pass


class IdempotencyConflictError(Exception):
    """同一幂等键被用于内容不同的请求"""


def find_by_idempotency_key(db: Session, key: str) -> Order | None:
    return db.scalar(select(Order).where(Order.idempotency_key == key))


def _replay(existing: Order, product_id: str) -> Order:
    # 请求内容目前只有 product_id；以后请求增加字段时，这里也要一并比较
    if existing.product_id != product_id:
        raise IdempotencyConflictError(existing.idempotency_key)
    return existing


def create_order(db: Session, product_id: str, idempotency_key: str | None = None) -> Order:
    """
    创建订单。带幂等键时，相同键 + 相同内容返回同一个订单，相同键 + 不同内容抛出冲突
    用于用户连点、网络超时后重试等场景，避免生成多个订单
    """
    product = get_product(product_id)
    if product is None:
        raise UnknownProductError(product_id)

    if idempotency_key is not None:
        existing = find_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return _replay(existing, product_id)

    order = Order(
        # 链上订单编号：后端生成的随机 32 字节，不可预测，创建后不再改变
        chain_order_id="0x" + secrets.token_hex(32),
        product_id=product.id,
        amount_wei=product.price_wei,
        status=STATUS_PENDING_PAYMENT,
        idempotency_key=idempotency_key,
        expires_at=datetime.now(UTC) + timedelta(seconds=get_settings().ORDER_TTL_SECONDS),
    )
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        # 两个相同键的请求同时到达：上面的查询都没查到，后提交的一方撞上唯一约束
        db.rollback()
        existing = find_by_idempotency_key(db, idempotency_key) if idempotency_key else None
        if existing is None:
            raise
        return _replay(existing, product_id)
    db.refresh(order)
    return order


def get_order(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.get(Order, order_id)


def record_submitted_tx(db: Session, order: Order, tx_hash: str) -> Order:
    """只记录哈希，便于展示和排查；订单状态只由扫描器改变"""
    order.submitted_tx_hash = tx_hash.lower()
    db.commit()
    db.refresh(order)
    return order


def to_order_out(order: Order) -> OrderOut:
    settings = get_settings()
    return OrderOut(
        order_id=order.id,
        product_id=order.product_id,
        chain_order_id=order.chain_order_id,
        amount_wei=str(int(order.amount_wei)),
        chain_id=settings.CHAIN_ID,
        contract_address=settings.CONTRACT_ADDRESS,
        status=order.status,
        submitted_tx_hash=order.submitted_tx_hash,
        paid_tx_hash=order.paid_tx_hash,
        paid_by_address=order.paid_by_address,
        paid_at=order.paid_at,
        expires_at=order.expires_at,
    )
