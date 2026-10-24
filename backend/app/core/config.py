"""
应用配置管理
使用 pydantic-settings 从环境变量 / .env 文件加载配置
后端只读链，不需要任何私钥
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # ── 应用 ──
    APP_NAME: str = "web3 Payment API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── 数据库 ──
    DATABASE_URL: str = "postgresql+psycopg://web3_app:change_me@127.0.0.1:5432/web3_payment"

    # ── 链与合约 ──
    RPC_URL: str = "http://127.0.0.1:8545"
    CHAIN_ID: int = 31337
    CONTRACT_ADDRESS: str = ""
    DEPLOYMENT_BLOCK: int = 0

    # ── 业务与扫描参数 ──
    REQUIRED_CONFIRMATIONS: int = 1
    ORDER_TTL_SECONDS: int = 1800
    SCAN_BATCH_SIZE: int = 500
    WORKER_POLL_SECONDS: int = 3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
