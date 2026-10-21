from pathlib import Path
import math
import pandas as pd

def load_metrics(path="data/processed/financial_metrics.csv"):
    p=Path(path)
    if not p.exists(): return pd.DataFrame()
    return pd.read_csv(p)

def load_report_metadata(path="data/metadata/reports.csv"):
    """Return report provenance keyed by (ticker, year), with blanks normalized."""
    p = Path(path)
    if not p.exists():
        return {}
    reports = pd.read_csv(p)
    result = {}
    for row in reports.to_dict(orient="records"):
        key = (str(row.get("ticker", "")).upper(), str(int(row["year"])))
        result[key] = {
            name: (None if pd.isna(value) else value)
            for name, value in row.items()
        }
    return result

def _clean_record(record):
    """Convert pandas NaN placeholders to None before records reach the UI/router."""
    return {
        key: (None if value is None or (isinstance(value, float) and math.isnan(value)) else value)
        for key, value in record.items()
    }

def get_financial_metric(data, ticker, year, metric, *, require_valid=True, allow_derived=False, allow_unverified=False):
    if data.empty: return None
    subset=data[(data.ticker.str.upper()==ticker.upper()) & (data.year.astype(int)==int(year)) & (data.metric_id==metric)]
    if require_valid and "validation_status" in subset.columns:
        usable = {"valid"}
        if allow_derived:
            usable.add("derived")
        if allow_unverified:
            usable.add("unverified")
        subset=subset[subset.validation_status.astype(str).str.lower().isin(usable)]
    return None if subset.empty else _clean_record(subset.iloc[0].to_dict())

def compare_companies(data, year, metric, tickers=None, *, require_valid=True, allow_derived=False, allow_unverified=False):
    if tickers is None:
        tickers = sorted(data.ticker.dropna().astype(str).str.upper().unique()) if not data.empty else []
    return [row for ticker in tickers if (row:=get_financial_metric(data,ticker,year,metric,require_valid=require_valid,allow_derived=allow_derived,allow_unverified=allow_unverified)) is not None]
