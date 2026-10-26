"""payments 链上付款记录表：扫描器发现的每一个 OrderPaid 事件都记录一行"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.services.payments import PaymentResult

PAYMENT_RESULTS = tuple(r.value for r in PaymentResult)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # 一个事件由交易哈希 + 日志序号唯一确定；重复扫描同一区块时插入冲突即跳过
        UniqueConstraint("tx_hash", "log_index", name="uq_payments_tx_log"),
        # 每个订单最多一笔被接受的付款
        Index(
            "uq_payments_accepted_order",
            "order_id",
            unique=True,
            postgresql_where=text("result = 'ACCEPTED'"),
        ),
        CheckConstraint(f"result IN {PAYMENT_RESULTS}", name="ck_payments_result"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 找不到对应订单时为空（UNKNOWN_ORDER）
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    chain_order_id: Mapped[str] = mapped_column(String(66), index=True)
    tx_hash: Mapped[str] = mapped_column(String(66))
    log_index: Mapped[int] = mapped_column(Integer)
    block_number: Mapped[int] = mapped_column(BigInteger)
    block_hash: Mapped[str] = mapped_column(String(66))
    block_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payer_address: Mapped[str] = mapped_column(String(42))
    amount_wei: Mapped[Decimal] = mapped_column(Numeric(78, 0))
    result: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
