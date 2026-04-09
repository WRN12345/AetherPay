"""对话相关的 Pydantic Schema"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., min_length=1, description="用户消息")
    conversation_id: str | None = Field(None, description="会话ID，为空则新建会话")


class ChatResponse(BaseModel):
    """对话响应"""

    message: str = Field(..., description="Agent 回复")
    agent: str = Field(..., description="处理该请求的 Agent 名称")
    conversation_id: str = Field(..., description="会话ID")
    tools_used: list[str] = Field(default_factory=list, description="使用的工具列表")
