"""对话记录 ORM 模型（预留）"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatRecord(SQLModel, table=True):
    """对话记录表"""

    __tablename__ = "chat_records"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, description="会话ID")
    role: str = Field(description="角色: user / assistant")
    content: str = Field(description="消息内容")
    agent_name: str | None = Field(default=None, description="处理该消息的 Agent")
    tools_used: str | None = Field(default=None, description="使用的工具，逗号分隔")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
