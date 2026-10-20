from src.finance.metrics import growth, gross_margin, net_profit_margin, roa, roe, liabilities_to_equity, current_ratio, free_cash_flow

def test_core_ratios():
    assert growth(120,100)==20
    assert gross_margin(30,100)==30
    assert net_profit_margin(10,100)==10
    assert roa(10,100)==10 and roe(10,50)==20
    assert liabilities_to_equity(40,20)==2
    assert current_ratio(60,30)==2
    assert free_cash_flow(100,-40)==60

def test_zero_and_missing_denominators():
    assert growth(10,0) is None
    assert net_profit_margin(2,None) is None
