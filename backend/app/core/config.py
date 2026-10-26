"""
应用配置管理
使用 pydantic-settings 从环境变量 / 仓库根目录 .env 文件加载配置
后端只读链，不需要任何私钥
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# backend/app/core/config.py → 仓库根目录
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """应用配置"""

    # ── 应用 ──
    APP_NAME: str = "web3 Payment API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── PostgreSQL ──
    PGSQL_HOST: str = "127.0.0.1"
    PGSQL_PORT: int = 5432
    PGSQL_USER: str = "web3_app"
    PGSQL_PASSWORD: str = ""
    PGSQL_DATABASE: str = "web3_payment"

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
    # 连续失败时重试间隔翻倍，最长不超过该值
    WORKER_MAX_BACKOFF_SECONDS: int = 60
    # 扫描进度落后最新区块超过该值时，/health 报告 lagging
    HEALTH_MAX_SCAN_LAG_BLOCKS: int = 20

    # 无论从哪个目录启动都读取根目录 .env；.env 中与本项目无关的变量忽略
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def DATABASE_URL(self) -> str:
        """由 PGSQL_* 拼出 SQLAlchemy 连接串；密码中的特殊字符会被自动转义"""
        return URL.create(
            "postgresql+psycopg",
            username=self.PGSQL_USER,
            password=self.PGSQL_PASSWORD or None,
            host=self.PGSQL_HOST,
            port=self.PGSQL_PORT,
            database=self.PGSQL_DATABASE,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
