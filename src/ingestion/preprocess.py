"""Run once to create local text, raw table, and canonical metric artifacts."""
import argparse, json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd
from src.ingestion.pdf_loader import find_report, extract_page_text
from src.ingestion.table_extraction import extract_tables
from src.processing.cleaning import canonical_rows
from src.processing.validation import validate_balance_sheet, validate_income_statement, validate_asset_components, validate_cash_flow

COMPANIES={"FPT":"FPT Corporation","VNM":"Vietnam Dairy Products Joint Stock Company","HPG":"Hoa Phat Group Joint Stock Company"}

def preprocess_text(raw_dir="data/raw",out_dir="data/processed"):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for ticker in COMPANIES:
      for year in (2023,2024,2025):
        pdf=find_report(raw_dir,ticker,year)
        if pdf is None: raise FileNotFoundError(f"Missing {ticker} {year} report under {raw_dir}")
        reports.append((ticker,year,pdf))
    with ProcessPoolExecutor(max_workers=min(4,len(reports))) as pool:
      for (ticker,year,pdf),pages in zip(reports,pool.map(extract_page_text,[r[2] for r in reports])):
        (out/f"{ticker}_{year}_text.json").write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding="utf-8")
        count=sum(bool(p["text"]) for p in pages)
        print(f"{ticker} {year}: {count}/{len(pages)} pages have searchable text")

def preprocess(raw_dir="data/raw", out_dir="data/processed"):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    all_rows=[]; checks=[]
    reports=[]
    for ticker,company in COMPANIES.items():
      for year in (2023,2024,2025):
        pdf=find_report(raw_dir,ticker,year)
        if pdf is None: raise FileNotFoundError(f"Missing {ticker} {year} report under {raw_dir}")
        reports.append((ticker,company,year,pdf))
    # OCR text independently by report. Separate processes avoid PyMuPDF thread-safety
    # issues and keep the offline extraction reasonably quick on local machines.
    with ProcessPoolExecutor(max_workers=min(4,len(reports))) as pool:
        for (ticker,company,year,pdf),pages in zip(reports,pool.map(extract_page_text,[r[3] for r in reports])):
            (out/f"{ticker}_{year}_text.json").write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding="utf-8")
    for ticker,company,year,pdf in reports:
        tables=extract_tables(pdf)
        (out/f"{ticker}_{year}_tables.json").write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding="utf-8")
        rows=canonical_rows(tables,ticker=ticker,company=company,year=year,source_file=pdf.name)
        values={r["metric_id"]:r["value"] for r in rows}
        check_specs=(("balance_sheet",validate_balance_sheet,("total_assets","total_liabilities","total_equity")),
                     ("asset_components",validate_asset_components,("current_assets","noncurrent_assets","total_assets")),
                     ("income_statement",validate_income_statement,("net_revenue","cost_of_goods_sold","gross_profit")),
                     ("cash_flow",validate_cash_flow,("opening_cash","net_change_cash","closing_cash")))
        for statement,fn,metric_ids in check_specs:
            status,detail=fn(values)
            checks.append({"ticker":ticker,"year":year,"statement_type":statement,"validation_status":status,"detail":detail})
            if status!="unverified":
                for row in rows:
                    if row["metric_id"] in metric_ids: row["validation_status"]=status
        all_rows.extend(rows)
        print(f"{ticker} {year}: {len(pages)} pages, {len(tables)} tables")
    pd.DataFrame(all_rows).to_csv(out/"financial_metrics.csv",index=False)
    pd.DataFrame(checks).to_csv(out/"validation_report.csv",index=False)
    print(f"Canonical unambiguous rows: {len(all_rows)}. Review raw tables and validation before relying on figures.")

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--raw-dir",default="data/raw"); parser.add_argument("--out-dir",default="data/processed"); parser.add_argument("--text-only",action="store_true")
    args=parser.parse_args()
    if args.text_only: preprocess_text(args.raw_dir,args.out_dir)
    else: preprocess(args.raw_dir,args.out_dir)
