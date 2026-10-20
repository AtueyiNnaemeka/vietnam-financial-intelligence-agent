from src.processing.normalization import normalize_number

def test_number_normalization():
    assert normalize_number('(1.234.567)').value == -1234567
    assert normalize_number('1,234,567').value == 1234567
    assert normalize_number('1,25').status == 'warning'

