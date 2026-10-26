"""付款分类测试：classify_payment 是纯函数，不需要链和数据库"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.payments import OrderSnapshot, PaidEvent, PaymentResult, classify_payment

ORDER_ID = "0x" + "aa" * 32
PRICE = 10**16  # 0.01 ETH
EXPIRES_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def make_event(amount_wei: int = PRICE, block_time: datetime = EXPIRES_AT - timedelta(minutes=5)) -> PaidEvent:
    return PaidEvent(
        chain_order_id=ORDER_ID,
        payer_address="0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
        amount_wei=amount_wei,
        tx_hash="0x" + "11" * 32,
        log_index=0,
        block_number=2,
        block_hash="0x" + "22" * 32,
        block_time=block_time,
    )


def make_order(has_accepted_payment: bool = False) -> OrderSnapshot:
    return OrderSnapshot(
        chain_order_id=ORDER_ID,
        amount_wei=PRICE,
        expires_at=EXPIRES_AT,
        has_accepted_payment=has_accepted_payment,
    )


def test_valid_payment_is_accepted() -> None:
    assert classify_payment(make_event(), make_order()) == PaymentResult.ACCEPTED


def test_unknown_order() -> None:
    assert classify_payment(make_event(), None) == PaymentResult.UNKNOWN_ORDER


@pytest.mark.parametrize("amount", [PRICE - 1, PRICE + 1, 1])
def test_wrong_amount(amount: int) -> None:
    assert classify_payment(make_event(amount_wei=amount), make_order()) == PaymentResult.AMOUNT_MISMATCH


def test_payment_at_expiry_is_late() -> None:
    # 区块时间等于到期时间也算逾期：规则是"早于" expires_at 才接受
    assert classify_payment(make_event(block_time=EXPIRES_AT), make_order()) == PaymentResult.LATE


def test_second_payment_is_duplicate() -> None:
    order = make_order(has_accepted_payment=True)
    assert classify_payment(make_event(), order) == PaymentResult.DUPLICATE


def test_amount_checked_before_duplicate() -> None:
    # 分类有先后顺序：金额不符优先于重复付款
    order = make_order(has_accepted_payment=True)
    assert classify_payment(make_event(amount_wei=1), order) == PaymentResult.AMOUNT_MISMATCH
