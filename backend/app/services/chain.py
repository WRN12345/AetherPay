"""链上读取：创建 web3 连接，后续阶段在此加入合约对象与事件读取"""

from functools import lru_cache

from web3 import Web3

from app.core.config import get_settings


@lru_cache
def get_web3() -> Web3:
    """获取全局 web3 连接"""
    settings = get_settings()
    return Web3(Web3.HTTPProvider(settings.RPC_URL, request_kwargs={"timeout": 10}))
