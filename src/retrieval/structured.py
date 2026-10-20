from pathlib import Path
import pandas as pd

def load_metrics(path="data/processed/financial_metrics.csv"):
    p=Path(path)
    if not p.exists(): return pd.DataFrame()
    return pd.read_csv(p)

def get_financial_metric(data, ticker, year, metric, *, require_valid=True):
    if data.empty: return None
    subset=data[(data.ticker.str.upper()==ticker.upper()) & (data.year.astype(int)==int(year)) & (data.metric_id==metric)]
    if require_valid and "validation_status" in subset.columns:
        subset=subset[subset.validation_status.astype(str).str.lower()=="valid"]
    return None if subset.empty else subset.iloc[0].to_dict()

def compare_companies(data, year, metric, tickers=("FPT","VNM","HPG"), *, require_valid=True):
    return [row for ticker in tickers if (row:=get_financial_metric(data,ticker,year,metric,require_valid=require_valid)) is not None]
