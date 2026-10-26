"""
链上调试命令行（在 backend 目录运行）
  python -m app.cli check                     检查数据库、节点和合约部署
  python -m app.cli verify <交易哈希>          核验一笔交易是否为有效付款
  python -m app.cli events [--from N] [--to N] 列出区块范围内的 OrderPaid 事件
"""

import argparse
import sys

from sqlalchemy import text
from web3 import Web3

from app.core.config import get_settings
from app.database import engine
from app.services.chain import check_deployment, get_web3
from app.services.payments import fetch_paid_events, verify_payment_tx

# Anvil 默认账户 (0) 和 (1)，仅用于本地显示余额
ANVIL_ACCOUNTS = {
    "(0) 部署者": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "(1) 测试用户": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
}


def cmd_check(_: argparse.Namespace) -> int:
    settings = get_settings()
    w3 = get_web3()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"数据库    ok  {settings.PGSQL_HOST}:{settings.PGSQL_PORT}/{settings.PGSQL_DATABASE}")
    except Exception as exc:
        print(f"数据库    失败  {type(exc).__name__}: {exc}")

    print(f"节点      {settings.RPC_URL}  链 ID {w3.eth.chain_id}  最新区块 {w3.eth.block_number}")
    for label, address in ANVIL_ACCOUNTS.items():
        print(f"余额      {label} {address}  {Web3.from_wei(w3.eth.get_balance(address), 'ether')} ETH")

    problems = check_deployment()
    if problems:
        for p in problems:
            print(f"合约      问题  {p}")
        return 1

    contract_address = Web3.to_checksum_address(settings.CONTRACT_ADDRESS)
    balance = Web3.from_wei(w3.eth.get_balance(contract_address), "ether")
    print(f"合约      ok  {contract_address}  余额 {balance} ETH  部署区块 {settings.DEPLOYMENT_BLOCK}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    result = verify_payment_tx(args.tx_hash)
    print(f"结论      {result.status}")
    print(f"原因      {result.reason}")
    for e in result.events:
        print(f"订单编号  {e.chain_order_id}")
        print(f"付款人    {e.payer_address}")
        print(f"金额      {e.amount_wei} Wei（{Web3.from_wei(e.amount_wei, 'ether')} ETH）")
        print(f"区块      {e.block_number}  {e.block_hash}  {e.block_time.isoformat()}")
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    w3 = get_web3()
    from_block = args.from_block if args.from_block is not None else get_settings().DEPLOYMENT_BLOCK
    to_block = args.to_block if args.to_block is not None else w3.eth.block_number

    events = fetch_paid_events(from_block, to_block)
    print(f"区块 {from_block} 至 {to_block} 共 {len(events)} 条 OrderPaid 事件")
    for e in events:
        print(
            f"区块 {e.block_number}  日志 {e.log_index}  订单 {e.chain_order_id}  "
            f"付款人 {e.payer_address}  金额 {Web3.from_wei(e.amount_wei, 'ether')} ETH  交易 {e.tx_hash}"
        )
    return 0


def main() -> int:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="python -m app.cli", description="链上调试命令")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="检查数据库、节点和合约部署").set_defaults(func=cmd_check)

    p_verify = sub.add_parser("verify", help="核验一笔交易")
    p_verify.add_argument("tx_hash")
    p_verify.set_defaults(func=cmd_verify)

    p_events = sub.add_parser("events", help="列出 OrderPaid 事件")
    p_events.add_argument("--from", dest="from_block", type=int)
    p_events.add_argument("--to", dest="to_block", type=int)
    p_events.set_defaults(func=cmd_events)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
