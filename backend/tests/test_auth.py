"""
钱包签名登录与订单访问控制测试
用 eth_account 在本地生成测试账户并签名，效果与 MetaMask 的 personal_sign 相同
"""

from datetime import UTC, datetime, timedelta

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuthChallenge

alice: LocalAccount = Account.create()
bob: LocalAccount = Account.create()


def sign(account: LocalAccount, message: str) -> str:
    return "0x" + account.sign_message(encode_defunct(text=message)).signature.hex().removeprefix("0x")


def challenge(client: TestClient, account: LocalAccount) -> dict:
    resp = client.post(
        "/api/v1/auth/challenge",
        json={"address": account.address, "chain_id": get_settings().CHAIN_ID},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def login(client: TestClient, account: LocalAccount) -> None:
    c = challenge(client, account)
    resp = client.post("/api/v1/auth/login", json={"nonce": c["nonce"], "signature": sign(account, c["message"])})
    assert resp.status_code == 200, resp.text


# ───────────────────────── 登录 ─────────────────────────


def test_challenge_message_follows_eip4361(anon_api: TestClient) -> None:
    message = challenge(anon_api, alice)["message"]
    settings = get_settings()
    assert message.startswith(f"{settings.APP_DOMAIN} wants you to sign in with your Ethereum account:\n{alice.address}\n")
    assert f"Chain ID: {settings.CHAIN_ID}" in message
    assert "Nonce: " in message and "Expiration Time: " in message


def test_login_sets_httponly_session_cookie(anon_api: TestClient) -> None:
    c = challenge(anon_api, alice)
    resp = anon_api.post("/api/v1/auth/login", json={"nonce": c["nonce"], "signature": sign(alice, c["message"])})

    assert resp.status_code == 200
    assert resp.json()["address"] == alice.address.lower()
    assert "HttpOnly" in resp.headers["set-cookie"]
    assert anon_api.get("/api/v1/auth/me").json()["address"] == alice.address.lower()


def test_signature_from_other_account_rejected(anon_api: TestClient) -> None:
    c = challenge(anon_api, alice)
    # bob 想冒充 alice：用自己的私钥签 alice 的登录消息
    resp = anon_api.post("/api/v1/auth/login", json={"nonce": c["nonce"], "signature": sign(bob, c["message"])})
    assert resp.status_code == 401


def test_nonce_cannot_be_replayed(anon_api: TestClient) -> None:
    c = challenge(anon_api, alice)
    body = {"nonce": c["nonce"], "signature": sign(alice, c["message"])}
    assert anon_api.post("/api/v1/auth/login", json=body).status_code == 200
    # 截获的签名再提交一次
    assert anon_api.post("/api/v1/auth/login", json=body).status_code == 401


def test_expired_challenge_rejected(anon_api: TestClient, db_session: Session) -> None:
    c = challenge(anon_api, alice)
    db_session.get(AuthChallenge, c["nonce"]).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    resp = anon_api.post("/api/v1/auth/login", json={"nonce": c["nonce"], "signature": sign(alice, c["message"])})
    assert resp.status_code == 401


def test_wrong_chain_rejected(anon_api: TestClient) -> None:
    resp = anon_api.post("/api/v1/auth/challenge", json={"address": alice.address, "chain_id": 1})
    assert resp.status_code == 400


def test_logout(anon_api: TestClient) -> None:
    login(anon_api, alice)
    assert anon_api.post("/api/v1/auth/logout").status_code == 204
    assert anon_api.get("/api/v1/auth/me").status_code == 401


# ─────────────────────── 订单访问控制 ───────────────────────


def test_orders_require_login(anon_api: TestClient) -> None:
    assert anon_api.post("/api/v1/orders", json={"product_id": "lesson17"}).status_code == 401
    assert anon_api.get("/api/v1/orders").status_code == 401


def test_cannot_read_other_users_order(anon_api: TestClient) -> None:
    login(anon_api, alice)
    order_id = anon_api.post("/api/v1/orders", json={"product_id": "lesson17"}).json()["order_id"]
    assert anon_api.get(f"/api/v1/orders/{order_id}").status_code == 200

    anon_api.cookies.clear()
    login(anon_api, bob)
    # 他人的订单返回 404，与订单不存在无法区分
    assert anon_api.get(f"/api/v1/orders/{order_id}").status_code == 404
    tx = {"tx_hash": "0x" + "ab" * 32}
    assert anon_api.post(f"/api/v1/orders/{order_id}/tx-hash", json=tx).status_code == 404
    assert anon_api.get("/api/v1/orders").json() == []


def test_idempotency_key_scoped_per_user(anon_api: TestClient) -> None:
    headers = {"Idempotency-Key": "same-key"}
    login(anon_api, alice)
    alice_order = anon_api.post("/api/v1/orders", json={"product_id": "lesson17"}, headers=headers).json()

    anon_api.cookies.clear()
    login(anon_api, bob)
    bob_order = anon_api.post("/api/v1/orders", json={"product_id": "lesson17"}, headers=headers).json()

    # 键相同，但属于不同账户，各自得到自己的订单
    assert bob_order["order_id"] != alice_order["order_id"]


def test_order_creation_rate_limited(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ORDER_CREATE_LIMIT_PER_MINUTE", 2)
    codes = [api.post("/api/v1/orders", json={"product_id": "lesson17"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
