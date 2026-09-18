"""einik 模块测试脚本"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Test 1: Pricing
from einik.pricing import calculate_monthly_cost, calculate_daily_costs

print("=== Pricing Tests ===")
print(f"Summer 100 kWh: {calculate_monthly_cost(100, 7)}")
print(f"Summer 300 kWh: {calculate_monthly_cost(300, 7)}")
print(f"Summer 700 kWh: {calculate_monthly_cost(700, 7)}")
print(f"Winter 150 kWh: {calculate_monthly_cost(150, 1)}")
print(f"Winter 350 kWh: {calculate_monthly_cost(350, 1)}")
print(f"Winter 500 kWh: {calculate_monthly_cost(500, 1)}")

# Expected:
# Summer 100: 100 * 0.5886 = 58.86
# Summer 300: 260*0.5886 + 40*0.6386 = 153.04 + 25.54 = 178.58
# Summer 700: 260*0.5886 + 340*0.6386 + 100*0.8886 = 153.04 + 217.12 + 88.86 = 459.02

s100 = calculate_monthly_cost(100, 7)
assert abs(s100 - 58.86) < 0.01, f"Summer 100 failed: {s100}"
s300 = calculate_monthly_cost(300, 7)
assert abs(s300 - 178.58) < 0.01, f"Summer 300 failed: {s300}"
s700 = calculate_monthly_cost(700, 7)
assert abs(s700 - 459.02) < 0.01, f"Summer 700 failed: {s700}"

# Daily costs
daily = [10.0] * 30
costs = calculate_daily_costs(daily, 7)
total = sum(c["cost"] for c in costs)
expected_total = calculate_monthly_cost(300, 7)
print(f"\nDaily 10kWh * 30 days total: {total:.2f} (expected: {expected_total})")
assert abs(total - expected_total) < 0.01

print("\nAll pricing tests PASSED!")

# Test 2: Renderer preview
print("\n=== Renderer Test ===")
try:
    from einik.renderer import renderer

    # QR screen
    qr_img = renderer.render_qr_screen("https://example.com/login?id=test123")
    qr_path = renderer.save_preview(qr_img, "test_qr_screen")
    print(f"QR screen saved: {qr_path}")

    # Dashboard with mock data
    mock_data = [
        {
            "account_number": "0601001234567890",
            "user_name": "Zhang*",
            "address": "Guangzhou",
            "balance": 150.50,
            "current_month": {
                "year": 2026, "month": 9,
                "total_kwh": 156.8,
                "total_cost": 92.29,
                "daily_usage": [
                    {"date": f"2026-09-{d:02d}", "kwh": kwh, "cost": round(kwh * 0.5886 * factor, 2)}
                    for d, kwh, factor in zip(
                        range(1, 18),
                        [9.8, 10.5, 8.2, 9.4, 10.2, 9.1, 12.8, 9.5, 8.4, 10.1, 9.2, 8.8, 9.9, 10.3, 6.8, 6.2, 6.6],
                        [1.05, 1.1, 0.95, 1.0, 1.05, 0.98, 1.15, 1.02, 0.96, 1.08, 1.0, 0.95, 1.02, 1.05, 0.9, 0.92, 0.94]
                    )
                ],
            },
            "last_month": {
                "year": 2026, "month": 8,
                "total_kwh": 320.5,
                "total_cost": 191.67,
            },
        },
        {
            "account_number": "0601009876543210",
            "user_name": "Li*",
            "address": "Guangzhou",
            "balance": 88.20,
            "current_month": {
                "year": 2026, "month": 9,
                "total_kwh": 130.2,
                "total_cost": 76.64,
                "daily_usage": [
                    {"date": f"2026-09-{d:02d}", "kwh": kwh, "cost": round(kwh * 0.5886 * factor, 2)}
                    for d, kwh, factor in zip(
                        range(1, 18),
                        [9.2, 10.6, 8.5, 7.6, 7.2, 8.8, 10.1, 6.8, 8.2, 9.8, 6.5, 5.2, 6.1, 6.4, 7.2, 5.1, 4.2],
                        [1.02, 1.08, 0.98, 0.95, 0.92, 1.0, 1.1, 0.9, 0.96, 1.05, 0.92, 0.88, 0.92, 0.94, 0.98, 0.9, 0.88]
                    )
                ],
            },
            "last_month": {
                "year": 2026, "month": 8,
                "total_kwh": 280.0,
                "total_cost": 165.81,
            },
        },
    ]

    dash_img = renderer.render_dashboard(mock_data)
    dash_path = renderer.save_preview(dash_img, "test_dashboard")
    print(f"Dashboard saved: {dash_path}")

    # Error screen
    err_img = renderer.render_error_screen("Test error message")
    err_path = renderer.save_preview(err_img, "test_error")
    print(f"Error screen saved: {err_path}")

    print("\nAll renderer tests PASSED!")
except Exception as e:
    print(f"Renderer test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Account filtering logic (3 accounts -> 2 accounts with last month data)
print("\n=== Account Selection Test ===")
from unittest.mock import MagicMock
from einik.csg_service import CSGService

test_service = CSGService()
test_service.client = MagicMock()
# 模拟绑定了 3 个户号
test_service.client.get_accounts.return_value = [
    {"account_number": "0601000000000001", "user_name": "张三", "address": "广州天河"},
    {"account_number": "0601000000000002", "user_name": "李四 (空置户)", "address": "广州越秀"},
    {"account_number": "0601000000000003", "user_name": "王五", "address": "广州番禺"},
]

def mock_fetch_usage(acc_num, year, month):
    # 模拟户号2上个月无数据(total_kwh=0)，户号1和户号3上个月有数据
    if acc_num == "0601000000000002":
        return {
            "account_number": acc_num,
            "user_name": "李四 (空置户)",
            "address": "广州越秀",
            "total_kwh": 0.0,
            "total_cost": 0.0,
            "balance": 50.0,
            "daily_usage": [],
        }
    elif acc_num == "0601000000000001":
        return {
            "account_number": acc_num,
            "user_name": "张三",
            "address": "广州天河",
            "total_kwh": 185.0 if month == 8 else 92.0,
            "total_cost": 108.89 if month == 8 else 54.15,
            "balance": 200.0,
            "daily_usage": [{"date": f"2026-{month:02d}-01", "kwh": 10.0, "cost": 5.88}],
        }
    else:
        return {
            "account_number": acc_num,
            "user_name": "王五",
            "address": "广州番禺",
            "total_kwh": 260.5 if month == 8 else 130.0,
            "total_cost": 153.33 if month == 8 else 76.51,
            "balance": 120.0,
            "daily_usage": [{"date": f"2026-{month:02d}-01", "kwh": 12.0, "cost": 7.06}],
        }

test_service.fetch_usage_data = MagicMock(side_effect=mock_fetch_usage)

selected_accounts = test_service.fetch_all_accounts_data()
print("选中的展示户号列表:")
for acc in selected_accounts:
    print(f"  - 户号: {acc['account_number']}, 用户: {acc['user_name']}, 上月用电: {acc['last_month']['total_kwh']}度")

selected_numbers = [a["account_number"] for a in selected_accounts]
assert len(selected_accounts) == 2, f"Expected 2 accounts, got {len(selected_accounts)}"
assert "0601000000000001" in selected_numbers, "Account 1 should be selected"
assert "0601000000000003" in selected_numbers, "Account 3 should be selected"
assert "0601000000000002" not in selected_numbers, "Account 2 (no data) should NOT be selected"

from einik.config import CONFIG_FILE
if CONFIG_FILE.exists():
    CONFIG_FILE.unlink()

print("\nAll account selection tests PASSED!")
