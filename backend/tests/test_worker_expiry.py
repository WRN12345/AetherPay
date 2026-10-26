"""Worker 退避重试与订单到期处理测试"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.jobs import scan_payments
from app.jobs.expire_orders import expire_orders
from app.models import Order
from app.services import orders as order_service
from app.worker import backoff_delay
from tests.conftest import FakeChain, make_event

# ───────────────────────── 退避重试 ─────────────────────────


@pytest.mark.parametrize(
    ("failures", "expected"),
    [(0, 3), (1, 3), (2, 6), (3, 12), (4, 24), (5, 48), (6, 60), (20, 60)],
)
def test_backoff_doubles_up_to_maximum(failures: int, expected: int) -> None:
    assert backoff_delay(failures, base=3, maximum=60) == expected


# ───────────────────────── 到期处理 ─────────────────────────


def make_expired_order(db: Session, minutes_ago: int = 10) -> Order:
    order = order_service.create_order(db, "lesson17")
    order.expires_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    db.commit()
    return order


def test_no_expiry_before_scanner_runs(db_session: Session) -> None:
    # 扫描器还没运行过：无法确定是否存在未扫描的有效付款，不做处理
    order = make_expired_order(db_session)
    assert expire_orders(db_session, latest_block=10) == 0
    db_session.refresh(order)
    assert order.status == "PENDING_PAYMENT"


def test_expires_when_scanner_caught_up(db_session: Session, fake_chain: FakeChain) -> None:
    order = make_expired_order(db_session)
    scan_payments.scan_once(db_session)  # 扫描到最新区块 10

    assert expire_orders(db_session, latest_block=10) == 1
    db_session.refresh(order)
    assert order.status == "EXPIRED"


def test_unexpired_order_untouched(db_session: Session, fake_chain: FakeChain) -> None:
    order = order_service.create_order(db_session, "lesson17")  # 默认 30 分钟后到期
    scan_payments.scan_once(db_session)

    expire_orders(db_session, latest_block=10)
    db_session.refresh(order)
    assert order.status == "PENDING_PAYMENT"


def test_no_expiry_while_scanner_behind(db_session: Session, fake_chain: FakeChain) -> None:
    order = make_expired_order(db_session, minutes_ago=10)
    # 扫描器只处理到区块 10，且该区块时间早于订单到期时间
    fake_chain.block_times[10] = datetime.now(UTC) - timedelta(minutes=20)
    scan_payments.scan_once(db_session)

    # 链上已出到区块 15：区块 11 至 15 可能含有到期前的有效付款，不能判定到期
    assert expire_orders(db_session, latest_block=15) == 0
    db_session.refresh(order)
    assert order.status == "PENDING_PAYMENT"


def test_payment_before_expiry_found_after_expiry(db_session: Session, fake_chain: FakeChain) -> None:
    """到期前已付款，但扫描器晚于到期处理才发现：订单仍应变为 PAID"""
    order = make_expired_order(db_session, minutes_ago=10)
    scan_payments.scan_once(db_session)
    expire_orders(db_session, latest_block=10)
    db_session.refresh(order)
    assert order.status == "EXPIRED"

    # 模拟一笔区块时间早于到期时间的付款（例如扫描器宕机期间打包的区块）
    fake_chain.block_number = 11
    fake_chain.events.append(make_event(order.chain_order_id, block=11, block_time=order.expires_at - timedelta(minutes=1)))
    summary = scan_payments.scan_once(db_session)

    assert summary.results == {"ACCEPTED": 1}
    db_session.refresh(order)
    assert order.status == "PAID"


def test_payment_after_expiry_is_late(db_session: Session, fake_chain: FakeChain) -> None:
    order = make_expired_order(db_session, minutes_ago=10)
    fake_chain.events.append(make_event(order.chain_order_id, block=5, block_time=datetime.now(UTC)))

    summary = scan_payments.scan_once(db_session)
    expire_orders(db_session, latest_block=10)

    assert summary.results == {"LATE": 1}
    db_session.refresh(order)
    assert order.status == "EXPIRED"
