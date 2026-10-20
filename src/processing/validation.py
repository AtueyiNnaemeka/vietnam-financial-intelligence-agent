"""Deterministic quality checks for normalized report rows."""
from math import isclose

def check_equation(left, right, *, relative_tolerance=0.01):
    if left is None or right is None:
        return "unverified", "one or more values are missing"
    if isclose(float(left), float(right), rel_tol=relative_tolerance, abs_tol=1):
        return "valid", ""
    relative_error=abs(float(left)-float(right))/max(abs(float(left)),abs(float(right)),1)
    status="error" if relative_error>0.10 else "warning"
    return status, f"values differ: {left} vs {right} ({relative_error:.1%} relative difference)"

def validate_balance_sheet(metrics):
    right = None
    if metrics.get("total_liabilities") is not None and metrics.get("total_equity") is not None:
        right = metrics["total_liabilities"] + metrics["total_equity"]
    return check_equation(metrics.get("total_assets"), right)

def validate_income_statement(metrics):
    cogs, gross, revenue = (metrics.get(k) for k in ("cost_of_goods_sold", "gross_profit", "net_revenue"))
    if cogs is None or gross is None or revenue is None:
        return "unverified", "revenue, COGS or gross profit missing"
    return check_equation(revenue - cogs, gross)

def validate_asset_components(metrics):
    current, noncurrent, total=(metrics.get(k) for k in ("current_assets","noncurrent_assets","total_assets"))
    if current is None or noncurrent is None or total is None:
        return "unverified","current assets, non-current assets or total assets missing"
    return check_equation(current+noncurrent,total)

def validate_cash_flow(metrics):
    opening,change,closing=(metrics.get(k) for k in ("opening_cash","net_change_cash","closing_cash"))
    if opening is None or change is None or closing is None:
        return "unverified","opening cash, net change or closing cash missing"
    return check_equation(opening+change,closing)
