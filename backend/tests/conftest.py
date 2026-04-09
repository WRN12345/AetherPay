"""pytest 配置"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI 测试客户端"""
    return TestClient(app)
