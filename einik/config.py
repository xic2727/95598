"""
einik 配置模块

路径定义、墨水屏参数、刷新策略等全局配置。
"""

import os
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── 目录结构 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PREVIEW_DIR = BASE_DIR / "preview"
FONTS_DIR = BASE_DIR / "fonts"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

# ── 持久化文件 ────────────────────────────────────────────
SESSION_FILE = DATA_DIR / "session.json"
CONFIG_FILE = DATA_DIR / "config.json"

# ── 墨水屏参数 ────────────────────────────────────────────
EPD_WIDTH = 800
EPD_HEIGHT = 480
ROTATE_180 = True              # 画面翻转180度（适配屏幕安装方向）

# ── 调度参数 ──────────────────────────────────────────────
DAILY_REFRESH_HOUR = 6      # 每日刷新时间 (24h)
DAILY_REFRESH_MINUTE = 0
QR_POLL_INTERVAL = 5        # 二维码轮询间隔 (秒)
QR_POLL_TIMEOUT = 300       # 二维码超时 (秒, 5分钟)

# ── 字体配置 ──────────────────────────────────────────────
# 优先级: 项目内字体 > 树莓派系统字体 > Windows 系统字体
_FONT_CANDIDATES = [
    FONTS_DIR / "WenQuanYiMicroHei.ttf",
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),       # Windows 微软雅黑
    Path("C:/Windows/Fonts/simhei.ttf"),     # Windows 黑体
]


def get_font_path() -> Path:
    """返回第一个可用的中文字体路径。"""
    for p in _FONT_CANDIDATES:
        if p.exists():
            log.info("使用字体: %s", p)
            return p
    raise FileNotFoundError(
        "未找到可用的中文字体！"
        "树莓派请运行: sudo apt install fonts-wqy-microhei\n"
        "或将字体文件放入 einik/fonts/ 目录"
    )


# ── 户号配置读写 ──────────────────────────────────────────

def load_config() -> dict:
    """加载 data/config.json 配置。"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict) -> None:
    """保存配置到 data/config.json。"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    log.info("配置已保存到 %s", CONFIG_FILE)


def get_account_numbers() -> list[str]:
    """从配置中获取要监控的户号列表。"""
    config = load_config()
    return config.get("account_numbers", [])
