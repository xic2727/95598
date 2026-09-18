from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.csg_client import csg_client
from app.models import (
    AccountListResponse,
    QRCompleteRequest,
    QRCompleteResponse,
    QRCreateResponse,
    SessionVerifyResponse,
    UsageQueryResponse,
)

app = FastAPI(
    title="南方电网 (CSG) 微信扫码登录与用电查询 API",
    description="基于 FastAPI 实现的南方电网微信扫码登录、会话验证及月度用电量/电费查询接口，提供交互式 OpenAPI 文档。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", summary="系统根路径")
def root():
    return {
        "status": "online",
        "service": "CSG Power Grid Stat API",
        "docs": "/docs",
    }

@app.post(
    "/api/session/qr/create",
    response_model=QRCreateResponse,
    summary="1. 发起微信扫码登录",
    description="生成用于微信扫码登录的二维码 URL 和 Base64 图片。",
)
def create_qr_login():
    return csg_client.create_qr_login()

@app.post(
    "/api/session/qr/complete",
    response_model=QRCompleteResponse,
    summary="2. 完成/轮询微信扫码登录",
    description="提交 login_id 校验微信扫码状态并完成登录注册过程。",
)
def complete_qr_login(body: QRCompleteRequest):
    return csg_client.complete_qr_login(body.login_id)

@app.get(
    "/api/session/verify",
    response_model=SessionVerifyResponse,
    summary="3. 验证会话状态",
    description="检查当前保存的南方电网 Token 是否有效。",
)
def verify_session():
    return csg_client.verify_session()

@app.get(
    "/api/accounts",
    response_model=AccountListResponse,
    summary="3.5. 获取缴费户号列表",
    description="获取当前已登录用户绑定的缴费户号列表。",
)
def get_accounts():
    return AccountListResponse(accounts=csg_client.get_accounts())

@app.get(
    "/api/usage/query",
    response_model=UsageQueryResponse,
    summary="4. 查询用电量与电费明细",
    description="根据缴费户号、年份和月份，查询对应月份的总电量、总电费及每日用电数据。",
)
def query_usage(
    account_number: Optional[str] = Query(
        None, description="缴费户号 (如留空则自动使用已登录账户默认户号)"
    ),
    year: int = Query(
        datetime.now().year, description="查询年份 (如 2026)"
    ),
    month: int = Query(
        datetime.now().month, description="查询月份 (1-12)"
    ),
):
    return csg_client.query_usage(account_number=account_number, year=year, month=month)
