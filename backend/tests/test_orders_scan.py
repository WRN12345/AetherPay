"""
订单接口与付款扫描的集成测试
数据库隔离方式和假链见 conftest.py
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs import scan_payments
from app.models import Payment, ScanCursor
from app.services import orders as order_service
from tests.conftest import PRICE, FakeChain, make_event

# ───────────────────────── 订单接口 ─────────────────────────


def test_create_and_get_order(api: TestClient) -> None:
    created = api.post("/api/v1/orders", json={"product_id": "lesson17"})
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "PENDING_PAYMENT"
    assert body["amount_wei"] == str(PRICE)  # 价格来自服务端，且以字符串返回
    assert len(body["chain_order_id"]) == 66

    fetched = api.get(f"/api/v1/orders/{body['order_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["chain_order_id"] == body["chain_order_id"]


def test_client_cannot_set_price(api: TestClient) -> None:
    # 请求中多余的价格字段被忽略
    created = api.post("/api/v1/orders", json={"product_id": "lesson17", "amount_wei": "1"})
    assert created.json()["amount_wei"] == str(PRICE)


def test_unknown_product(api: TestClient) -> None:
    assert api.post("/api/v1/orders", json={"product_id": "nope"}).status_code == 400


def test_missing_order(api: TestClient) -> None:
    assert api.get("/api/v1/orders/00000000-0000-0000-0000-000000000000").status_code == 404


def test_submit_tx_hash_does_not_mark_paid(api: TestClient) -> None:
    order_id = api.post("/api/v1/orders", json={"product_id": "lesson17"}).json()["order_id"]
    tx_hash = "0x" + "ab" * 32

    resp = api.post(f"/api/v1/orders/{order_id}/tx-hash", json={"tx_hash": tx_hash})
    assert resp.status_code == 200
    assert resp.json()["submitted_tx_hash"] == tx_hash
    assert resp.json()["status"] == "PENDING_PAYMENT"


def test_invalid_tx_hash_rejected(api: TestClient) -> None:
    order_id = api.post("/api/v1/orders", json={"product_id": "lesson17"}).json()["order_id"]
    assert api.post(f"/api/v1/orders/{order_id}/tx-hash", json={"tx_hash": "0x123"}).status_code == 422


# ───────────────────────── 付款扫描 ─────────────────────────


def test_scan_marks_order_paid(db_session: Session, fake_chain: FakeChain) -> None:
    order = order_service.create_order(db_session, "lesson17")
    fake_chain.events.append(make_event(order.chain_order_id))

    summary = scan_payments.scan_once(db_session)

    db_session.refresh(order)
    assert summary.results == {"ACCEPTED": 1}
    assert order.status == "PAID"
    assert order.paid_tx_hash == fake_chain.events[0].tx_hash


def test_scan_classifies_abnormal_payments(db_session: Session, fake_chain: FakeChain) -> None:
    order = order_service.create_order(db_session, "lesson17")
    fake_chain.events.extend(
        [
            make_event(order.chain_order_id, block=2),  # 正常付款
            make_event(order.chain_order_id, block=3),  # 再付一次
            make_event(order.chain_order_id, amount_wei=1, block=4),  # 金额不符
            make_event("0x" + "ee" * 32, block=5),  # 不存在的订单
        ]
    )

    summary = scan_payments.scan_once(db_session)

    assert summary.results == {"ACCEPTED": 1, "DUPLICATE": 1, "AMOUNT_MISMATCH": 1, "UNKNOWN_ORDER": 1}
    db_session.refresh(order)
    assert order.status == "PAID"
    assert order.paid_tx_hash == fake_chain.events[0].tx_hash  # 后续付款不会覆盖已接受的付款


def test_rescan_does_not_duplicate(db_session: Session, fake_chain: FakeChain) -> None:
    order = order_service.create_order(db_session, "lesson17")
    fake_chain.events.append(make_event(order.chain_order_id))
    scan_payments.scan_once(db_session)

    # 模拟游标回退（比如 Worker 在提交前崩溃后重扫）
    cursor = db_session.scalar(select(ScanCursor))
    cursor.last_scanned_block = 0
    db_session.commit()

    summary = scan_payments.scan_once(db_session)

    assert summary.skipped == 1
    payments = db_session.scalars(select(Payment).where(Payment.order_id == order.id)).all()
    assert len(payments) == 1


def test_cursor_advances_to_safe_head(db_session: Session, fake_chain: FakeChain) -> None:
    scan_payments.scan_once(db_session)
    cursor = db_session.scalar(select(ScanCursor))
    assert cursor.last_scanned_block == 10  # 本地确认数为 1，扫描到最新区块

    # 没有新区块时再扫描，不做任何事
    summary = scan_payments.scan_once(db_session)
    assert summary.to_block < summary.from_block
