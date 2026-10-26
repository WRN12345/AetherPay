"""订单与商品接口的请求和响应模型；Wei 金额一律序列化为字符串，避免前端精度丢失"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

TX_HASH_PATTERN = r"^0x[0-9a-fA-F]{64}$"


class ProductOut(BaseModel):
    product_id: str
    name: str
    price_wei: str


class OrderCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class OrderOut(BaseModel):
    order_id: uuid.UUID
    product_id: str
    chain_order_id: str
    amount_wei: str
    chain_id: int
    contract_address: str
    status: str
    submitted_tx_hash: str | None
    paid_tx_hash: str | None
    paid_by_address: str | None
    paid_at: datetime | None
    expires_at: datetime


class TxHashSubmit(BaseModel):
    tx_hash: str = Field(pattern=TX_HASH_PATTERN)
