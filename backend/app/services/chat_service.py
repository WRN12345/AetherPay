"""
对话业务逻辑层
负责编排 Agent 调用和会话管理
"""

import logging
import uuid

from app.agents.base import AgentResponse
from app.agents.coordinator import CoordinatorAgent
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class ChatService:
    """对话服务"""

    def __init__(self) -> None:
        self.coordinator = CoordinatorAgent()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """处理对话请求"""
        # 生成或使用已有的会话 ID
        conversation_id = request.conversation_id or str(uuid.uuid4())

        logger.info(
            "Chat request [conv=%s]: %s",
            conversation_id,
            request.message[:50],
        )

        # 委派给 Coordinator Agent
        agent_response: AgentResponse = await self.coordinator.run(
            message=request.message,
            conversation_id=conversation_id,
        )

        logger.info(
            "Agent response [agent=%s, tools=%s]",
            agent_response.agent_name,
            agent_response.tools_used,
        )

        return ChatResponse(
            message=agent_response.message,
            agent=agent_response.agent_name,
            conversation_id=conversation_id,
            tools_used=agent_response.tools_used,
        )

    def get_agents_info(self) -> list[dict]:
        """获取所有注册的 Agent 信息"""
        return self.coordinator.get_workers_info()
