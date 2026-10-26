"""
钱包签名登录（Sign-In with Ethereum，EIP-4361）

流程：
1. create_challenge：服务端为某个地址生成一条标准格式的登录消息，含一次性 nonce 和有效期，保存在数据库
2. 前端请钱包对这条消息签名（personal_sign），签名不发交易、不花 Gas
3. login：服务端用签名反推出签名者地址，与消息中的地址比对；一致则说明对方持有该地址的私钥，创建会话

消息由服务端生成并保存，验证时直接使用保存的原文，不需要解析前端提交的消息，也就无法被篡改
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from web3 import Web3

from app.core.config import get_settings
from app.models import AuthChallenge, AuthSession

SESSION_COOKIE = "session"
STATEMENT = "登录 web3 课程资料商店。签名不会发起交易，也不会产生任何费用。"


class AuthError(Exception):
    """登录失败，消息可直接展示给用户"""


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_siwe_message(address: str, chain_id: int, nonce: str, issued_at: datetime, expires_at: datetime) -> str:
    """按 EIP-4361 格式生成登录消息；MetaMask 识别该格式，会核对消息中的域名与当前网页是否一致"""
    settings = get_settings()
    return (
        f"{settings.APP_DOMAIN} wants you to sign in with your Ethereum account:\n"
        f"{address}\n"
        f"\n"
        f"{STATEMENT}\n"
        f"\n"
        f"URI: {settings.APP_URI}\n"
        f"Version: 1\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {_fmt(issued_at)}\n"
        f"Expiration Time: {_fmt(expires_at)}"
    )


def create_challenge(db: Session, address: str, chain_id: int) -> AuthChallenge:
    settings = get_settings()
    if chain_id != settings.CHAIN_ID:
        raise AuthError(f"请把钱包切换到链 ID {settings.CHAIN_ID} 的网络后再登录")
    if not Web3.is_address(address):
        raise AuthError("钱包地址格式无效")

    # 消息中的地址必须是 EIP-55 校验和格式
    checksum = Web3.to_checksum_address(address)
    nonce = secrets.token_hex(16)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.LOGIN_CHALLENGE_TTL_SECONDS)

    challenge = AuthChallenge(
        nonce=nonce,
        address=checksum.lower(),
        message=build_siwe_message(checksum, chain_id, nonce, now, expires_at),
        expires_at=expires_at,
    )
    db.add(challenge)
    db.commit()
    return challenge


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(db: Session, nonce: str, signature: str) -> tuple[str, AuthSession]:
    """验证签名并创建会话，返回 (Cookie 中保存的明文令牌, 会话)"""
    settings = get_settings()
    now = datetime.now(UTC)

    # 加锁：同一个 nonce 的两次登录请求同时到达时，只有一个能成功
    challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.nonce == nonce).with_for_update())
    if challenge is None:
        raise AuthError("登录请求不存在，请重新登录")
    if challenge.used_at is not None:
        raise AuthError("该登录请求已经使用过，请重新登录")
    if challenge.expires_at <= now:
        raise AuthError("登录请求已过期，请重新登录")

    try:
        # personal_sign 会在消息前加上 "\x19Ethereum Signed Message:\n长度" 再签名，encode_defunct 做同样的处理
        signer = Account.recover_message(encode_defunct(text=challenge.message), signature=signature)
    except Exception:
        raise AuthError("签名格式无效")
    if signer.lower() != challenge.address:
        raise AuthError("签名者与登录地址不一致")

    challenge.used_at = now
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        token_hash=_hash_token(token),
        address=challenge.address,
        expires_at=now + timedelta(seconds=settings.SESSION_TTL_SECONDS),
    )
    db.add(session)
    db.commit()
    return token, session


def get_session_address(db: Session, token: str) -> str | None:
    """根据 Cookie 中的令牌查出已登录地址；令牌无效或已过期返回 None"""
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash_token(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    return session.address if session else None


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash_token(token)))
    db.commit()
