# einik - 树莓派墨水屏南方电网用电监控

基于 7.5 英寸黑白墨水屏的南方电网用电量实时展示系统。

## 功能

- **微信扫码登录**: 未登录时墨水屏显示二维码，微信扫码登录
- **双户号展示**: 左右分栏展示两个户号的用电数据
- **每日自动更新**: 每天 06:00 自动获取最新用电数据
- **阶梯电价计算**: 按广州居民阶梯电价计算费用
- **展示内容**:
  - 上月用电量 + 费用
  - 本月累计用电量 + 费用
  - 本月每日用电度数和费用

## 快速开始

### 1. 安装依赖

```bash
cd einik
pip install -r requirements.txt
```

树莓派还需安装:
```bash
# 中文字体
sudo apt install fonts-wqy-microhei

# Waveshare 墨水屏驱动
pip install waveshare-epd
# 或从官方仓库安装:
# git clone https://github.com/waveshare/e-Paper.git
# cd e-Paper/RaspberryPi_JetsonNano/python
# pip install .
```

### 2. PC 预览测试

在 Windows/Mac 上生成预览 PNG 图片（不需要墨水屏硬件）:

```bash
cd 95598
python -m einik.main --preview
```

预览图保存在 `einik/preview/` 目录。

### 3. 树莓派运行

```bash
cd 95598
python -m einik.main
```

### 4. 设为开机自启 (systemd)

创建 `/etc/systemd/system/einik.service`:

```ini
[Unit]
Description=einik E-Ink Power Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/95598
ExecStart=/usr/bin/python3 -m einik.main
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

启用服务:
```bash
sudo systemctl enable einik
sudo systemctl start einik
```

## 户号配置

首次登录后，程序会自动从 API 获取绑定户号并保存到 `einik/data/config.json`。

你可以手动编辑此文件来指定要展示的户号:

```json
{
  "account_numbers": ["0601001234567890", "0601009876543210"],
  "all_accounts": [...]
}
```

## 目录结构

```
einik/
├── __init__.py          # 包初始化
├── __main__.py          # python -m 入口
├── main.py              # 主守护进程 (状态机)
├── config.py            # 配置管理
├── csg_service.py       # 南方电网 API 封装
├── pricing.py           # 广州阶梯电价计算
├── renderer.py          # Pillow 图片渲染
├── epd_manager.py       # 墨水屏硬件抽象
├── scheduler.py         # 定时调度
├── requirements.txt     # 依赖
├── data/                # 运行时数据
│   ├── session.json     # 登录 Token
│   └── config.json      # 户号配置
├── fonts/               # 字体文件
└── preview/             # PC 预览输出
```

## 广州阶梯电价

| 档次 | 夏季 (5-10月) | 非夏季 (1-4/11-12月) | 电价 |
|------|:---:|:---:|------|
| 一档 | 0~260度 | 0~200度 | 0.5886 元/度 |
| 二档 | 261~600度 | 201~400度 | 0.6386 元/度 |
| 三档 | 601度+ | 401度+ | 0.8886 元/度 |
