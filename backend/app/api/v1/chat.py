"""对话 API 端点"""

from fastapi import APIRouter, Depends

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service() -> ChatService:
    """获取 ChatService 实例"""
    return ChatService()


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """发送消息，由 Multi-Agent 系统处理并返回回复"""
    return await service.chat(request)
