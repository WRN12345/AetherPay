"""钱包签名登录 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_address
from app.core.config import get_settings
from app.database import get_db
from app.schemas.auth import ChallengeOut, ChallengeRequest, LoginRequest, MeOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/challenge", response_model=ChallengeOut)
def create_challenge(body: ChallengeRequest, db: Session = Depends(get_db)) -> ChallengeOut:
    """生成待签名的登录消息"""
    try:
        challenge = auth_service.create_challenge(db, body.address, body.chain_id)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ChallengeOut(nonce=challenge.nonce, message=challenge.message)


@router.post("/login", response_model=MeOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> MeOut:
    """验证签名，成功后通过 Cookie 下发会话令牌"""
    settings = get_settings()
    try:
        token, session = auth_service.login(db, body.nonce, body.signature)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    response.set_cookie(
        auth_service.SESSION_COOKIE,
        token,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,  # 网页脚本读不到 Cookie，即使页面被注入恶意脚本也偷不走令牌
        samesite="lax",  # 其他网站发起的跨站 POST 不携带 Cookie，防御 CSRF
        secure=settings.COOKIE_SECURE,
    )
    return MeOut(address=session.address)


@router.get("/me", response_model=MeOut)
def me(address: str = Depends(get_current_address)) -> MeOut:
    """查询当前登录的钱包地址"""
    return MeOut(address=address)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """退出登录：删除服务端会话并清除 Cookie"""
    token = request.cookies.get(auth_service.SESSION_COOKIE)
    if token:
        auth_service.logout(db, token)
    response.delete_cookie(auth_service.SESSION_COOKIE)
