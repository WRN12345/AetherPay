"""
FastAPI 应用入口
"""

import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.config import router as config_router
from app.api.v1.orders import router as orders_router
from app.api.v1.products import router as products_router
from app.core.config import get_settings
from app.database import engine
from app.services.chain import get_web3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="web3 链上支付与订单 API",
)

# 开发时由 Vite 代理、部署时由 nginx 转发 /api，前后端同源，无需 CORS

# 注册路由
app.include_router(config_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict:
    """健康检查：数据库与 RPC 连通性"""
    result: dict = {"app": settings.APP_NAME, "version": settings.APP_VERSION}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["database"] = "ok"
    except Exception as exc:
        result["database"] = f"error: {type(exc).__name__}"

    try:
        chain_id = get_web3().eth.chain_id
        result["rpc"] = "ok" if chain_id == settings.CHAIN_ID else f"chain_id mismatch: {chain_id}"
    except Exception as exc:
        result["rpc"] = f"error: {type(exc).__name__}"

    result["status"] = "ok" if result["database"] == "ok" and result["rpc"] == "ok" else "degraded"
    return result
