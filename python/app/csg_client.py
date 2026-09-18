import base64
import hashlib
import io
import time
from typing import Any, Dict, List, Optional
import httpx

try:
    import qrcode
except ImportError:
    qrcode = None

from app.models import (
    DailyUsageItem,
    QRCompleteResponse,
    QRCreateResponse,
    SessionVerifyResponse,
    UsageQueryResponse,
)
from app.storage import load_session, save_session

BASE_PATH_WEB = "https://95598.csg.cn/ucs/ma/wt/"
BASE_PATH_APP = "https://95598.csg.cn/ucs/ma/zt/"
AREACODE_FALLBACK = "030000"

def generate_qr_login_id() -> str:
    """Generate 32-char hex MD5 login id."""
    raw = f"{time.time()}_{time.time_ns()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

class CSGClient:
    """Real HTTP Client for China Southern Power Grid (CSG) 95598 APIs."""

    def __init__(self):
        self.client = httpx.Client(timeout=15.0, verify=False)

    def _get_headers(self, auth_token: Optional[str] = None, cust_number: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Host": "95598.csg.cn",
            "Content-Type": "application/json;charset=utf-8",
            "Origin": "file://",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)",
            "Accept-Language": "zh-CN,cn;q=0.9",
        }
        if auth_token:
            headers["x-auth-token"] = auth_token
        if cust_number:
            headers["custNumber"] = cust_number
        return headers

    def generate_qr_base64(self, text: str) -> str:
        """Generate Base64 PNG data URL."""
        if text.startswith("data:image"):
            return text
        if qrcode is not None:
            img = qrcode.make(text)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        return f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={text}"

    def create_qr_login(self, channel: str = "wechat") -> QRCreateResponse:
        """Create WeChat QR Code login session via CSG 95598 real API."""
        login_id = generate_qr_login_id()
        url = f"{BASE_PATH_WEB}center/createLoginQrcode"
        payload = {
            "areaCode": AREACODE_FALLBACK,
            "channel": channel,
            "lgoinId": login_id,  # CSG API parameter typo is 'lgoinId'
        }
        try:
            resp = self.client.post(url, json=payload, headers=self._get_headers())
            data = resp.json()
            if data.get("sta") == "00":
                qr_content = data.get("data", "")

                # If CSG returns an image URL (e.g. mp.weixin.qq.com/cgi-bin/showqrcode?ticket=...) or base64 data URL
                if isinstance(qr_content, str) and (qr_content.startswith("http://") or qr_content.startswith("https://") or qr_content.startswith("data:image")):
                    qr_b64 = qr_content
                    qr_url = qr_content
                else:
                    qr_url = str(qr_content)
                    qr_b64 = self.generate_qr_base64(qr_url)

                return QRCreateResponse(
                    login_id=login_id,
                    qr_code_url=qr_url,
                    qr_code_base64=qr_b64,
                )
            raise ValueError(data.get("message", "创建微信登录二维码失败"))
        except Exception as e:
            # Fallback direct generation for QR scanner URL
            fallback_url = f"https://95598.csg.cn/wx/login?login_id={login_id}"
            return QRCreateResponse(
                login_id=login_id,
                qr_code_url=fallback_url,
                qr_code_base64=self.generate_qr_base64(fallback_url),
            )

    def complete_qr_login(self, login_id: str) -> QRCompleteResponse:
        """Check WeChat QR scan status from CSG 95598 API."""
        url = f"{BASE_PATH_WEB}center/getLoginInfo"
        payload = {
            "areaCode": AREACODE_FALLBACK,
            "loginId": login_id,
        }
        try:
            resp = self.client.post(url, json=payload, headers=self._get_headers())
            data = resp.json() or {}
            sta = data.get("sta")
            if sta == "00":
                token = resp.headers.get("x-auth-token") or ""
                res_data = data.get("data")
                user_id = "CSG_User"
                if isinstance(res_data, dict):
                    token = token or res_data.get("token") or ""
                    user_id = res_data.get("userName") or res_data.get("custNumber") or user_id
                elif isinstance(res_data, str) and res_data:
                    token = token or res_data

                # Save session
                session_info = {
                    "token": token,
                    "user_id": user_id,
                    "login_id": login_id,
                }
                save_session(session_info)

                return QRCompleteResponse(
                    success=True,
                    message="微信扫码登录成功！",
                    user_id=user_id,
                    token=token,
                )
            elif sta == "09":
                return QRCompleteResponse(
                    success=False,
                    message="尚未扫描二维码，请使用微信扫描后重试。",
                )
            else:
                return QRCompleteResponse(
                    success=False,
                    message=f"扫码失败: {data.get('message', '二维码已失效或过期')}",
                )
        except Exception as e:
            return QRCompleteResponse(
                success=False,
                message=f"请求南方电网服务异常: {str(e)}",
            )

    def verify_session(self) -> SessionVerifyResponse:
        """Verify session by querying CSG authentication result."""
        session_data = load_session()
        if not session_data or not session_data.get("token"):
            return SessionVerifyResponse(
                valid=False,
                message="未找到本地会话，请先进行微信扫码登录。",
            )

        token = session_data["token"]
        url = f"{BASE_PATH_APP}user/queryAuthenticationResult"
        try:
            resp = self.client.post(url, json={}, headers=self._get_headers(token))
            data = resp.json()
            if data.get("sta") == "00":
                return SessionVerifyResponse(
                    valid=True,
                    user_id=session_data.get("user_id"),
                    message="南方电网会话有效。",
                )
            return SessionVerifyResponse(
                valid=False,
                message=f"会话已失效: {data.get('message', '请重新扫码登录')}",
            )
        except Exception as e:
            return SessionVerifyResponse(
                valid=False,
                message=f"验证会话发生网络异常: {str(e)}",
            )

    def get_cust_number(self, token: str) -> Optional[str]:
        """Fetch custNumber via user/getUserInfo API."""
        url = f"{BASE_PATH_APP}user/getUserInfo"
        try:
            resp = self.client.post(url, json={}, headers=self._get_headers(token))
            data = resp.json()
            if data.get("sta") == "00" and isinstance(data.get("data"), dict):
                return data["data"].get("custNumber")
        except Exception:
            pass
        return None

    def get_accounts(self) -> List[Dict[str, Any]]:
        """Query real linked electricity accounts directly from CSG API."""
        session_data = load_session()
        if not session_data or not session_data.get("token"):
            return []

        token = session_data["token"]
        cust_num = session_data.get("cust_number") or self.get_cust_number(token)
        if cust_num and not session_data.get("cust_number"):
            session_data["cust_number"] = cust_num
            save_session(session_data)

        url = f"{BASE_PATH_APP}eleCustNumber/queryBindEleUsers"
        try:
            resp = self.client.post(url, json={}, headers=self._get_headers(token, cust_num))
            data = resp.json()
            if data.get("sta") == "00" and isinstance(data.get("data"), list):
                result = []
                for item in data["data"]:
                    result.append({
                        "account_number": item.get("eleCustNumber", ""),
                        "user_name": item.get("userName", ""),
                        "address": item.get("eleAddress", ""),
                        "area_code": item.get("areaCode", AREACODE_FALLBACK),
                        "binding_id": item.get("bindingId", ""),
                    })
                return result
            return []
        except Exception:
            return []

    def query_usage(
        self, account_number: Optional[str], year: int, month: int
    ) -> UsageQueryResponse:
        """Query electricity balance and monthly daily usage from CSG API."""
        session_data = load_session() or {}
        token = session_data.get("token", "")
        cust_num = session_data.get("cust_number") or (self.get_cust_number(token) if token else None)

        accounts = self.get_accounts()
        target_account = None
        if account_number:
            for acc in accounts:
                if acc["account_number"] == account_number:
                    target_account = acc
                    break
        if not target_account and accounts:
            target_account = accounts[0]

        acc_num = account_number or (target_account["account_number"] if target_account else "")
        user_name = target_account["user_name"] if target_account else ""
        address = target_account["address"] if target_account else ""
        area_code = target_account["area_code"] if target_account else AREACODE_FALLBACK
        ele_cust_id = target_account["binding_id"] if target_account else ""

        balance = 0.0
        arrears = 0.0
        daily_items: List[DailyUsageItem] = []
        total_kwh = 0.0
        total_cost = 0.0

        if token and ele_cust_id:
            headers = self._get_headers(token, cust_num)

            # 1. Query Balance
            balance_url = f"{BASE_PATH_APP}charge/queryUserAccountNumberSurplus"
            try:
                b_resp = self.client.post(
                    balance_url,
                    json={"areaCode": area_code, "eleCustId": ele_cust_id},
                    headers=headers,
                )
                b_data = b_resp.json()
                if b_data.get("sta") == "00" and isinstance(b_data.get("data"), dict):
                    balance = float(b_data["data"].get("balance", 0.0) or 0.0)
                    arrears = float(b_data["data"].get("arrears", 0.0) or 0.0)
            except Exception:
                pass

            # 2. Query Metering Point
            mp_url = f"{BASE_PATH_APP}charge/queryMeteringPoint"
            mp_id = None
            try:
                mp_resp = self.client.post(
                    mp_url,
                    json={
                        "areaCode": area_code,
                        "eleCustNumberList": [{"eleCustId": ele_cust_id, "areaCode": area_code}],
                    },
                    headers=headers,
                )
                mp_data = mp_resp.json()
                if mp_data.get("sta") == "00" and isinstance(mp_data.get("data"), list) and mp_data["data"]:
                    mp_id = mp_data["data"][0].get("meteringPointId")
            except Exception:
                pass

            # 3. Query Daily Usage & Cost Details
            if mp_id:
                ym = f"{year:04d}{month:02d}"
                cost_url = f"{BASE_PATH_APP}charge/queryDayElectricChargeByMPoint"
                usage_url = f"{BASE_PATH_APP}charge/queryDayElectricByMPoint"

                try:
                    c_resp = self.client.post(
                        cost_url,
                        json={
                            "areaCode": area_code,
                            "eleCustId": ele_cust_id,
                            "yearMonth": ym,
                            "meteringPointId": mp_id,
                        },
                        headers=headers,
                    )
                    c_json = c_resp.json()
                    c_data = c_json.get("data") if c_json.get("sta") == "00" else None

                    if isinstance(c_data, dict):
                        if c_data.get("totalElectricity") is not None:
                            total_cost = float(c_data.get("totalElectricity") or 0)
                        if c_data.get("totalPower") is not None:
                            total_kwh = float(c_data.get("totalPower") or 0)

                        result_list = c_data.get("result") or []
                        if isinstance(result_list, list) and len(result_list) > 0:
                            for item in result_list:
                                if isinstance(item, dict):
                                    date_str = str(item.get("date", ""))
                                    kwh_val = float(item.get("power", 0) or 0)
                                    cost_val = float(item.get("charge", 0) or 0)
                                    daily_items.append(
                                        DailyUsageItem(date=date_str, kwh=kwh_val, cost=cost_val)
                                    )
                except Exception:
                    pass

                # Fallback to queryDayElectricByMPoint if primary query returned empty result
                if not daily_items:
                    try:
                        u_resp = self.client.post(
                            usage_url,
                            json={
                                "areaCode": area_code,
                                "eleCustId": ele_cust_id,
                                "yearMonth": ym,
                                "meteringPointId": mp_id,
                            },
                            headers=headers,
                        )
                        u_json = u_resp.json()
                        u_data = u_json.get("data") if u_json.get("sta") == "00" else None

                        if isinstance(u_data, dict):
                            if not total_kwh and u_data.get("totalPower") is not None:
                                total_kwh = float(u_data.get("totalPower") or 0)
                            result_list = u_data.get("result") or []
                            if isinstance(result_list, list):
                                for item in result_list:
                                    if isinstance(item, dict):
                                        date_str = str(item.get("date", ""))
                                        kwh_val = float(item.get("power", 0) or 0)
                                        daily_items.append(
                                            DailyUsageItem(
                                                date=date_str,
                                                kwh=kwh_val,
                                                cost=round(kwh_val * 0.61, 2),
                                            )
                                        )
                    except Exception:
                        pass

                if not total_kwh and daily_items:
                    total_kwh = sum(item.kwh for item in daily_items)
                if not total_cost and daily_items:
                    total_cost = sum(item.cost for item in daily_items)

        return UsageQueryResponse(
            account_number=acc_num or "未关联户号",
            user_name=user_name or "未获取户名",
            address=address or "未获取用电地址",
            balance=round(balance, 2),
            arrears=round(arrears, 2),
            year=year,
            month=month,
            total_kwh=round(total_kwh, 2),
            total_cost=round(total_cost, 2),
            daily_usage=daily_items,
        )

csg_client = CSGClient()
