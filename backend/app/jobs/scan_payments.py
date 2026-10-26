"""
付款扫描器：读取已确认区块中的 OrderPaid 事件，记录付款并完成订单
这是唯一会把订单改为 PAID 的地方
用法（backend 目录）：python -m app.jobs.scan_payments --once
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import Order, Payment, ScanCursor
from app.models.order import STATUS_EXPIRED, STATUS_PAID, STATUS_PENDING_PAYMENT
from app.services.chain import get_web3
from app.services.payments import (
    OrderSnapshot,
    PaidEvent,
    PaymentResult,
    classify_payment,
    fetch_paid_events,
)

logger = logging.getLogger(__name__)


@dataclass
class ScanSummary:
    from_block: int
    to_block: int
    events: int = 0
    skipped: int = 0
    results: dict[str, int] = field(default_factory=dict)


def get_or_create_cursor(db: Session) -> ScanCursor:
    """读取并锁住当前合约的扫描游标，不存在时创建"""
    settings = get_settings()
    contract_address = settings.CONTRACT_ADDRESS.lower()
    cursor = db.scalar(
        select(ScanCursor)
        .where(ScanCursor.chain_id == settings.CHAIN_ID, ScanCursor.contract_address == contract_address)
        .with_for_update()
    )
    if cursor is None:
        # 游标记录"已处理完的最后一个区块"，从部署区块开始扫描，所以初始值为部署区块减 1
        cursor = ScanCursor(
            chain_id=settings.CHAIN_ID,
            contract_address=contract_address,
            last_scanned_block=settings.DEPLOYMENT_BLOCK - 1,
        )
        db.add(cursor)
        db.flush()
    return cursor


def record_payment(db: Session, event: PaidEvent) -> PaymentResult | None:
    """记录一个付款事件并按分类更新订单；事件已记录过时返回 None"""
    already = db.scalar(
        select(Payment.id).where(Payment.tx_hash == event.tx_hash, Payment.log_index == event.log_index)
    )
    if already is not None:
        return None

    # 锁住订单行，避免并发处理同一订单
    order = db.scalar(select(Order).where(Order.chain_order_id == event.chain_order_id).with_for_update())
    snapshot = None
    if order is not None:
        snapshot = OrderSnapshot(
            chain_order_id=order.chain_order_id,
            amount_wei=int(order.amount_wei),
            expires_at=order.expires_at,
            has_accepted_payment=order.paid_tx_hash is not None,
        )
    result = classify_payment(event, snapshot)

    db.add(
        Payment(
            order_id=order.id if order is not None else None,
            chain_order_id=event.chain_order_id,
            tx_hash=event.tx_hash,
            log_index=event.log_index,
            block_number=event.block_number,
            block_hash=event.block_hash,
            block_time=event.block_time,
            payer_address=event.payer_address,
            amount_wei=event.amount_wei,
            result=result.value,
        )
    )

    if result is PaymentResult.ACCEPTED:
        # 条件更新：只有待付款或已到期的订单才能改为已支付
        db.execute(
            update(Order)
            .where(Order.id == order.id, Order.status.in_([STATUS_PENDING_PAYMENT, STATUS_EXPIRED]))
            .values(
                status=STATUS_PAID,
                paid_tx_hash=event.tx_hash,
                paid_by_address=event.payer_address,
                paid_at=event.block_time,
            )
        )
        # 让同一批次后续事件看到最新状态（用于 DUPLICATE 判断）
        db.refresh(order)
    return result


def scan_once(db: Session) -> ScanSummary:
    """从游标扫描到当前确认区块；每批的付款记录与游标推进在同一事务中提交"""
    settings = get_settings()
    w3 = get_web3()

    cursor = get_or_create_cursor(db)
    # 只处理达到确认要求的区块
    safe_head = w3.eth.block_number - (settings.REQUIRED_CONFIRMATIONS - 1)
    summary = ScanSummary(from_block=cursor.last_scanned_block + 1, to_block=cursor.last_scanned_block)

    from_block = cursor.last_scanned_block + 1
    while from_block <= safe_head:
        to_block = min(from_block + settings.SCAN_BATCH_SIZE - 1, safe_head)
        events = fetch_paid_events(from_block, to_block)

        for event in events:
            result = record_payment(db, event)
            summary.events += 1
            if result is None:
                summary.skipped += 1
            else:
                summary.results[result.value] = summary.results.get(result.value, 0) + 1

        cursor.last_scanned_block = to_block
        cursor.last_scanned_block_time = datetime.fromtimestamp(w3.eth.get_block(to_block)["timestamp"], tz=UTC)
        db.commit()
        logger.info("已扫描区块 %d 至 %d，事件 %d 条", from_block, to_block, len(events))

        summary.to_block = to_block
        from_block = to_block + 1
        # commit 会释放行锁，下一批开始前重新锁住游标
        cursor = get_or_create_cursor(db)

    db.commit()
    return summary


def main() -> int:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="python -m app.jobs.scan_payments", description="扫描链上付款")
    parser.add_argument(
        "--once",
        action="store_true",
        required=True,
        help="扫描一次后退出；常驻循环在阶段 4 的 worker 中实现",
    )
    parser.parse_args()

    with SessionLocal() as db:
        s = scan_once(db)
    if s.to_block < s.from_block:
        print(f"没有新的已确认区块，已扫描到区块 {s.to_block}")
    else:
        print(
            f"扫描区块 {s.from_block} 至 {s.to_block}：事件 {s.events} 条，"
            f"已处理过跳过 {s.skipped} 条，分类结果 {s.results}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
