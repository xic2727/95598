import sys
from pathlib import Path

# Add project root directory to sys.path so 'app' module can be imported cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
import streamlit as st

from app.csg_client import csg_client
from app.storage import load_session

st.set_page_config(
    page_title="南方电网 - 用电查询仪表盘",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ 南方电网 - 微信扫码登录与用电查询")
st.markdown("通过微信扫码登录南方电网账户，查询实时电费余额及每日用电明细。")

# Persistent state initialization
if "login_id" not in st.session_state:
    st.session_state["login_id"] = None
if "qr_b64" not in st.session_state:
    st.session_state["qr_b64"] = None

tabs = st.tabs(["1. 微信扫码登录", "2. 会话状态验证", "3. 用电量与电费查询"])

# --- TAB 1: 微信扫码登录 ---
with tabs[0]:
    st.header("微信扫码登录")
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("生成微信登录二维码", type="primary"):
            res = csg_client.create_qr_login()
            st.session_state["login_id"] = res.login_id
            st.session_state["qr_b64"] = res.qr_code_base64
            st.success(f"已成功生成二维码！Login ID: `{res.login_id}`")

        if st.session_state.get("qr_b64"):
            st.image(st.session_state["qr_b64"], caption="请使用微信扫描上方二维码", width=260)

    with col2:
        if st.session_state.get("login_id"):
            st.subheader("扫码状态确认")
            st.info(f"正在等待扫码: `{st.session_state['login_id']}`")
            if st.button("确认/完成扫码登录"):
                res = csg_client.complete_qr_login(st.session_state["login_id"])
                if res.success:
                    st.success(res.message)
                    st.json({"用户ID": res.user_id, "Token": res.token})
                else:
                    st.error(res.message)
        else:
            st.write("点击左侧按钮生成二维码以开始登录。")

# --- TAB 2: 会话状态验证 ---
with tabs[1]:
    st.header("会话状态验证")
    if st.button("检查当前会话有效性"):
        res = csg_client.verify_session()
        if res.valid:
            st.success(f"✅ {res.message}")
            st.write(f"当前登录用户: `{res.user_id}`")
        else:
            st.warning(f"⚠️ {res.message}")

    saved_session = load_session()
    if saved_session:
        st.subheader("当前已保存的本地会话信息")
        st.json(saved_session)

# --- TAB 3: 用电量与电费查询 ---
with tabs[2]:
    st.header("用电量与电费查询")

    accounts = csg_client.get_accounts()
    account_options = [
        f"{acc['account_number']} ({acc['user_name']} - {acc['address']})"
        for acc in accounts
    ]
    account_mapping = {
        f"{acc['account_number']} ({acc['user_name']} - {acc['address']})": acc['account_number']
        for acc in accounts
    }

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        selected_account_label = st.selectbox(
            "选择缴费户号",
            options=account_options,
            help="选择已绑定的南方电网缴费户号",
        )
        acc_num = account_mapping.get(selected_account_label, "0601001234567890")
    with col_b:
        year = st.number_input("年份", min_value=2020, max_value=2030, value=datetime.now().year)
    with col_c:
        month = st.number_input("月份", min_value=1, max_value=12, value=datetime.now().month)

    if st.button("查询用电数据", type="primary"):
        usage = csg_client.query_usage(account_number=acc_num, year=year, month=month)

        # Overview Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("户名 / 缴费户号", f"{usage.user_name}", delta=usage.account_number)
        m2.metric("当前账户余额", f"¥ {usage.balance:.2f} 元")
        m3.metric(f"{usage.year}年{usage.month}月总用电量", f"{usage.total_kwh:.2f} kWh")
        m4.metric(f"{usage.year}年{usage.month}月总电费", f"¥ {usage.total_cost:.2f} 元")

        st.subheader("每日用电量趋势图")
        chart_data = {
            "日期": [item.date for item in usage.daily_usage],
            "用电量 (kWh)": [item.kwh for item in usage.daily_usage],
        }
        st.line_chart(chart_data, x="日期", y="用电量 (kWh)")

        st.subheader("每日用电量及估算电费明细表")
        table_data = [
            {"日期": item.date, "用电量 (kWh)": item.kwh, "估算电费 (元)": item.cost}
            for item in usage.daily_usage
        ]
        st.dataframe(table_data, use_container_width=True)
