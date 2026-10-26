"""
付款核验
- verify_payment_tx：根据交易哈希核验单笔交易，供排查问题和前端展示进度
- fetch_paid_events：按区块范围读取 OrderPaid 事件，阶段 3 起由扫描器使用
- classify_payment：比对事件与订单，给出付款分类，不访问链也不访问数据库
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TransactionNotFound

from app.core.config import get_settings
from app.services.chain import get_contract, get_web3

# 事件签名的哈希，即日志的 topics[0]，用来识别"这是一条 OrderPaid 日志"
ORDER_PAID_TOPIC = Web3.keccak(text="OrderPaid(bytes32,address,uint256)")


@dataclass(frozen=True)
class PaidEvent:
    """一条已解码的 OrderPaid 事件；地址统一小写，编号和哈希为 0x 开头的十六进制"""

    chain_order_id: str
    payer_address: str
    amount_wei: int
    tx_hash: str
    log_index: int
    block_number: int
    block_hash: str
    block_time: datetime


class TxStatus(StrEnum):
    """单笔交易的核验结论"""

    NOT_FOUND = "NOT_FOUND"  # 节点上找不到这笔交易
    PENDING = "PENDING"  # 交易已发出但尚未打包
    REVERTED = "REVERTED"  # 已打包但执行失败
    NO_PAYMENT_EVENT = "NO_PAYMENT_EVENT"  # 执行成功，但没有本合约的 OrderPaid（如普通转账）
    CONFIRMING = "CONFIRMING"  # 找到付款事件，确认数未达要求
    CONFIRMED = "CONFIRMED"  # 找到付款事件，且确认数已达要求


@dataclass
class TxVerification:
    status: TxStatus
    reason: str
    confirmations: int = 0
    events: list[PaidEvent] = field(default_factory=list)


def _to_paid_event(decoded, block_time: datetime) -> PaidEvent:
    """把 web3.py 解码出的事件转换为 PaidEvent"""
    return PaidEvent(
        chain_order_id=Web3.to_hex(decoded.args.orderId),
        payer_address=decoded.args.payer.lower(),
        amount_wei=decoded.args.amount,
        tx_hash=Web3.to_hex(decoded.transactionHash),
        log_index=decoded.logIndex,
        block_number=decoded.blockNumber,
        block_hash=Web3.to_hex(decoded.blockHash),
        block_time=block_time,
    )


def _block_time(block_number: int) -> datetime:
    timestamp = get_web3().eth.get_block(block_number)["timestamp"]
    return datetime.fromtimestamp(timestamp, tz=UTC)


def verify_payment_tx(tx_hash: str) -> TxVerification:
    """核验一笔交易是否向本合约付了款"""
    w3 = get_web3()
    contract = get_contract()
    required = get_settings().REQUIRED_CONFIRMATIONS

    try:
        w3.eth.get_transaction(tx_hash)
    except TransactionNotFound:
        return TxVerification(TxStatus.NOT_FOUND, "节点上找不到这笔交易，哈希可能有误或交易未发出")

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return TxVerification(TxStatus.PENDING, "交易尚未被打包，稍后再查")

    if receipt["status"] != 1:
        return TxVerification(TxStatus.REVERTED, "交易执行失败已回滚，回滚交易不会产生事件")

    # 只认本合约发出的 OrderPaid：process_receipt 不检查日志来源地址，必须先自己按地址过滤，
    # 否则其他合约发出的同名事件也会被当成付款
    own_logs = [
        log
        for log in receipt["logs"]
        if log["address"].lower() == contract.address.lower()
        and log["topics"]
        and HexBytes(log["topics"][0]) == ORDER_PAID_TOPIC
    ]
    if not own_logs:
        return TxVerification(TxStatus.NO_PAYMENT_EVENT, "交易成功，但没有本合约发出的 OrderPaid 事件")

    block_time = _block_time(receipt["blockNumber"])
    events = [
        _to_paid_event(contract.events.OrderPaid().process_log(log), block_time) for log in own_logs
    ]

    confirmations = w3.eth.block_number - receipt["blockNumber"] + 1
    if confirmations < required:
        return TxVerification(
            TxStatus.CONFIRMING,
            f"已找到付款事件，确认数 {confirmations}/{required}",
            confirmations,
            events,
        )
    return TxVerification(
        TxStatus.CONFIRMED,
        f"已找到付款事件，确认数 {confirmations}/{required}",
        confirmations,
        events,
    )


def fetch_paid_events(from_block: int, to_block: int) -> list[PaidEvent]:
    """读取 [from_block, to_block] 区间内本合约发出的全部 OrderPaid 事件"""
    contract = get_contract()
    # get_logs 由节点按合约地址和事件签名过滤；回滚交易不产生日志，不会出现在结果中
    logs = contract.events.OrderPaid().get_logs(from_block=from_block, to_block=to_block)

    block_times: dict[int, datetime] = {}
    events: list[PaidEvent] = []
    for log in logs:
        if log.blockNumber not in block_times:
            block_times[log.blockNumber] = _block_time(log.blockNumber)
        events.append(_to_paid_event(log, block_times[log.blockNumber]))
    return events


# ───────────────────────── 付款分类 ─────────────────────────


class PaymentResult(StrEnum):
    """付款分类，对应实施方案 7.2 节"""

    ACCEPTED = "ACCEPTED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    LATE = "LATE"
    DUPLICATE = "DUPLICATE"
    UNKNOWN_ORDER = "UNKNOWN_ORDER"


@dataclass(frozen=True)
class OrderSnapshot:
    """分类所需的订单信息；阶段 3 由数据库中的订单转换而来"""

    chain_order_id: str
    amount_wei: int
    expires_at: datetime
    has_accepted_payment: bool


def classify_payment(event: PaidEvent, order: OrderSnapshot | None) -> PaymentResult:
    """按顺序判断一条付款事件属于哪一类"""
    if order is None:
        return PaymentResult.UNKNOWN_ORDER
    if event.amount_wei != order.amount_wei:
        return PaymentResult.AMOUNT_MISMATCH
    # 以付款所在区块的时间判断是否逾期，而不是以扫描到它的时间
    if event.block_time >= order.expires_at:
        return PaymentResult.LATE
    if order.has_accepted_payment:
        return PaymentResult.DUPLICATE
    return PaymentResult.ACCEPTED
