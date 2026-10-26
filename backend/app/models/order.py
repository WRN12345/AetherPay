"""orders 订单表"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 订单状态：只有扫描器能写入 PAID；EXPIRED 在发现到期前的有效付款时仍可转为 PAID
STATUS_PENDING_PAYMENT = "PENDING_PAYMENT"
STATUS_PAID = "PAID"
STATUS_EXPIRED = "EXPIRED"
ORDER_STATUSES = (STATUS_PENDING_PAYMENT, STATUS_PAID, STATUS_EXPIRED)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_orders_status"),
        CheckConstraint("amount_wei > 0", name="ck_orders_amount_positive"),
        Index("ix_orders_status_expires_at", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 0x 开头的 32 字节十六进制，小写；用户调用 pay 时传入
    chain_order_id: Mapped[str] = mapped_column(String(66), unique=True)
    product_id: Mapped[str] = mapped_column(String(64))
    # NUMERIC(78,0) 能容纳 uint256；SQLAlchemy 返回 Decimal，业务代码中用 int() 转换
    amount_wei: Mapped[Decimal] = mapped_column(Numeric(78, 0))
    status: Mapped[str] = mapped_column(String(32), default=STATUS_PENDING_PAYMENT)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)

    # 前端提交的最近一个交易哈希，只用于展示和排查，不影响状态
    submitted_tx_hash: Mapped[str | None] = mapped_column(String(66))
    # 以下由扫描器在接受付款时写入
    paid_tx_hash: Mapped[str | None] = mapped_column(String(66))
    paid_by_address: Mapped[str | None] = mapped_column(String(42))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
