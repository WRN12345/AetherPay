"""API 共用依赖"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import SESSION_COOKIE, get_session_address


def get_current_address(request: Request, db: Session = Depends(get_db)) -> str:
    """从 Cookie 中读取会话，返回已登录的钱包地址（小写）；未登录返回 401"""
    token = request.cookies.get(SESSION_COOKIE)
    address = get_session_address(db, token) if token else None
    if address is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先用钱包登录")
    return address
