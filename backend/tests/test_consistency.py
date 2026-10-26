"""
阶段 6 一致性测试：幂等键，以及绕过业务代码时数据库约束仍能兜底
数据库隔离方式见 conftest.py
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.jobs import scan_payments
from app.models import Order, Payment
from app.services import orders as order_service
from tests.conftest import FakeChain, make_event

# ───────────────────────── 幂等键 ─────────────────────────


def test_same_key_returns_same_order(api: TestClient) -> None:
    headers = {"Idempotency-Key": "key-1"}
    first = api.post("/api/v1/orders", json={"product_id": "lesson17"}, headers=headers)
    second = api.post("/api/v1/orders", json={"product_id": "lesson17"}, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["order_id"] == second.json()["order_id"]


def test_same_key_different_content_conflicts(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import products

    monkeypatch.setitem(products.PRODUCTS, "other", products.Product("other", "其他商品", 1))
    headers = {"Idempotency-Key": "key-2"}
    api.post("/api/v1/orders", json={"product_id": "lesson17"}, headers=headers)

    resp = api.post("/api/v1/orders", json={"product_id": "other"}, headers=headers)
    assert resp.status_code == 409


def test_without_key_creates_new_orders(api: TestClient) -> None:
    first = api.post("/api/v1/orders", json={"product_id": "lesson17"})
    second = api.post("/api/v1/orders", json={"product_id": "lesson17"})
    assert first.json()["order_id"] != second.json()["order_id"]


def test_concurrent_same_key_resolved_by_unique_constraint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """模拟两个相同键的请求同时到达：后到的请求查询时还看不到先到的订单，插入时撞上唯一约束"""
    # 必须带所有者：唯一约束是 (owner_address, idempotency_key)，PostgreSQL 视 NULL 为互不相同，
    # 所有者为空时约束不生效；通过 API 创建的订单都有所有者
    owner = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"
    first = order_service.create_order(db_session, "lesson17", "key-3", owner_address=owner)

    real_find = order_service.find_by_idempotency_key
    calls = {"n": 0}

    def stale_then_real(db: Session, owner: str | None, key: str):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(db, owner, key)

    monkeypatch.setattr(order_service, "find_by_idempotency_key", stale_then_real)
    second = order_service.create_order(db_session, "lesson17", "key-3", owner_address=owner)

    assert second.id == first.id
    assert len(db_session.scalars(select(Order).where(Order.idempotency_key == "key-3")).all()) == 1


# ─────────────────────── 数据库约束兜底 ───────────────────────


def _payment(order: Order, tx_suffix: str, result: str) -> Payment:
    return Payment(
        order_id=order.id,
        chain_order_id=order.chain_order_id,
        tx_hash="0x" + tx_suffix * 32,
        log_index=0,
        block_number=1,
        block_hash="0x" + "cc" * 32,
        block_time=datetime.now(UTC),
        payer_address="0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
        amount_wei=order.amount_wei,
        result=result,
    )


def test_db_rejects_second_accepted_payment(db_session: Session) -> None:
    """即使业务代码出错，数据库的部分唯一索引也不允许同一订单有两笔被接受的付款"""
    order = order_service.create_order(db_session, "lesson17")
    db_session.add(_payment(order, "a1", "ACCEPTED"))
    db_session.commit()

    db_session.add(_payment(order, "a2", "ACCEPTED"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 非 ACCEPTED 的记录不受限制
    db_session.add(_payment(order, "a3", "DUPLICATE"))
    db_session.commit()


def test_db_rejects_same_event_twice(db_session: Session) -> None:
    order = order_service.create_order(db_session, "lesson17")
    db_session.add(_payment(order, "b1", "DUPLICATE"))
    db_session.commit()

    db_session.add(_payment(order, "b1", "DUPLICATE"))  # 相同 tx_hash 与 log_index
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_rejects_invalid_status(db_session: Session) -> None:
    order = order_service.create_order(db_session, "lesson17")
    order.status = "PAYED"  # 拼写错误
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ─────────────────────── 两个入口同时处理 ───────────────────────


def test_tx_hash_submission_and_scan_do_not_double_credit(
    api: TestClient, db_session: Session, fake_chain: FakeChain
) -> None:
    """前端反复提交哈希、扫描器重复扫描，订单都只入账一次"""
    order_id = api.post("/api/v1/orders", json={"product_id": "lesson17"}).json()["order_id"]
    order = db_session.get(Order, order_id)
    event = make_event(order.chain_order_id)
    fake_chain.events.append(event)

    for _ in range(3):
        api.post(f"/api/v1/orders/{order_id}/tx-hash", json={"tx_hash": event.tx_hash})
    scan_payments.scan_once(db_session)
    scan_payments.scan_once(db_session)

    accepted = db_session.scalars(
        select(Payment).where(Payment.order_id == order.id, Payment.result == "ACCEPTED")
    ).all()
    assert len(accepted) == 1
    assert api.get(f"/api/v1/orders/{order_id}").json()["status"] == "PAID"
