"""公开配置接口测试"""

from fastapi.testclient import TestClient


def test_public_config(client: TestClient) -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()
    assert body["chain_id"] == 31337
    assert "contract_address" in body
