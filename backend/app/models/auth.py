"""登录相关表：签名挑战与服务端会话"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthChallenge(Base):
    """一次登录请求：服务端生成待签名的消息，签名验证通过后标记为已使用，防止重放"""

    __tablename__ = "auth_challenges"

    # 一次性随机数，同时写在待签名消息里
    nonce: Mapped[str] = mapped_column(String(32), primary_key=True)
    address: Mapped[str] = mapped_column(String(42))
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    """登录会话：浏览器 Cookie 中保存随机令牌，数据库只保存令牌的哈希"""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 数据库泄露时，攻击者拿到的只是哈希，无法伪造 Cookie
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(String(42), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
