"""Agent 管理 API 端点"""

from fastapi import APIRouter, Depends

from app.schemas.agent import AgentInfo, AgentListResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/agents", tags=["agents"])


def get_chat_service() -> ChatService:
    """获取 ChatService 实例"""
    return ChatService()


@router.get("", response_model=AgentListResponse)
async def list_agents(
    service: ChatService = Depends(get_chat_service),
) -> AgentListResponse:
    """获取所有已注册的 Agent 列表"""
    agents_info = service.get_agents_info()
    agents = [AgentInfo(**info) for info in agents_info]
    return AgentListResponse(agents=agents, total=len(agents))
