# 南方电网 (CSG) Python FastAPI + Streamlit 应用

基于 Python (FastAPI + Streamlit) 实现的极简南方电网微信扫码登录、会话状态验证与用电量/电费查询子项目。

## 目录结构

```
python/
├── app/
│   ├── __init__.py
│   ├── config.py            # 配置与路径定义
│   ├── csg_client.py        # 南方电网接口与 Mock 逻辑
│   ├── main.py              # FastAPI 路由入口 (包含 OpenAPI /docs)
│   ├── models.py            # Pydantic 响应与请求模型
│   ├── storage.py           # 会话本地 JSON 持久化
│   └── streamlit_app.py     # Streamlit 仪表盘界面
├── README.md                # 使用说明
└── requirements.txt         # 依赖列表
```

## 功能特性

1. **微信扫码登录**：生成登录二维码及 Base64 图，支持状态确认并保存 Token。
2. **会话状态验证**：检测本地存储的南方电网 Token 是否依然有效。
3. **用电量与电费查询**：支持按户号、年份、月份查询账户余额、月度累计用电量及每日用电明细图表。
4. **OpenAPI (Swagger)**：FastAPI 自动提供可视化 RESTful API 交互文档。

## 快速开始

### 1. 安装依赖

推荐使用 Python 3.9+ 虚拟环境：

```bash
cd python
pip install -r requirements.txt
```

### 2. 启动 FastAPI API 服务 (含 OpenAPI)

```bash
uvicorn app.main:app --reload --port 8000
```

服务启动后，访问以下地址查看 OpenAPI 交互文档：
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 3. 启动 Streamlit Web 仪表盘

在新的终端窗口中运行：

```bash
streamlit run app/streamlit_app.py --server.port 8501
```

浏览器打开 [http://localhost:8501](http://localhost:8501) 即可在线体验：
- **Tab 1**: 生成微信登录二维码并确认登录。
- **Tab 2**: 一键验证本地 Cookie/Token 会话有效性。
- **Tab 3**: 输入户号、年份和月份查询用电趋势图与明细数据。
