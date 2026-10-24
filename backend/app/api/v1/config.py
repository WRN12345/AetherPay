"""公开配置 API 端点：前端据此确认网络和合约地址"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_public_config() -> dict:
    """返回链 ID、合约地址和确认要求"""
    settings = get_settings()
    return {
        "chain_id": settings.CHAIN_ID,
        "contract_address": settings.CONTRACT_ADDRESS,
        "required_confirmations": settings.REQUIRED_CONFIRMATIONS,
    }
