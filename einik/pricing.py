"""
广州阶梯电价计算模块

广州居民阶梯电价标准 (2024-2025):
- 夏季 (5-10月):  一档 0-260度, 二档 261-600度, 三档 601度+
- 非夏季 (1-4月, 11-12月): 一档 0-200度, 二档 201-400度, 三档 401度+

电价:
- 一档: 0.5886 元/度
- 二档: 0.6386 元/度 (加价 0.05)
- 三档: 0.8886 元/度 (加价 0.30)
"""

from typing import List, Tuple

# 基础电价 (元/度)
TIER1_PRICE = 0.5886
TIER2_PRICE = 0.6386   # +0.05
TIER3_PRICE = 0.8886   # +0.30


def is_summer(month: int) -> bool:
    """判断是否为夏季 (5-10月)。"""
    return 5 <= month <= 10


def get_tier_thresholds(month: int) -> Tuple[int, int]:
    """
    根据月份返回阶梯电价的档位分界点。

    Returns:
        (tier1_limit, tier2_limit): 一档上限, 二档上限
        超过 tier2_limit 的部分为三档
    """
    if is_summer(month):
        return 260, 600
    else:
        return 200, 400


def calculate_monthly_cost(total_kwh: float, month: int) -> float:
    """
    按月累计用电量计算当月总电费。

    Args:
        total_kwh: 当月累计用电量 (度)
        month: 月份 (1-12)

    Returns:
        总电费 (元)
    """
    if total_kwh <= 0:
        return 0.0

    tier1_limit, tier2_limit = get_tier_thresholds(month)

    if total_kwh <= tier1_limit:
        return round(total_kwh * TIER1_PRICE, 2)
    elif total_kwh <= tier2_limit:
        cost = tier1_limit * TIER1_PRICE + (total_kwh - tier1_limit) * TIER2_PRICE
        return round(cost, 2)
    else:
        cost = (
            tier1_limit * TIER1_PRICE
            + (tier2_limit - tier1_limit) * TIER2_PRICE
            + (total_kwh - tier2_limit) * TIER3_PRICE
        )
        return round(cost, 2)


def calculate_daily_costs(
    daily_kwh_list: List[float], month: int
) -> List[dict]:
    """
    为每日用电量分配费用 (基于累计档位)。

    每天的费用 = 截止当天的累计费用 - 截止前一天的累计费用。
    这样可以正确反映阶梯电价的递进关系。

    Args:
        daily_kwh_list: 每日用电量列表 (度), 按日期顺序
        month: 月份 (1-12)

    Returns:
        [{"kwh": float, "cost": float}, ...] 每日用电量和对应费用
    """
    results = []
    cumulative_kwh = 0.0
    prev_cumulative_cost = 0.0

    for kwh in daily_kwh_list:
        cumulative_kwh += kwh
        cumulative_cost = calculate_monthly_cost(cumulative_kwh, month)
        daily_cost = round(cumulative_cost - prev_cumulative_cost, 2)
        results.append({"kwh": round(kwh, 2), "cost": daily_cost})
        prev_cumulative_cost = cumulative_cost

    return results
