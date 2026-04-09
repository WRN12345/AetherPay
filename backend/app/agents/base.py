"""
Agent 基类
所有自定义 Agent 继承此类
"""

from abc import ABC, abstractmethod
from typing import Any

from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.core.config import get_settings


class AgentResponse(BaseModel):
    """Agent 执行结果"""

    agent_name: str
    message: str
    tools_used: list[str] = []
    success: bool = True
    error: str | None = None


class BaseAgent(ABC):
    """
    Agent 基类
    子类需实现:
      - name: Agent 名称
      - description: Agent 描述
      - run(): 执行逻辑
    """

    name: str = ""
    description: str = ""
    tools: list[Any] = []

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
        )

    @abstractmethod
    async def run(self, message: str, **kwargs) -> AgentResponse:
        """执行 Agent 逻辑"""
        ...

    def get_info(self) -> dict:
        """获取 Agent 信息"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": [t.name for t in self.tools] if self.tools else [],
        }
