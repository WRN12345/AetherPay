"""
应用配置管理
使用 pydantic-settings 从环境变量 / .env 文件加载配置
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # ── 应用 ──
    APP_NAME: str = "Multi-Agent API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Ollama ──
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5"

    # ── 数据库（预留） ──
    DATABASE_URL: str = "sqlite:///./data.db"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
