"""
墨水屏硬件抽象层

封装 Waveshare 7.5" B/W V2 e-paper 面板的驱动操作。
PC 端无硬件时自动退化为 no-op，支持开发调试。
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

log = logging.getLogger(__name__)


class EpdManager:
    """Waveshare 7.5" e-paper V2 硬件管理。

    所有方法在 SDK 不可用时自动变为 no-op，
    这样可以在 PC 上进行开发和预览。
    """

    def __init__(self) -> None:
        self._epd = None
        self._module = None
        self._init_partial_done = False

        try:
            from waveshare_epd import epd7in5_V2_old  # type: ignore
            self._module = epd7in5_V2_old
            self._epd = epd7in5_V2_old.EPD()
            log.info("EpdManager: 墨水屏驱动已加载 (%s)", epd7in5_V2_old.__name__)
        except Exception as exc:
            log.warning(
                "EpdManager: waveshare_epd SDK 不可用，显示操作将被跳过 (%s)", exc
            )

    @property
    def available(self) -> bool:
        """是否有可用的墨水屏硬件。"""
        return self._epd is not None

    # ── 基础操作 ──────────────────────────────────────────

    def full_update(self, image: Image.Image) -> None:
        """全量刷新。每日数据更新时使用。"""
        if self._epd is None:
            return
        log.info("EPD: 全量刷新")
        self._epd.init()
        self._epd.display(self._epd.getbuffer(image))
        self._init_partial_done = False

    def partial_update(self, image: Image.Image) -> None:
        """局部刷新。二维码轮询等频繁更新时使用。"""
        if self._epd is None:
            return
        if not self._init_partial_done:
            self._epd.init_part()
            self._init_partial_done = True
        self._epd.display_Partial(
            self._epd.getbuffer(image),
            0, 0, self._epd.width, self._epd.height,
        )

    def clear(self) -> None:
        """清屏。"""
        if self._epd is None:
            return
        log.info("EPD: 清屏")
        self._epd.init()
        self._epd.Clear()
        self._init_partial_done = False

    # ── 高级操作 ──────────────────────────────────────────

    def wake_and_display(self, image: Image.Image) -> None:
        """唤醒并全量刷新后切换到局部模式。06:00 数据更新用。"""
        if self._epd is None:
            return
        log.info("EPD: 唤醒 + 全量刷新 + 切换局部模式")
        self._epd.init()
        self._epd.display(self._epd.getbuffer(image))
        self._epd.init_part()
        self._init_partial_done = True

    def wash(self, image: Image.Image) -> None:
        """防残影冲洗：清屏 → 全量刷新 → 切换局部模式。"""
        if self._epd is None:
            return
        log.info("EPD: 防残影冲洗")
        self._epd.init()
        self._epd.Clear()
        self._epd.display(self._epd.getbuffer(image))
        self._epd.init_part()
        self._init_partial_done = True

    def sleep(self) -> None:
        """进入低功耗模式。"""
        if self._epd is None:
            return
        try:
            self._epd.sleep()
            log.info("EPD: 已进入睡眠模式")
        except Exception as exc:
            log.warning("EPD sleep() 异常: %s", exc)
        self._init_partial_done = False

    def cleanup(self) -> None:
        """释放 SPI/GPIO 资源。程序退出时调用。"""
        if self._module is None:
            return
        try:
            self._module.epdconfig.module_exit(cleanup=True)
            log.info("EPD: GPIO 资源已释放")
        except Exception as exc:
            log.warning("EPD module_exit 异常: %s", exc)


# 单例
epd_manager = EpdManager()
