"""Agent 相关测试"""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_list_agents(client: TestClient) -> None:
    """测试获取 Agent 列表"""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "total" in data
    assert data["total"] >= 0


def test_chat_empty_message(client: TestClient) -> None:
    """测试空消息返回 422"""
    response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422
