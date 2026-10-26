"""scan_cursors 扫描游标表：记录扫描器已处理到哪个区块"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanCursor(Base):
    __tablename__ = "scan_cursors"
    __table_args__ = (UniqueConstraint("chain_id", "contract_address", name="uq_scan_cursors_chain_contract"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chain_id: Mapped[int] = mapped_column(BigInteger)
    contract_address: Mapped[str] = mapped_column(String(42))
    # 已处理完的最后一个区块；初始值为部署区块减 1
    last_scanned_block: Mapped[int] = mapped_column(BigInteger)
    # 该区块的时间，阶段 5 的到期处理据此判断
    last_scanned_block_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
