from src.processing.validation import validate_balance_sheet

def test_balance_sheet():
    assert validate_balance_sheet({'total_assets':100,'total_liabilities':60,'total_equity':40})[0]=='valid'
    assert validate_balance_sheet({'total_assets':100,'total_liabilities':50,'total_equity':40})[0]=='warning'
