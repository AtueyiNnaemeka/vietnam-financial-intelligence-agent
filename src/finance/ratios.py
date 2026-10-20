from src.finance.metrics import *

DERIVED={
 "revenue_growth":("net_revenue",growth,"growth"), "net_profit_growth":("net_profit",growth,"growth"),
 "gross_margin":("gross_profit",gross_margin,"percent"), "operating_margin":("operating_profit",operating_margin,"percent"),
 "net_profit_margin":("net_profit",net_profit_margin,"percent"), "roa":("net_profit",roa,"percent"), "roe":("net_profit",roe,"percent"),
 "liabilities_to_equity":("total_liabilities",liabilities_to_equity,"ratio"), "current_ratio":("current_assets",current_ratio,"ratio"),
 "cash_ratio":("cash_and_equivalents",cash_ratio,"ratio"), "free_cash_flow":("operating_cash_flow",free_cash_flow,"VND"),
}
