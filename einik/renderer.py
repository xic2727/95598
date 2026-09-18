"""
墨水屏图片渲染模块

使用 Pillow 生成 800x480 黑白图片，用于 7.5 英寸墨水屏显示。
支持二维码登录页面和双户号用电仪表盘（条形图+折线图）。
"""

from __future__ import annotations

import io
import math
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

try:
    import qrcode
except ImportError:
    qrcode = None

from einik.config import EPD_WIDTH, EPD_HEIGHT, ROTATE_180, PREVIEW_DIR, get_font_path

log = logging.getLogger(__name__)

# ── 布局常量 ──────────────────────────────────────────────
W, H = EPD_WIDTH, EPD_HEIGHT   # 800 x 480
LINE_COLOR = 0                 # 黑色
BG_COLOR = 255                 # 白色


def _calc_nice_ticks(max_val: float, num_intervals: int = 4) -> Tuple[float, List[float]]:
    """
    计算美观的刻度上限与分段刻度值，确保刻度数恒定为 num_intervals + 1。
    例如 max_val = 11.4, 返回 (12.0, [0.0, 3.0, 6.0, 9.0, 12.0])
    """
    if max_val <= 0:
        max_val = 1.0

    target_step = max_val / num_intervals
    magnitude = 10 ** math.floor(math.log10(target_step)) if target_step > 0 else 1
    normalized = target_step / magnitude

    for candidate in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]:
        if candidate >= normalized:
            step = candidate * magnitude
            break
    else:
        step = 10.0 * magnitude

    nice_max = step * num_intervals
    ticks = [round(i * step, 2) for i in range(num_intervals + 1)]
    return nice_max, ticks


