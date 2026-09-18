"""
CSG API 服务封装层

封装南方电网 API 调用，为 einik 主流程提供简洁接口。
复用 python/app/csg_client.py 中的核心 HTTP 逻辑。
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保可以导入 python/app 中的模块
_project_root = Path(__file__).resolve().parent.parent
_python_app = _project_root / "python"
if str(_python_app) not in sys.path:
    sys.path.insert(0, str(_python_app))

from app.csg_client import CSGClient
from app.storage import load_session as _load_session_orig, save_session as _save_session_orig

from einik.config import (
    SESSION_FILE,
    CONFIG_FILE,
    QR_POLL_INTERVAL,
    QR_POLL_TIMEOUT,
    load_config,
    save_config,
    get_candidate_accounts,
)
from einik.pricing import calculate_monthly_cost, calculate_daily_costs

log = logging.getLogger(__name__)


# ── 会话存取：覆盖 app.storage 的路径指向 einik/data ──────

import app.config as _app_config
_app_config.SESSION_FILE_PATH = SESSION_FILE
_app_config.DATA_DIR = SESSION_FILE.parent
_app_config.DATA_DIR.mkdir(parents=True, exist_ok=True)


class CSGService:
    """面向 einik 的南方电网服务接口。"""

    def __init__(self):
        self.client = CSGClient()

    # ── 登录状态 ──────────────────────────────────────────

    def check_login_status(self) -> bool:
        """检查当前 Token 是否有效。"""
        result = self.client.verify_session()
        if result.valid:
            log.info("登录状态有效: %s", result.message)
            return True
        else:
            log.warning("登录已失效: %s", result.message)
            return False

    # ── 二维码登录 ────────────────────────────────────────

    def create_qr_login(self) -> dict:
        """
        创建微信扫码登录二维码。

        Returns:
            {"login_id": str, "qr_url": str, "qr_base64": str}
        """
        result = self.client.create_qr_login()
        return {
            "login_id": result.login_id,
            "qr_url": result.qr_code_url,
            "qr_base64": result.qr_code_base64,
        }

    def poll_qr_status(self, login_id: str) -> bool:
        """
        轮询扫码状态，直到成功或超时。

        Args:
            login_id: 登录会话 ID

        Returns:
            True 如果扫码登录成功
        """
        start = time.time()
        while time.time() - start < QR_POLL_TIMEOUT:
            result = self.client.complete_qr_login(login_id)
            if result.success:
                log.info("扫码登录成功: %s", result.message)
                return True
            log.debug("等待扫码... (%s)", result.message)
            time.sleep(QR_POLL_INTERVAL)

        log.warning("二维码扫码超时 (%d秒)", QR_POLL_TIMEOUT)
        return False

    # ── 户号管理 ──────────────────────────────────────────

    def fetch_and_save_accounts(self) -> List[Dict[str, Any]]:
        """
        从 API 获取绑定户号列表并保存到 config.json。

        Returns:
            户号列表 [{"account_number": str, "user_name": str, "address": str, ...}, ...]
        """
        accounts = self.client.get_accounts()
        if not accounts:
            log.warning("未获取到绑定户号")
            return []

        log.info("获取到 %d 个绑定户号:", len(accounts))
        for acc in accounts:
            log.info("  - %s (%s) %s",
                     acc["account_number"], acc["user_name"], acc["address"])

        # 保存到配置
        config = load_config()
        config["all_accounts"] = accounts
        # 保存所有绑定户号为候选列表
        config["account_numbers"] = [acc["account_number"] for acc in accounts]
        log.info("已将全部 %d 个绑定户号加入候选监控列表", len(config["account_numbers"]))
        save_config(config)
        return accounts

    # ── 用电数据获取 ──────────────────────────────────────

    def fetch_usage_data(
        self, account_number: str, year: int, month: int
    ) -> Dict[str, Any]:
        """
        获取指定户号某月的用电数据。

        Returns:
            {
                "account_number": str,
                "user_name": str,
                "address": str,
                "total_kwh": float,
                "total_cost": float,
                "balance": float,
                "daily_usage": [{"date": str, "kwh": float, "cost": float}, ...]
            }
        """
        result = self.client.query_usage(
            account_number=account_number, year=year, month=month
        )

        daily_usage = []
        daily_kwh_list = []
        for item in result.daily_usage:
            daily_kwh_list.append(item.kwh)

        # 用阶梯电价重新计算每日费用
        daily_costs = calculate_daily_costs(daily_kwh_list, month)
        for i, item in enumerate(result.daily_usage):
            daily_usage.append({
                "date": item.date,
                "kwh": daily_costs[i]["kwh"],
                "cost": daily_costs[i]["cost"],
            })

        total_kwh = result.total_kwh
        # 用阶梯电价计算总费用
        total_cost = calculate_monthly_cost(total_kwh, month)

        return {
            "account_number": result.account_number,
            "user_name": result.user_name,
            "address": result.address,
            "total_kwh": round(total_kwh, 2),
            "total_cost": round(total_cost, 2),
            "balance": result.balance,
            "daily_usage": daily_usage,
        }

    def fetch_all_accounts_data(self) -> List[Dict[str, Any]]:
        """
        获取户号的当月和上月用电数据。
        当绑定户号多于 2 个时，自动筛选上月有数据（用电量 > 0）的 2 个户号进行展示。

        Returns:
            展示户号数据列表 (最多 2 个)
        """
        # 尝试从 API 同步刷新所有绑定的户号
        try:
            api_accounts = self.client.get_accounts()
            if api_accounts:
                cfg = load_config()
                cfg["all_accounts"] = api_accounts
                cfg["account_numbers"] = [acc["account_number"] for acc in api_accounts]
                save_config(cfg)
        except Exception as e:
            log.debug("尝试获取最新户号列表失败，使用本地配置: %s", e)

        candidates = get_candidate_accounts()

        if not candidates:
            log.warning("配置中无户号，尝试从 API 获取...")
            self.fetch_and_save_accounts()
            candidates = get_candidate_accounts()

        if not candidates:
            log.error("无法获取户号列表")
            return []

        log.info("待检查候选户号 (%d 个): %s", len(candidates), candidates)

        now = datetime.now()
        cur_year, cur_month = now.year, now.month

        # 上月
        if cur_month == 1:
            last_year, last_month = cur_year - 1, 12
        else:
            last_year, last_month = cur_year, cur_month - 1

        all_candidates_data = []
        for acc_num in candidates:
            log.info("获取户号 %s 的用电数据 (上月 %d-%02d / 当月 %d-%02d)...",
                     acc_num, last_year, last_month, cur_year, cur_month)
            try:
                last = self.fetch_usage_data(acc_num, last_year, last_month)
                current = self.fetch_usage_data(acc_num, cur_year, cur_month)

                user_name = current.get("user_name") or last.get("user_name") or ""
                address = current.get("address") or last.get("address") or ""
                balance = current.get("balance", 0.0)

                last_kwh = last.get("total_kwh", 0.0)
                # 判定上月是否有数据：用电度数 > 0 或日用电明细有度数 > 0
                has_last_month_data = (last_kwh > 0) or any(
                    d.get("kwh", 0) > 0 for d in last.get("daily_usage", [])
                )

                acc_data = {
                    "account_number": acc_num,
                    "user_name": user_name,
                    "address": address,
                    "balance": balance,
                    "current_month": {
                        "year": cur_year,
                        "month": cur_month,
                        "total_kwh": current["total_kwh"],
                        "total_cost": current["total_cost"],
                        "daily_usage": current["daily_usage"],
                    },
                    "last_month": {
                        "year": last_year,
                        "month": last_month,
                        "total_kwh": last["total_kwh"],
                        "total_cost": last["total_cost"],
                        "daily_usage": last.get("daily_usage", []),
                    },
                    "has_last_month_data": has_last_month_data,
                }
                all_candidates_data.append(acc_data)
                log.info("  户号 %s (%s): 上月=%.1f度(¥%.2f, %s) | 当月=%.1f度(¥%.2f)",
                         acc_num, user_name,
                         last["total_kwh"], last["total_cost"],
                         "上月有数据" if has_last_month_data else "上月无数据",
                         current["total_kwh"], current["total_cost"])
            except Exception as e:
                log.error("获取户号 %s 数据失败: %s", acc_num, e)
                all_candidates_data.append({
                    "account_number": acc_num,
                    "user_name": "获取失败",
                    "address": "",
                    "balance": 0.0,
                    "current_month": {
                        "year": cur_year, "month": cur_month,
                        "total_kwh": 0, "total_cost": 0, "daily_usage": [],
                    },
                    "last_month": {
                        "year": last_year, "month": last_month,
                        "total_kwh": 0, "total_cost": 0,
                    },
                    "has_last_month_data": False,
                })

        # ── 智能筛选：优先选择上月有数据（用电量 > 0）的户号 ──
        with_data = [acc for acc in all_candidates_data if acc.get("has_last_month_data")]
        without_data = [acc for acc in all_candidates_data if not acc.get("has_last_month_data")]

        if len(with_data) >= 2:
            # 找到 2 个或以上上月有数据的户号，取前 2 个展示
            selected = with_data[:2]
            log.info("已选出上月有数据的 2 个户号进行展示: %s",
                     [a["account_number"] for a in selected])
        elif len(with_data) == 1:
            # 仅 1 个户号上月有数据，如果有其他候选户号则补选 1 个凑成双户号，否则单户展示
            if without_data:
                selected = with_data + without_data[:1]
                log.info("仅 1 个户号上月有数据，补选 1 个户号展示: %s",
                         [a["account_number"] for a in selected])
            else:
                selected = with_data
                log.info("仅 1 个户号有数据，采用单户号全屏展示: %s",
                         selected[0]["account_number"])
        else:
            # 全部无上月数据，默认展示前两个
            selected = all_candidates_data[:2]
            log.warning("候选户号上月均无数据，默认展示前 %d 个户号", len(selected))

        # 记录实际展示户号到配置供参考
        try:
            cfg = load_config()
            cfg["display_accounts"] = [a["account_number"] for a in selected]
            save_config(cfg)
        except Exception:
            pass

        return selected


# 单例
csg_service = CSGService()
