"""Pure deterministic financial calculations."""
def _ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0: return None
    return numerator / denominator

def growth(current, previous):
    r = _ratio(None if current is None or previous is None else current - previous, previous)
    return None if r is None else r * 100
def gross_margin(gross_profit, revenue):
    r = _ratio(gross_profit, revenue); return None if r is None else r * 100
def operating_margin(operating_profit, revenue):
    r = _ratio(operating_profit, revenue); return None if r is None else r * 100
def net_profit_margin(net_profit, revenue):
    r = _ratio(net_profit, revenue); return None if r is None else r * 100
def roa(net_profit, average_assets):
    """Return on assets using average opening and closing assets for the period."""
    r = _ratio(net_profit, average_assets); return None if r is None else r * 100
def roe(net_profit, average_equity):
    """Return on equity using average opening and closing equity for the period."""
    r = _ratio(net_profit, average_equity); return None if r is None else r * 100

def average_balance(opening_balance, closing_balance):
    if opening_balance is None or closing_balance is None:
        return None
    return (opening_balance + closing_balance) / 2
def liabilities_to_equity(liabilities, equity): return _ratio(liabilities, equity)
def borrowings_to_equity(short_borrowings, long_borrowings, equity):
    if short_borrowings is None or long_borrowings is None: return None
    return _ratio(short_borrowings + long_borrowings, equity)
def current_ratio(current_assets, current_liabilities): return _ratio(current_assets, current_liabilities)
def cash_ratio(cash, current_liabilities): return _ratio(cash, current_liabilities)
def operating_cash_flow_to_profit(operating_cash_flow, net_profit): return _ratio(operating_cash_flow, net_profit)
def free_cash_flow(operating_cash_flow, capital_expenditure):
    if operating_cash_flow is None or capital_expenditure is None: return None
    return operating_cash_flow - abs(capital_expenditure)