class Renderer:
    """墨水屏图片渲染器。"""

    def __init__(self):
        font_path = str(get_font_path())
        self.font_title = ImageFont.truetype(font_path, 20)
        self.font_header = ImageFont.truetype(font_path, 17)
        self.font_body = ImageFont.truetype(font_path, 15)
        self.font_summary_num = ImageFont.truetype(font_path, 16)
        self.font_small = ImageFont.truetype(font_path, 13)
        self.font_tiny = ImageFont.truetype(font_path, 11)

        # 75% 高对比度浓黑点阵底图：大幅加深墨水屏条形图黑度，彻底避免发淡发灰
        row_a = bytes([0x88] * (W // 8))  # 10001000
        row_b = bytes([0x00] * (W // 8))  # 00000000 全黑
        row_c = bytes([0x22] * (W // 8))  # 00100010
        row_d = bytes([0x00] * (W // 8))  # 00000000 全黑
        raw_bytes = b"".join([row_a, row_b, row_c, row_d][y % 4] for y in range(H))
        self._checker_img = Image.frombytes("1", (W, H), raw_bytes)

    def _new_image(self) -> Tuple[Image.Image, ImageDraw.Draw]:
        """创建新的白底黑字画布。"""
        img = Image.new("1", (W, H), BG_COLOR)
        draw = ImageDraw.Draw(img)
        return img, draw

    def _finalize(self, img: Image.Image) -> Image.Image:
        """最终处理：根据配置翻转 180°。"""
        if ROTATE_180:
            return img.rotate(180)
        return img

    def _draw_hline(self, draw: ImageDraw.Draw, y: int,
                    x1: int = 0, x2: int = W, width: int = 2) -> None:
        """画水平实线 (默认2px粗线，墨水屏更清晰)。"""
        draw.line([(x1, y), (x2, y)], fill=LINE_COLOR, width=width)

    def _draw_dashed_hline(self, draw: ImageDraw.Draw, y: int,
                           x1: int, x2: int, dash: int = 3, gap: int = 3) -> None:
        """画水平虚线（用于图表网格线）。"""
        for x in range(x1, x2, dash + gap):
            draw.line([(x, y), (min(x + dash, x2), y)], fill=LINE_COLOR, width=1)

    def _draw_avatar_icon(self, draw: ImageDraw.Draw, cx: int, cy: int) -> None:
        """在 (cx, cy) 为中心绘制一个精致的用户人像剪影图标。"""
        # 头部圆圈 (半径 5)
        draw.ellipse([cx - 4, cy - 9, cx + 4, cy - 1], fill=LINE_COLOR)
        # 身体/肩膀圆弧
        draw.pieslice([cx - 8, cy - 2, cx + 8, cy + 10], 190, 350, fill=LINE_COLOR)

    # ── 二维码登录页面 ────────────────────────────────────

    def render_qr_screen(
        self, qr_data: str, timestamp: Optional[datetime] = None
    ) -> Image.Image:
        """渲染二维码登录页面。"""
        img, draw = self._new_image()
        ts = timestamp or datetime.now()

        # 顶部标题 (字号放大到 20pt，清晰醒目)
        title = "南方电网 · 微信扫码登录"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 22), title, fill=LINE_COLOR, font=self.font_title)

        # 二维码
        qr_size = 280
        qr_img = self._generate_qr_image(qr_data, qr_size)
        qr_x = (W - qr_size) // 2
        qr_y = 65
        img.paste(qr_img, (qr_x, qr_y))

        # 二维码边框 (2px 粗线，清晰)
        draw.rectangle(
            [qr_x - 3, qr_y - 3, qr_x + qr_size + 3, qr_y + qr_size + 3],
            outline=LINE_COLOR, width=2
        )

        # 提示文字 (17pt 清晰)
        hint = "请使用微信扫描上方二维码绑定/登录"
        bbox = draw.textbbox((0, 0), hint, font=self.font_header)
        hw = bbox[2] - bbox[0]
        draw.text(((W - hw) // 2, qr_y + qr_size + 20), hint,
                  fill=LINE_COLOR, font=self.font_header)

        # 时间戳
        ts_text = f"生成时间: {ts.strftime('%Y-%m-%d %H:%M')}"
        bbox = draw.textbbox((0, 0), ts_text, font=self.font_body)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, qr_y + qr_size + 55), ts_text,
                  fill=LINE_COLOR, font=self.font_body)

        # 底部提示
        foot = "二维码有效期约5分钟，过期后系统将自动刷新重试"
        bbox = draw.textbbox((0, 0), foot, font=self.font_small)
        fw = bbox[2] - bbox[0]
        draw.text(((W - fw) // 2, H - 28), foot,
                  fill=LINE_COLOR, font=self.font_small)

        return self._finalize(img)

    def _generate_qr_image(self, data: str, size: int) -> Image.Image:
        """生成二维码图片。"""
        if data.startswith("data:image"):
            b64_part = data.split(",", 1)[1]
            raw = base64.b64decode(b64_part)
            qr_img = Image.open(io.BytesIO(raw))
        elif qrcode is not None:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
        else:
            qr_img = Image.new("1", (size, size), BG_COLOR)
            d = ImageDraw.Draw(qr_img)
            d.text((size // 4, size // 2 - 10), "QR N/A", fill=LINE_COLOR)
            return qr_img

        qr_img = qr_img.convert("1")
        qr_img = qr_img.resize((size, size), Image.NEAREST)
        return qr_img

    # ── 用电仪表盘（双卡片 + 条形图 + 折线图） ───────────────────

    def render_dashboard(self, accounts_data: List[Dict[str, Any]]) -> Image.Image:
        """
        渲染用电数据仪表盘。
        - 2个户号：左右分栏展示
        - 1个户号：全屏单卡片展示（充分利用 800px 宽度）
        """
        img, draw = self._new_image()
        now = datetime.now()

        # ── 顶部黑色状态栏 ──
        top_bar_h = 32
        draw.rectangle([0, 0, W, top_bar_h], fill=LINE_COLOR)

        title = "南方电网用电监控"
        draw.text((12, 5), title, fill=BG_COLOR, font=self.font_title)

        ts_text = f"{now.strftime('%m-%d %H:%M')} 更新"
        bbox = draw.textbbox((0, 0), ts_text, font=self.font_small)
        tw = bbox[2] - bbox[0]
        draw.text((W - tw - 14, 8), ts_text, fill=BG_COLOR, font=self.font_small)

        margin_x = 8
        card_top = top_bar_h + 8
        card_bottom = H - 8

        num_accounts = len(accounts_data)

        if num_accounts >= 2:
            # ── 双户号：左右分栏 ──
            card_gap = 10
            card_w = (W - 2 * margin_x - card_gap) // 2

            card1_x1 = margin_x
            card1_x2 = card1_x1 + card_w
            card2_x1 = card1_x2 + card_gap
            card2_x2 = card2_x1 + card_w

            self._render_account_card(img, draw, accounts_data[0],
                                     card1_x1, card1_x2, card_top, card_bottom)
            self._render_account_card(img, draw, accounts_data[1],
                                     card2_x1, card2_x2, card_top, card_bottom)

        elif num_accounts == 1:
            # ── 单户号：全屏宽展示 ──
            card_x1 = margin_x
            card_x2 = W - margin_x
            self._render_account_card(img, draw, accounts_data[0],
                                     card_x1, card_x2, card_top, card_bottom)

        return self._finalize(img)

    def _render_account_card(
        self, img: Image.Image, draw: ImageDraw.Draw, data: Dict[str, Any],
        x1: int, x2: int, y1: int, y2: int
    ) -> None:
        """
        渲染单个户号卡片。
        按需求：上月和本月用电情况在同一行展示，下方使用条形图(kWh)与折线(¥)展示。
        """
        # 卡片外框 (2px粗黑线，清晰不发虚)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=6, outline=LINE_COLOR, width=2)

        acc_num = data.get("account_number", "")
        user_name = data.get("user_name", "")
        cur = data.get("current_month", {})
        last = data.get("last_month", {})

        # ── 1. 顶部户号信息栏 (y1 到 y1 + 44) ──
        avatar_cx = x1 + 20
        avatar_cy = y1 + 22
        self._draw_avatar_icon(draw, avatar_cx, avatar_cy)

        draw.text((x1 + 36, y1 + 5), user_name, fill=LINE_COLOR, font=self.font_header)
        draw.text((x1 + 36, y1 + 26), acc_num, fill=LINE_COLOR, font=self.font_small)

        header_split_y = y1 + 46
        self._draw_hline(draw, header_split_y, x1, x2, width=2)

        # ── 2. 上月与本月汇总 (同一行展示) (header_split_y 到 header_split_y + 48) ──
        sum_y = header_split_y + 4
        mid_x = (x1 + x2) // 2

        last_month = last.get("month", 0)
        last_kwh = last.get("total_kwh", 0)
        last_cost = last.get("total_cost", 0)

        cur_month = cur.get("month", 0)
        cur_kwh = cur.get("total_kwh", 0)
        cur_cost = cur.get("total_cost", 0)

        # 左列: 上月用电
        draw.text((x1 + 10, sum_y), f"上月({last_month}月):", fill=LINE_COLOR, font=self.font_small)
        last_str = f"{last_kwh:.1f}度  ¥{last_cost:.2f}"
        draw.text((x1 + 10, sum_y + 18), last_str, fill=LINE_COLOR, font=self.font_summary_num)

        # 中间微细分隔线 (2px粗线)
        draw.line([(mid_x, sum_y + 2), (mid_x, sum_y + 36)], fill=LINE_COLOR, width=2)

        # 右列: 本月用电 (带走势对比符号)
        trend = "↑" if cur_kwh > last_kwh else ("↓" if cur_kwh < last_kwh else "")
        draw.text((mid_x + 10, sum_y), f"本月({cur_month}月):", fill=LINE_COLOR, font=self.font_small)
        cur_str = f"{cur_kwh:.1f}度  ¥{cur_cost:.2f} {trend}".rstrip()
        draw.text((mid_x + 10, sum_y + 18), cur_str, fill=LINE_COLOR, font=self.font_summary_num)

        summary_split_y = header_split_y + 44
        self._draw_hline(draw, summary_split_y, x1, x2, width=2)

        # ── 3. 图表区域 (summary_split_y 到 y2) ──
        daily_usage = cur.get("daily_usage", [])
        self._render_chart(img, draw, daily_usage,
                           x1=x1 + 6, x2=x2 - 6,
                           y1=summary_split_y + 4, y2=y2 - 6)

    def _render_chart(
        self, img: Image.Image, draw: ImageDraw.Draw, daily: List[Dict[str, Any]],
        x1: int, x2: int, y1: int, y2: int
    ) -> None:
        """
        绘制条形图 + 折线图组合图表。
        - 左 Y 轴: 用电量 (kWh / 度)，以浓黑点阵柱状图展示
        - 右 Y 轴: 电费 (元)，以加粗实线折线图展示
        - X 轴: 日期 (MM-DD)
        """
        # 图例说明栏
        legend_y = y1 + 2
        # 左侧小标题
        draw.text((x1 + 4, legend_y), "每日用电走势", fill=LINE_COLOR, font=self.font_tiny)

        # 右侧图例: [▒] 度数  ●─ 电费
        leg_bar_x = x2 - 145
        # 绘制图例小方块 (深色点阵)
        draw.rectangle([leg_bar_x, legend_y + 1, leg_bar_x + 10, legend_y + 11], outline=LINE_COLOR, width=1)
        bar_icon_crop = self._checker_img.crop((leg_bar_x + 1, legend_y + 2, leg_bar_x + 10, legend_y + 11))
        img.paste(bar_icon_crop, (leg_bar_x + 1, legend_y + 2))
        draw.text((leg_bar_x + 14, legend_y), "度数(左)", fill=LINE_COLOR, font=self.font_tiny)

        leg_line_x = x2 - 68
        draw.line([(leg_line_x, legend_y + 6), (leg_line_x + 14, legend_y + 6)], fill=LINE_COLOR, width=2)
        draw.ellipse([leg_line_x + 4, legend_y + 3, leg_line_x + 10, legend_y + 9], fill=LINE_COLOR)
        draw.text((leg_line_x + 18, legend_y), "电费(右)", fill=LINE_COLOR, font=self.font_tiny)

        # 检查是否有日明细数据
        if not daily:
            no_data_hint = "暂无当日本月每日用电明细"
            bbox = draw.textbbox((0, 0), no_data_hint, font=self.font_small)
            nw = bbox[2] - bbox[0]
            draw.text((x1 + (x2 - x1 - nw) // 2, y1 + (y2 - y1) // 2),
                      no_data_hint, fill=LINE_COLOR, font=self.font_small)
            return

        # 坐标系边界设定 (留出图例与顶部刻度文字空间)
        plot_top = y1 + 28
        plot_bottom = y2 - 24
        plot_h = plot_bottom - plot_top

        axis_left_w = 26   # 左刻度文字宽度
        axis_right_w = 26  # 右刻度文字宽度

        plot_x1 = x1 + axis_left_w + 2
        plot_x2 = x2 - axis_right_w - 2
        plot_w = plot_x2 - plot_x1

        # 计算数值上限与刻度 (左轴 kwh，右轴 cost)
        max_kwh_val = max((item.get("kwh", 0) for item in daily), default=1.0)
        max_cost_val = max((item.get("cost", 0) for item in daily), default=1.0)

        nice_max_kwh, kwh_ticks = _calc_nice_ticks(max_kwh_val, num_intervals=4)
        nice_max_cost, cost_ticks = _calc_nice_ticks(max_cost_val, num_intervals=4)

        num_intervals = len(kwh_ticks) - 1

        # 绘制横向网格虚线及 Y 轴刻度文字
        for i in range(num_intervals + 1):
            tick_ratio = i / num_intervals
            grid_y = int(plot_bottom - tick_ratio * plot_h)

            # 网格线 (最底部为实线，其余为虚线)
            if i == 0:
                draw.line([(plot_x1, grid_y), (plot_x2, grid_y)], fill=LINE_COLOR, width=2)
            else:
                self._draw_dashed_hline(draw, grid_y, plot_x1, plot_x2)

            # 左轴标签 (kwh): 右对齐
            kwh_val = kwh_ticks[i]
            kwh_str = f"{int(kwh_val)}" if kwh_val.is_integer() else f"{kwh_val:.1f}"
            bbox = draw.textbbox((0, 0), kwh_str, font=self.font_tiny)
            kw = bbox[2] - bbox[0]
            draw.text((plot_x1 - kw - 3, grid_y - 6), kwh_str, fill=LINE_COLOR, font=self.font_tiny)

            # 右轴标签 (cost): 左对齐
            cost_val = cost_ticks[i]
            cost_str = f"{int(cost_val)}" if cost_val.is_integer() else f"{cost_val:.1f}"
            draw.text((plot_x2 + 3, grid_y - 6), cost_str, fill=LINE_COLOR, font=self.font_tiny)

        # 绘制柱状图与折线图数据
        n = len(daily)
        slot_w = plot_w / n
        bar_w = max(3, min(14, int(slot_w * 0.55)))

        line_points: List[Tuple[int, int]] = []

        # 1. 绘制条形图 (kWh)
        for i, item in enumerate(daily):
            cx = int(plot_x1 + (i + 0.5) * slot_w)
            kwh = item.get("kwh", 0)

            # 柱高度计算
            bar_ratio = min(1.0, kwh / nice_max_kwh)
            bh = int(bar_ratio * plot_h)

            bx1 = cx - bar_w // 2
            bx2 = bx1 + bar_w
            by2 = plot_bottom
            by1 = plot_bottom - bh

            if bh > 0:
                cbx1 = max(0, min(W, bx1))
                cby1 = max(0, min(H, by1))
                cbx2 = max(cbx1 + 1, min(W, bx2))
                cby2 = max(cby1 + 1, min(H, by2))
                # 填充浓黑点阵
                bar_crop = self._checker_img.crop((cbx1, cby1, cbx2, cby2))
                img.paste(bar_crop, (cbx1, cby1))
                # 黑色描边
                draw.rectangle([bx1, by1, bx2, by2], outline=LINE_COLOR, width=1)

            # 计算折线点位置 (基于 cost 比例)
            cost = item.get("cost", 0)
            cost_ratio = min(1.0, cost / nice_max_cost)
            cy = int(plot_bottom - cost_ratio * plot_h)
            line_points.append((cx, cy))

        # 2. 绘制折线图 (Cost)
        if len(line_points) > 1:
            draw.line(line_points, fill=LINE_COLOR, width=3)
        elif len(line_points) == 1:
            # 只有1天数据
            pt = line_points[0]
            draw.ellipse([pt[0] - 4, pt[1] - 4, pt[0] + 4, pt[1] + 4], fill=LINE_COLOR)

        # 绘制折线各数据点的圆点标记（带白色衬底防遮挡）
        for pt in line_points:
            # 白色衬圈
            draw.ellipse([pt[0] - 5, pt[1] - 5, pt[0] + 5, pt[1] + 5], fill=BG_COLOR, outline=BG_COLOR)
            # 黑色实心点
            draw.ellipse([pt[0] - 3, pt[1] - 3, pt[0] + 3, pt[1] + 3], fill=LINE_COLOR)

        # 3. 绘制 X 轴刻度与日期标签
        # 针对 1~31 天自适应选择最佳刻度间隔，保证清晰不重叠
        if n >= 28:
            # 满月场景 (28~31天): 按 5 日周期展示 1, 5, 10, 15, 20, 25, 末日
            selected_indices = sorted(list({0, 4, 9, 14, 19, 24, n - 1}))
        elif n > 18:
            selected_indices = list(range(0, n, 3))
            if (n - 1) not in selected_indices:
                selected_indices.append(n - 1)
        elif n > 9:
            selected_indices = list(range(0, n, 2))
            if (n - 1) not in selected_indices:
                selected_indices.append(n - 1)
        else:
            selected_indices = list(range(n))

        date_y = plot_bottom + 4
        for i in selected_indices:
            if i >= n:
                continue
            item = daily[i]
            date_str = item.get("date", "")
            # 取后5位 MM-DD
            if len(date_str) >= 10:
                display_date = date_str[5:10]
            elif len(date_str) >= 5:
                display_date = date_str[-5:]
            else:
                display_date = date_str

            cx = int(plot_x1 + (i + 0.5) * slot_w)
            # 小刻度线
            draw.line([(cx, plot_bottom), (cx, plot_bottom + 3)], fill=LINE_COLOR, width=1)

            bbox = draw.textbbox((0, 0), display_date, font=self.font_tiny)
            dw = bbox[2] - bbox[0]
            draw.text((cx - dw // 2, date_y), display_date, fill=LINE_COLOR, font=self.font_tiny)

    # ── 错误/状态页面 ─────────────────────────────────────

    def render_error_screen(self, message: str) -> Image.Image:
        """渲染错误或状态提示页面。"""
        img, draw = self._new_image()

        title = "系统提示"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, H // 3 - 30), title,
                  fill=LINE_COLOR, font=self.font_title)

        self._draw_wrapped_text(draw, message, (40, H // 3 + 20),
                                W - 80, self.font_header)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bbox = draw.textbbox((0, 0), ts, font=self.font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, H - 40), ts,
                  fill=LINE_COLOR, font=self.font_small)

        return self._finalize(img)

    def _draw_wrapped_text(
        self, draw: ImageDraw.Draw, text: str,
        position: Tuple[int, int], max_width: int, font: ImageFont.FreeTypeFont
    ) -> None:
        """绘制自动换行的文字。"""
        x, y = position
        line = ""
        for char in text:
            test_line = line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width:
                draw.text((x, y), line, fill=LINE_COLOR, font=font)
                y += bbox[3] - bbox[1] + 4
                line = char
            else:
                line = test_line
        if line:
            draw.text((x, y), line, fill=LINE_COLOR, font=font)

    # ── 预览工具 ──────────────────────────────────────────

    def save_preview(self, img: Image.Image, name: str = "preview") -> str:
        """保存预览图到 preview/ 目录，返回文件路径。"""
        path = PREVIEW_DIR / f"{name}.png"
        img.convert("L").save(path, "PNG")
        log.info("预览图已保存: %s", path)
        return str(path)


# 单例
renderer = Renderer()
