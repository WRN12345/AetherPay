"""
FastAPI 应用入口
"""

import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.orders import router as orders_router
from app.api.v1.products import router as products_router
from app.core.config import get_settings
from app.database import SessionLocal, engine
from app.jobs.scan_payments import get_cursor, scan_head
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict:
    """健康检查：数据库、RPC 连通性，以及扫描进度落后多少区块"""
    result: dict = {"app": settings.APP_NAME, "version": settings.APP_VERSION}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["database"] = "ok"
    except Exception as exc:
        result["database"] = f"error: {type(exc).__name__}"

    latest_block: int | None = None
    head: int | None = None
    try:
        w3 = get_web3()
        chain_id = w3.eth.chain_id
        latest_block = w3.eth.block_number
        head = scan_head(w3)
        result["rpc"] = "ok" if chain_id == settings.CHAIN_ID else f"chain_id mismatch: {chain_id}"
    except Exception as exc:
        result["rpc"] = f"error: {type(exc).__name__}"

    if result["database"] == "ok":
        result["scanner"] = _scanner_status(latest_block, head)
    else:
        result["scanner"] = {"status": "unknown"}

    healthy = result["database"] == "ok" and result["rpc"] == "ok" and result["scanner"]["status"] == "ok"
    result["status"] = "ok" if healthy else "degraded"
    return result


def _scanner_status(latest_block: int | None, head: int | None) -> dict:
    """
    扫描进度：与扫描上限比较，而不是与最新区块比较
    使用 finalized 时，扫描上限本身就落后最新区块几十个区块，这是正常的；
    Worker 停止或卡住时，落后扫描上限的区块数会持续增大
    """
    with SessionLocal() as db:
        cursor = get_cursor(db)
    if cursor is None:
        return {"status": "not_started"}
    status: dict = {"last_scanned_block": cursor.last_scanned_block, "block_tag": settings.SCAN_BLOCK_TAG}
    if latest_block is None or head is None:
        status["status"] = "unknown"
        return status
    lag = head - cursor.last_scanned_block
    status["latest_block"] = latest_block
    status["scan_head"] = head
    status["lag_blocks"] = lag
    if latest_block < cursor.last_scanned_block:
        # 链上区块比已扫描的还少：本地 Anvil 被重启后链已重置，数据库仍停留在旧链
        status["status"] = "chain_reset"
        status["hint"] = "链上最新区块低于扫描进度，链可能已被重置；需重新部署合约并清空数据库"
    else:
        status["status"] = "ok" if lag <= settings.HEALTH_MAX_SCAN_LAG_BLOCKS else "lagging"
    return status
