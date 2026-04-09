"""
Coordinator Agent（协调 Agent）
负责分析用户意图，选择合适的专业 Agent 处理请求
"""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.agents.base import AgentResponse, BaseAgent
from app.agents.workers.calculator import CalculatorAgent
from app.agents.workers.search import SearchAgent
from app.agents.workers.weather import WeatherAgent
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """协调 Agent：分析意图并委派给专业 Agent"""

    name: str = "coordinator"
    description: str = "协调多个专业 Agent，根据用户意图选择最合适的 Agent 处理请求"

    def __init__(self) -> None:
        super().__init__()
        # 注册所有专业 Agent
        self._workers: dict[str, BaseAgent] = {
            "search_agent": SearchAgent(),
            "calculator_agent": CalculatorAgent(),
            "weather_agent": WeatherAgent(),
        }

    async def run(self, message: str, **kwargs) -> AgentResponse:
        """分析用户意图并委派给合适的 Agent"""
        # 1. 用 LLM 分析意图，选择合适的 Agent
        selected_agent = await self._route(message)

        if selected_agent == "none":
            # 没有匹配的 Agent，直接用 LLM 回答
            return await self._direct_answer(message)

        # 2. 委派给选中的 Agent
        agent = self._workers.get(selected_agent)
        if not agent:
            logger.warning("Agent %s not found, falling back to direct answer", selected_agent)
            return await self._direct_answer(message)

        logger.info("Routing to agent: %s", selected_agent)
        return await agent.run(message, **kwargs)

    async def _route(self, message: str) -> str:
        """使用 LLM 分析用户意图并选择 Agent"""
        agent_descriptions = "\n".join(
            f"- {name}: {agent.description}"
            for name, agent in self._workers.items()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个任务路由器。根据用户消息，选择最合适的 Agent 处理。\n"
                    "可选 Agent:\n{agent_descriptions}\n\n"
                    "如果没有合适的 Agent，回复 'none'。\n"
                    "只回复 Agent 名称或 'none'，不要其他内容。",
                ),
                ("human", "{message}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke(
            {
                "agent_descriptions": agent_descriptions,
                "message": message,
            }
        )

        selected = response.content.strip().lower()

        # 验证选择的 Agent 是否存在
        if selected in self._workers:
            return selected
        return "none"

    async def _direct_answer(self, message: str) -> AgentResponse:
        """直接使用 LLM 回答（无匹配 Agent 时）"""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个智能助手。用中文简洁地回答用户问题。",
                ),
                ("human", "{message}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke({"message": message})

        return AgentResponse(
            agent_name=self.name,
            message=response.content,
        )

    def get_workers_info(self) -> list[dict]:
        """获取所有注册的 Worker Agent 信息"""
        return [agent.get_info() for agent in self._workers.values()]
