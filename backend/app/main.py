"""
FastAPI 应用入口
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agent import router as agent_router
from app.api.v1.chat import router as chat_router
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-Agent API with LangChain + Ollama",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
