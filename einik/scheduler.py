"""
定时调度模块

计算到下一个刷新时间点的等待秒数。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from einik.config import DAILY_REFRESH_HOUR, DAILY_REFRESH_MINUTE

log = logging.getLogger(__name__)


def seconds_until_next_refresh(now: datetime | None = None) -> float:
    """
    计算从当前时间到下一个刷新时间点的等待秒数。

    刷新时间: 每日 DAILY_REFRESH_HOUR:DAILY_REFRESH_MINUTE (默认 06:00)

    Returns:
        等待秒数
    """
    if now is None:
        now = datetime.now()

    target = now.replace(
        hour=DAILY_REFRESH_HOUR,
        minute=DAILY_REFRESH_MINUTE,
        second=0,
        microsecond=0,
    )

    # 如果今天的刷新时间已过，等到明天
    if now >= target:
        target += timedelta(days=1)

    delta = (target - now).total_seconds()
    log.info("下次刷新: %s (%.0f 秒后)", target.strftime("%Y-%m-%d %H:%M"), delta)
    return delta
