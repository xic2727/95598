"""
einik 主守护进程

状态机循环:
  1. CHECK_LOGIN  - 检查登录状态
  2. QR_LOGIN     - 显示二维码，轮询扫码
  3. FETCH_DATA   - 获取用电数据
  4. DISPLAY      - 渲染并刷新墨水屏
  5. SLEEP        - 等待到次日 06:00

用法:
  python -m einik.main              # 正常运行 (需要墨水屏硬件)
  python -m einik.main --preview    # PC 预览模式 (只生成 PNG)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from enum import Enum, auto
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("einik")


class State(Enum):
    CHECK_LOGIN = auto()
    QR_LOGIN = auto()
    FETCH_DATA = auto()
    DISPLAY = auto()
    SLEEP = auto()
    EXIT = auto()


class EinkDaemon:
    """墨水屏用电监控守护进程。"""

    def __init__(self, preview_mode: bool = False):
        self.preview_mode = preview_mode
        self.state = State.CHECK_LOGIN
        self._running = True
        self._current_image = None
        self._accounts_data = None

        # 延迟导入，避免循环依赖和便于 PC 开发
        from einik.renderer import renderer
        from einik.epd_manager import epd_manager
        from einik.csg_service import csg_service
        from einik.scheduler import seconds_until_next_refresh

        self.renderer = renderer
        self.epd = epd_manager
        self.csg = csg_service
        self.seconds_until_next_refresh = seconds_until_next_refresh

        if preview_mode:
            log.info(">>> PC 预览模式：不驱动墨水屏硬件 <<<")

    def _display(self, image, full: bool = True) -> None:
        """显示图片到墨水屏或保存预览。"""
        self._current_image = image

        if self.preview_mode:
            name = f"preview_{datetime.now().strftime('%H%M%S')}"
            self.renderer.save_preview(image, name)
        else:
            if full:
                self.epd.full_update(image)
            else:
                self.epd.partial_update(image)

    def run(self) -> None:
        """主循环。"""
        log.info("einik 守护进程启动")

        # 注册信号处理
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        while self._running and self.state != State.EXIT:
            try:
                self._tick()
            except KeyboardInterrupt:
                log.info("收到中断信号，正在退出...")
                self.state = State.EXIT
            except Exception as e:
                log.error("状态 %s 执行异常: %s", self.state.name, e, exc_info=True)
                # 显示错误并等待后重试
                try:
                    err_img = self.renderer.render_error_screen(f"系统异常: {e}")
                    self._display(err_img)
                except Exception:
                    pass
                time.sleep(60)
                self.state = State.CHECK_LOGIN

        self._shutdown()

    def _tick(self) -> None:
        """状态机单步。"""
        if self.state == State.CHECK_LOGIN:
            self._do_check_login()
        elif self.state == State.QR_LOGIN:
            self._do_qr_login()
        elif self.state == State.FETCH_DATA:
            self._do_fetch_data()
        elif self.state == State.DISPLAY:
            self._do_display()
        elif self.state == State.SLEEP:
            self._do_sleep()

    # ── 各状态实现 ────────────────────────────────────────

    def _do_check_login(self) -> None:
        """检查登录状态。"""
        log.info("═══ 检查登录状态 ═══")
        if self.csg.check_login_status():
            log.info("登录有效，获取数据")
            self.state = State.FETCH_DATA
        else:
            log.info("需要登录，显示二维码")
            self.state = State.QR_LOGIN

    def _do_qr_login(self) -> None:
        """显示二维码并轮询扫码。"""
        log.info("═══ 二维码登录流程 ═══")

        qr_info = self.csg.create_qr_login()
        login_id = qr_info["login_id"]
        qr_data = qr_info["qr_url"]

        log.info("二维码已生成: login_id=%s", login_id)

        # 渲染二维码到墨水屏
        qr_img = self.renderer.render_qr_screen(qr_data)
        self._display(qr_img, full=True)

        # 轮询扫码状态
        if self.csg.poll_qr_status(login_id):
            log.info("扫码登录成功！")
            # 获取并保存户号
            self.csg.fetch_and_save_accounts()
            self.state = State.FETCH_DATA
        else:
            log.warning("扫码超时，将重新生成二维码")
            time.sleep(3)
            # 保持在 QR_LOGIN 状态，循环重试

    def _do_fetch_data(self) -> None:
        """获取所有户号的用电数据。"""
        log.info("═══ 获取用电数据 ═══")
        self._accounts_data = self.csg.fetch_all_accounts_data()

        if not self._accounts_data:
            log.error("未获取到任何用电数据")
            err_img = self.renderer.render_error_screen("未获取到用电数据，请检查户号配置")
            self._display(err_img)
            self.state = State.SLEEP
        else:
            self.state = State.DISPLAY

    def _do_display(self) -> None:
        """渲染仪表盘并显示。"""
        log.info("═══ 渲染仪表盘 ═══")
        dashboard_img = self.renderer.render_dashboard(self._accounts_data)
        self._display(dashboard_img, full=True)

        if self.preview_mode:
            # 预览模式只运行一次
            log.info("预览模式完成")
            self.state = State.EXIT
        else:
            self.state = State.SLEEP

    def _do_sleep(self) -> None:
        """等待到次日刷新时间。"""
        wait_seconds = self.seconds_until_next_refresh()
        hours = wait_seconds / 3600
        log.info("═══ 等待 %.1f 小时后刷新 ═══", hours)

        if not self.preview_mode:
            self.epd.sleep()

        # 分段等待，便于响应信号
        sleep_interval = 60  # 每 60 秒检查一次
        elapsed = 0.0
        while elapsed < wait_seconds and self._running:
            chunk = min(sleep_interval, wait_seconds - elapsed)
            time.sleep(chunk)
            elapsed += chunk

        if self._running:
            log.info("等待结束，开始新一轮数据更新")
            self.state = State.CHECK_LOGIN

    # ── 退出处理 ──────────────────────────────────────────

    def _handle_signal(self, signum, frame) -> None:
        """信号处理：优雅退出。"""
        sig_name = signal.Signals(signum).name
        log.info("收到信号 %s，准备退出", sig_name)
        self._running = False
        self.state = State.EXIT

    def _shutdown(self) -> None:
        """清理并退出。"""
        log.info("正在关闭...")
        if not self.preview_mode:
            self.epd.cleanup()
        log.info("einik 守护进程已停止")


def main():
    parser = argparse.ArgumentParser(
        description="einik - 墨水屏南方电网用电监控守护进程"
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="PC 预览模式：只生成 PNG 图片，不驱动硬件"
    )
    args = parser.parse_args()

    daemon = EinkDaemon(preview_mode=args.preview)
    daemon.run()


if __name__ == "__main__":
    main()
