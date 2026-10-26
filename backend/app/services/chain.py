"""链上读取：web3 连接、合约对象与部署检查"""

import json
from functools import lru_cache
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from app.core.config import get_settings

# 由 scripts/export_abi.py 从 Foundry 编译产物导出
ABI_PATH = Path(__file__).resolve().parents[2] / "abi" / "Payment.json"


@lru_cache
def get_web3() -> Web3:
    """获取全局 web3 连接"""
    settings = get_settings()
    return Web3(Web3.HTTPProvider(settings.RPC_URL, request_kwargs={"timeout": 10}))


@lru_cache
def get_contract() -> Contract:
    """获取 Payment 合约对象：地址来自配置，接口来自 ABI"""
    settings = get_settings()
    if not settings.CONTRACT_ADDRESS:
        raise RuntimeError("未配置 CONTRACT_ADDRESS，请先部署合约并填写 .env")
    abi = json.loads(ABI_PATH.read_text(encoding="utf-8"))
    return get_web3().eth.contract(
        address=Web3.to_checksum_address(settings.CONTRACT_ADDRESS),
        abi=abi,
    )


def check_deployment() -> list[str]:
    """检查链 ID 与合约部署情况，返回问题列表；为空表示一切正常"""
    settings = get_settings()
    w3 = get_web3()
    problems: list[str] = []

    chain_id = w3.eth.chain_id
    if chain_id != settings.CHAIN_ID:
        problems.append(f"链 ID 不一致：节点为 {chain_id}，配置为 {settings.CHAIN_ID}")

    if not settings.CONTRACT_ADDRESS:
        problems.append("未配置 CONTRACT_ADDRESS")
    elif not w3.eth.get_code(Web3.to_checksum_address(settings.CONTRACT_ADDRESS)):
        # 地址上没有代码：合约未部署，或 Anvil 重启后链已被重置
        problems.append(f"地址 {settings.CONTRACT_ADDRESS} 上没有合约代码")

    return problems
