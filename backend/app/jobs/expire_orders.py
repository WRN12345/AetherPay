"""
到期处理：把确定不会再有有效付款的待付款订单标记为 EXPIRED
用法（backend 目录）：python -m app.jobs.expire_orders --once

何时能确定"不会再有有效付款"：
付款有效的条件是所在区块时间早于 expires_at。只要扫描器已经处理完所有时间早于 expires_at 的区块，
之后才出现的付款都会被判为 LATE，订单就可以安全地标记为到期。
- 扫描器已追上最新区块：之后的新区块时间都不早于当前时间，截止时间取当前时间
- 扫描器落后于最新区块：还有已出块但未扫描的区块，截止时间只能取已扫描到的区块时间
即使判断过早，扫描器发现到期前的有效付款时仍会把 EXPIRED 改为 PAID，不会漏单
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.jobs.scan_payments import get_cursor
from app.models import Order
from app.models.order import STATUS_EXPIRED, STATUS_PENDING_PAYMENT
from app.services.chain import get_web3

logger = logging.getLogger(__name__)


def expiry_cutoff(db: Session, latest_block: int, now: datetime) -> datetime | None:
    """返回可以安全判定到期的截止时间；扫描器尚未运行时返回 None"""
    cursor = get_cursor(db)
    if cursor is None or cursor.last_scanned_block_time is None:
        return None
    if cursor.last_scanned_block >= latest_block:
        return now
    return cursor.last_scanned_block_time


def expire_orders(db: Session, latest_block: int, now: datetime | None = None) -> int:
    """标记到期订单，返回本次标记的数量"""
    cutoff = expiry_cutoff(db, latest_block, now or datetime.now(UTC))
    if cutoff is None:
        return 0

    result = db.execute(
        update(Order)
        .where(Order.status == STATUS_PENDING_PAYMENT, Order.expires_at <= cutoff)
        .values(status=STATUS_EXPIRED)
    )
    db.commit()
    if result.rowcount:
        logger.info("expire_orders expired=%d cutoff=%s", result.rowcount, cutoff.isoformat())
    return result.rowcount


def main() -> int:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="python -m app.jobs.expire_orders", description="标记到期订单")
    parser.add_argument("--once", action="store_true", required=True, help="执行一次后退出")
    parser.parse_args()

    with SessionLocal() as db:
        count = expire_orders(db, get_web3().eth.block_number)
    print(f"本次标记到期订单 {count} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
