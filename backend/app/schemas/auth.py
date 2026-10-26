"""登录接口的请求和响应模型"""

from pydantic import BaseModel, Field


class ChallengeRequest(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    chain_id: int


class ChallengeOut(BaseModel):
    nonce: str
    # 前端原样交给钱包签名，不能做任何修改
    message: str


class LoginRequest(BaseModel):
    nonce: str = Field(min_length=1, max_length=32)
    signature: str = Field(pattern=r"^0x[0-9a-fA-F]{130}$")


class MeOut(BaseModel):
    address: str
