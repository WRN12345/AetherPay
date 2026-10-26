"""pytest 配置与共用夹具"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_address
from app.database import Base, engine, get_db
from app.jobs import scan_payments
from app.main import app
from app.services.payments import PaidEvent
from app.services.rate_limit import order_create_limiter

PRICE = 10**16  # 0.01 ETH
USER_ADDRESS = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"


@pytest.fixture
def client() -> TestClient:
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """
    连接真实 PostgreSQL，但与真实数据完全隔离：
    在一个事务内新建临时 schema 并把表建在里面，测试结束整体回滚，schema、表和数据一起消失
    """
    try:
        connection = engine.connect()
    except Exception as exc:
        pytest.skip(f"数据库不可用：{type(exc).__name__}")

    transaction = connection.begin()
    schema = f"test_{uuid.uuid4().hex[:12]}"
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    # SET LOCAL 只在当前事务内生效：之后不带 schema 前缀的表名都指向临时 schema
    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    Base.metadata.create_all(connection)
    # 业务代码中的 commit 只提交到保存点，外层事务仍可回滚
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    order_create_limiter.reset()


@pytest.fixture
def anon_api(db_session: Session) -> Iterator[TestClient]:
    """未登录的测试客户端，使用隔离数据库会话；登录测试从这里走完整的签名流程"""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def api(anon_api: TestClient) -> TestClient:
    """以 USER_ADDRESS 身份"已登录"的测试客户端，跳过签名流程，供订单相关测试使用"""
    app.dependency_overrides[get_current_address] = lambda: USER_ADDRESS
    return anon_api


# ───────────────────────── 假链 ─────────────────────────


class FakeEth:
    def __init__(self, chain: "FakeChain") -> None:
        self._chain = chain

    @property
    def block_number(self) -> int:
        return self._chain.block_number

    def get_block(self, block: int | str) -> dict:
        # 支持 "safe" / "finalized" 等区块标签
        number = self._chain.finalized_block if isinstance(block, str) else block
        timestamp = self._chain.block_times.get(number, self._chain.default_time).timestamp()
        return {"number": number, "timestamp": int(timestamp)}


class FakeChain:
    """替代真实节点：测试可以设置最新区块号、各区块时间和付款事件"""

    def __init__(self) -> None:
        self.block_number = 10
        self.finalized_block = 4
        self.default_time = datetime.now(UTC)
        self.block_times: dict[int, datetime] = {}
        self.events: list[PaidEvent] = []
        self.eth = FakeEth(self)

    def fetch(self, start: int, end: int) -> list[PaidEvent]:
        return [e for e in self.events if start <= e.block_number <= end]


@pytest.fixture
def fake_chain(monkeypatch: pytest.MonkeyPatch) -> FakeChain:
    chain = FakeChain()
    monkeypatch.setattr(scan_payments, "get_web3", lambda: chain)
    monkeypatch.setattr(scan_payments, "fetch_paid_events", chain.fetch)
    return chain


def make_event(
    chain_order_id: str,
    amount_wei: int = PRICE,
    block: int = 2,
    log_index: int = 0,
    block_time: datetime | None = None,
) -> PaidEvent:
    return PaidEvent(
        chain_order_id=chain_order_id,
        payer_address="0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
        amount_wei=amount_wei,
        tx_hash=f"0x{block:064x}",
        log_index=log_index,
        block_number=block,
        block_hash="0x" + "cc" * 32,
        block_time=block_time or datetime.now(UTC) - timedelta(minutes=1),
    )
