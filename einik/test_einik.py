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
