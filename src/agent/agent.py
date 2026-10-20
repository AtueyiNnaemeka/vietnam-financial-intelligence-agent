"""Small bilingual intent router; all numbers come from structured rows/calculations."""
import re
from src.retrieval.structured import get_financial_metric, compare_companies
from src.retrieval.text import search_financial_notes
from src.finance.metrics import growth, net_profit_margin, roe, free_cash_flow

ALIASES={"revenue":"net_revenue","doanh thu":"net_revenue","total assets":"total_assets","tổng tài sản":"total_assets","tổng cộng tài sản":"total_assets",
 "net profit":"net_profit","lợi nhuận sau thuế":"net_profit","profit after tax":"net_profit","equity":"total_equity","vốn chủ sở hữu":"total_equity",
 "operating cash flow":"operating_cash_flow","lưu chuyển tiền thuần từ hoạt động kinh doanh":"operating_cash_flow",
 "cost of goods sold":"cost_of_goods_sold","giá vốn hàng bán":"cost_of_goods_sold","gross profit":"gross_profit","lợi nhuận gộp":"gross_profit",
 "operating profit":"operating_profit","financial income":"financial_income","financial expenses":"financial_expenses","profit before tax":"profit_before_tax",
 "parent shareholders":"parent_net_profit","basic eps":"basic_eps","cash and cash equivalents":"cash_and_equivalents","short-term investments":"short_term_investments",
 "accounts receivable":"accounts_receivable","inventory":"inventory","current assets":"current_assets","current liabilities":"current_liabilities",
 "short-term borrowings":"short_term_borrowings","long-term borrowings":"long_term_borrowings","total liabilities":"total_liabilities",
 "charter capital":"charter_capital","retained earnings":"retained_earnings","investing cash flow":"investing_cash_flow",
 "financing cash flow":"financing_cash_flow","capital expenditure":"capital_expenditure","capex":"capital_expenditure",
 "fixed assets":"capital_expenditure","net change in cash":"net_change_cash"}
TICKERS=("FPT","VNM","HPG")

