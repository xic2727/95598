from typing import List, Optional
from pydantic import BaseModel, Field

# --- QR Code Login Models ---

class QRCreateResponse(BaseModel):
    login_id: str = Field(..., description="登录 ID / 唯一会话标识")
    qr_code_url: str = Field(..., description="二维码原始 URL")
    qr_code_base64: str = Field(..., description="二维码图片的 Base64 data URL")

class QRCompleteRequest(BaseModel):
    login_id: str = Field(..., description="待完成的登录 ID")

class QRCompleteResponse(BaseModel):
    success: bool = Field(..., description="扫码登录是否成功/完成")
    message: str = Field(..., description="状态描述信息")
    user_id: Optional[str] = Field(None, description="用户标识/手机号/户号")
    token: Optional[str] = Field(None, description="南方电网会话 Token")

class AccountItem(BaseModel):
    account_number: str = Field(..., description="缴费户号")
    user_name: str = Field(..., description="户名")
    address: str = Field(..., description="用电地址")

class AccountListResponse(BaseModel):
    accounts: List[AccountItem] = Field(default_factory=list, description="用户关联的缴费户号列表")

class SessionVerifyResponse(BaseModel):
    valid: bool = Field(..., description="会话是否有效")
    user_id: Optional[str] = Field(None, description="绑定的用户 ID")
    message: str = Field(..., description="说明消息")

# --- Electricity Usage & Balance Models ---

class DailyUsageItem(BaseModel):
    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    kwh: float = Field(..., description="当日用电量 (kWh)")
    cost: float = Field(..., description="当日估计电费 (元)")

class UsageQueryResponse(BaseModel):
    account_number: str = Field(..., description="缴费户号")
    user_name: str = Field("张*", description="户名")
    address: str = Field("广东省广州市天河区***", description="用电地址")
    balance: float = Field(..., description="当前账户余额 (元)")
    arrears: float = Field(..., description="当前欠费金额 (元)")
    year: int = Field(..., description="查询年份")
    month: int = Field(..., description="查询月份")
    total_kwh: float = Field(..., description="当月累计用电量 (kWh)")
    total_cost: float = Field(..., description="当月总电费 (元)")
    daily_usage: List[DailyUsageItem] = Field(default_factory=list, description="每日用电明细")
