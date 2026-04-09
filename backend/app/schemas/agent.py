"""Agent 管理相关的 Pydantic Schema"""

from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    """Agent 信息"""

    name: str = Field(..., description="Agent 名称")
    description: str = Field(..., description="Agent 描述")
    tools: list[str] = Field(default_factory=list, description="Agent 可用工具列表")


class AgentListResponse(BaseModel):
    """Agent 列表响应"""

    agents: list[AgentInfo] = Field(default_factory=list, description="Agent 列表")
    total: int = Field(..., description="Agent 总数")