def answer_question(question,data,language="English"):
    q=question.casefold(); ticker=next((t for t in TICKERS if re.search(rf"\b{t.casefold()}\b",q)),None)
    is_vi=language.lower().startswith("tiếng") or any(x in q for x in ("so sánh","tổng tài sản","biên lợi nhuận","doanh thu","lợi nhuận","năm "))
    years=[int(y) for y in re.findall(r"20\d\d",q)]; year=years[-1] if years else None
    if any(x in q for x in ("stock price","share price","giá cổ phiếu")):
        return {"answer":"Stock-price data is not included in the project's financial-statement dataset." if language=="English" else "Bộ dữ liệu báo cáo tài chính của dự án không bao gồm giá cổ phiếu.","evidence":[]}
    if year and year not in (2023,2024,2025):
        return {"answer":f"{year} is outside the available 2023–2025 dataset." if language=="English" else f"Năm {year} nằm ngoài dữ liệu hiện có (2023–2025).","evidence":[]}
    if data.empty:
        return {"answer":"No processed financial data found. Run `python -m src.ingestion.preprocess` first.","evidence":[]}
    compare=any(w in q for w in ("compare","so sánh"))
    metric_id=next((v for k,v in sorted(ALIASES.items(),key=lambda x:-len(x[0])) if k in q),None)
    if compare and year and ("margin" in q or "biên lợi nhuận" in q):
        rows=[]
        for co in TICKERS:
            profit=get_financial_metric(data,co,year,"net_profit"); revenue=get_financial_metric(data,co,year,"net_revenue")
            if profit and revenue:
                val=net_profit_margin(profit["value"],revenue["value"])
                rows.append({"ticker":co,"year":year,"metric_id":"net_profit_margin","value":val,"unit":"percent","source_file":profit["source_file"],"source_page":profit["source_page"],"validation_status":profit.get("validation_status","unverified")})
        if rows:
            lead=f"So sánh biên lợi nhuận ròng năm {year}: " if is_vi else "Net profit margin comparison for "+str(year)+": "
            return {"answer":lead+"; ".join(f"{r['ticker']} {r['value']:.2f}%" for r in rows),"evidence":rows,"formula":"lợi nhuận sau thuế / doanh thu thuần × 100" if is_vi else "net profit / net revenue × 100"}
    if ticker and year and ("cover" in q or "đủ" in q) and any(x in q for x in ("capital expenditure","capex","chi đầu tư")):
        ocf=get_financial_metric(data,ticker,year,"operating_cash_flow"); capex=get_financial_metric(data,ticker,year,"capital_expenditure")
        if ocf and capex:
            covered=ocf["value"] >= abs(capex["value"])
            answer=f"Dòng tiền kinh doanh của {ticker} {'đủ' if covered else 'không đủ'} bù chi đầu tư năm {year}." if is_vi else f"{ticker}'s operating cash flow {'covered' if covered else 'did not cover'} capital expenditure in {year}."
            return {"answer":answer,"evidence":[ocf,capex],"formula":"dòng tiền kinh doanh ≥ trị tuyệt đối chi đầu tư" if is_vi else "operating cash flow ≥ absolute capital expenditure"}
    if compare and year and metric_id:
        rows=compare_companies(data,year,metric_id)
        if rows: return {"answer":f"{metric_id} comparison for {year}: "+"; ".join(f"{r['ticker']} {r['value']:,.0f}" for r in rows),"evidence":rows}
    # Deterministic derived queries
    derived=None; base="net_profit"
    if "margin" in q or "biên lợi nhuận" in q: derived=net_profit_margin; base="net_profit"
    elif "roe" in q or "return on equity" in q: derived=roe; base="net_profit"
    if derived and ticker and year:
        a=get_financial_metric(data,ticker,year,base); b=get_financial_metric(data,ticker,year,"net_revenue" if derived is net_profit_margin else "total_equity")
        if a and b:
            value=derived(a["value"],b["value"])
            answer=(f"{ticker} năm {year}: {value:.2f}%." if is_vi else f"{ticker} {year}: {value:.2f}% (deterministic calculation).") if value is not None else ("Không thể tính do thiếu dữ liệu hoặc mẫu số bằng 0." if is_vi else "Cannot calculate: a value is missing or denominator is zero.")
            formula=("lợi nhuận sau thuế / doanh thu thuần × 100" if derived is net_profit_margin else "lợi nhuận sau thuế / vốn chủ sở hữu × 100") if is_vi else f"{base} / {'net_revenue' if derived is net_profit_margin else 'total_equity'} × 100"
            return {"answer":answer,"evidence":[a,b],"formula":formula}
    if "growth" in q or "tăng trưởng" in q:
        metric_id="net_revenue" if "revenue" in q or "doanh thu" in q else "net_profit"
        if ticker and len(years)>=2:
            cur=get_financial_metric(data,ticker,max(years),metric_id); prev=get_financial_metric(data,ticker,min(years),metric_id)
            if cur and prev:
                val=growth(cur["value"],prev["value"])
                return {"answer":f"{ticker} {metric_id} growth from {min(years)} to {max(years)}: {val:.2f}%." if val is not None else "Cannot calculate growth.","evidence":[prev,cur],"formula":"(current - previous) / previous × 100"}
    if ticker and year and metric_id:
        row=get_financial_metric(data,ticker,year,metric_id)
        if row:
            name=row.get("metric_name_vi",metric_id) if is_vi else row.get("metric_name_en",metric_id.replace("_"," "))
            return {"answer":f"{ticker} năm {year}, {name}: {row['value']:,.0f} {row.get('currency','VND')} (đơn vị theo báo cáo: {row.get('unit','theo báo cáo')})." if is_vi else f"{ticker} {year} {name}: {row['value']:,.0f} {row.get('currency','VND')} (reported unit: {row.get('unit','as reported')}).","evidence":[row]}
    hits=search_financial_notes(question,ticker=ticker,year=year)
    if hits:
        return {"answer":"Đã tìm thấy nội dung liên quan trong báo cáo. Hãy kiểm tra trích đoạn và trang được dẫn." if is_vi else "Relevant report text found. Review the cited excerpt; narrative search uses local keyword matching.","evidence":hits}
    return {"answer":"Không tìm thấy số liệu được hỗ trợ trong dữ liệu đã xử lý. Hãy kiểm tra báo cáo và nhãn chỉ tiêu đã trích xuất." if is_vi else "I couldn't find a supported value for that question in the processed dataset. Confirm the report is processed and the metric label was extracted.","evidence":[]}
