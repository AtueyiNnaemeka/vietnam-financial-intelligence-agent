"""Run once to create local text, raw table, and canonical metric artifacts."""
import argparse, json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
from src.ingestion.pdf_loader import find_report, extract_page_text
from src.ingestion.table_extraction import extract_tables
from src.processing.cleaning import canonical_rows
from src.processing.validation import validate_balance_sheet, validate_income_statement, validate_net_revenue, validate_asset_components, validate_cash_flow

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
      futures={pool.submit(extract_page_text,pdf):(ticker,year,pdf) for ticker,year,pdf in reports}
      for future in as_completed(futures):
        ticker,year,pdf=futures[future]; pages=future.result()
        (out/f"{ticker}_{year}_text.json").write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding="utf-8")
        count=sum(bool(p["text"]) for p in pages)
        print(f"{ticker} {year}: {count}/{len(pages)} pages have searchable text")

def rebuild_metrics(out_dir="data/processed"):
    out=Path(out_dir); all_rows=[]; checks=[]
    check_specs=(("balance_sheet",validate_balance_sheet,("total_assets","total_liabilities","total_equity")),
                 ("asset_components",validate_asset_components,("current_assets","noncurrent_assets","total_assets")),
                 ("income_statement",validate_income_statement,("net_revenue","cost_of_goods_sold","gross_profit")),
                 ("net_revenue_reconciliation",validate_net_revenue,("gross_sales","revenue_deductions","net_revenue")),
                 ("cash_flow",validate_cash_flow,("opening_cash","net_change_cash","closing_cash")))
    for ticker,company in COMPANIES.items():
      for year in (2023,2024,2025):
        table_path=out/f"{ticker}_{year}_tables.json"
        if not table_path.exists(): raise FileNotFoundError(f"Missing extracted table artifact: {table_path}")
        tables=json.loads(table_path.read_text(encoding="utf-8"))
        rows=canonical_rows(tables,ticker=ticker,company=company,year=year,source_file=f"{ticker}_{year}.pdf")
        values={r["metric_id"]:r["value"] for r in rows}
        for statement,fn,metric_ids in check_specs:
            status,detail=fn(values)
            checks.append({"ticker":ticker,"year":year,"statement_type":statement,"validation_status":status,"detail":detail})
            if status!="unverified":
                for row in rows:
                    if row["metric_id"] in metric_ids: row["validation_status"]=status
        all_rows.extend(rows)
    columns=["company","ticker","year","statement_type","metric_id","metric_name_vi","metric_name_en","value","currency","unit","source_file","source_page","validation_status","derivation"]
    pd.DataFrame(all_rows,columns=columns).to_csv(out/"financial_metrics.csv",index=False)
    pd.DataFrame(checks).to_csv(out/"validation_report.csv",index=False)
    print(f"Rebuilt metrics: {len(all_rows)} rows; {sum(r['validation_status']=='valid' for r in all_rows)} individually validated.")

def preprocess(raw_dir="data/raw", out_dir="data/processed"):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for ticker,company in COMPANIES.items():
      for year in (2023,2024,2025):
        pdf=find_report(raw_dir,ticker,year)
        if pdf is None: raise FileNotFoundError(f"Missing {ticker} {year} report under {raw_dir}")
        reports.append((ticker,company,year,pdf))
    # Text OCR runs in parallel across reports; table OCR remains an offline step.
    preprocess_text(raw_dir,out_dir)
    for ticker,company,year,pdf in reports:
        tables=extract_tables(pdf)
        (out/f"{ticker}_{year}_tables.json").write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding="utf-8")
    rebuild_metrics(out_dir)
    for ticker,company,year,pdf in reports:
        pages=json.loads((out/f"{ticker}_{year}_text.json").read_text(encoding="utf-8"))
        tables=json.loads((out/f"{ticker}_{year}_tables.json").read_text(encoding="utf-8"))
        print(f"{ticker} {year}: {len(pages)} pages, {len(tables)} tables")

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--raw-dir",default="data/raw"); parser.add_argument("--out-dir",default="data/processed"); parser.add_argument("--text-only",action="store_true"); parser.add_argument("--reuse-tables",action="store_true",help="Rebuild metrics and validation from existing *_tables.json artifacts")
    args=parser.parse_args()
    if args.text_only: preprocess_text(args.raw_dir,args.out_dir)
    elif args.reuse_tables: rebuild_metrics(args.out_dir)
    else: preprocess(args.raw_dir,args.out_dir)
