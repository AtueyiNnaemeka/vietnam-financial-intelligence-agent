import pandas as pd
from src.retrieval.structured import get_financial_metric

def test_structured_retrieval_preserves_source():
    frame=pd.DataFrame([{"ticker":"HPG","year":2023,"metric_id":"net_revenue","value":42,
                         "source_file":"HPG_2023.pdf","source_page":10}])
    row=get_financial_metric(frame,"HPG",2023,"net_revenue")
    assert row["value"]==42 and row["source_file"]=="HPG_2023.pdf" and row["source_page"]==10
