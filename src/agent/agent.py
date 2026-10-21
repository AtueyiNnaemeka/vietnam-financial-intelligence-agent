"""Small bilingual intent router; all numbers come from reviewed rows/calculations."""
import re

from src.finance.metrics import growth, net_profit_margin, roe
from src.retrieval.structured import compare_companies, get_financial_metric
from src.retrieval.text import search_financial_notes

ALIASES = {
    "revenue": "net_revenue", "doanh thu": "net_revenue",
    "total assets": "total_assets", "tổng tài sản": "total_assets", "tổng cộng tài sản": "total_assets",
    "net profit": "net_profit", "lợi nhuận sau thuế": "net_profit", "profit after tax": "net_profit",
    "equity": "total_equity", "vốn chủ sở hữu": "total_equity",
    "operating cash flow": "operating_cash_flow", "lưu chuyển tiền thuần từ hoạt động kinh doanh": "operating_cash_flow",
    "cost of goods sold": "cost_of_goods_sold", "giá vốn hàng bán": "cost_of_goods_sold",
    "gross profit": "gross_profit", "lợi nhuận gộp": "gross_profit",
    "operating profit": "operating_profit", "financial income": "financial_income",
    "financial expenses": "financial_expenses", "profit before tax": "profit_before_tax",
    "parent shareholders": "parent_net_profit", "basic eps": "basic_eps",
    "cash and cash equivalents": "cash_and_equivalents", "short-term investments": "short_term_investments",
    "accounts receivable": "accounts_receivable", "inventory": "inventory",
    "current assets": "current_assets", "current liabilities": "current_liabilities",
    "short-term borrowings": "short_term_borrowings", "long-term borrowings": "long_term_borrowings",
    "total liabilities": "total_liabilities", "charter capital": "charter_capital",
    "retained earnings": "retained_earnings", "investing cash flow": "investing_cash_flow",
    "financing cash flow": "financing_cash_flow", "capital expenditure": "capital_expenditure",
    "capex": "capital_expenditure", "fixed assets": "capital_expenditure", "net change in cash": "net_change_cash",
}
TICKERS = ("FPT", "VNM", "HPG")


def _answer(text, evidence=None, **extra):
    return {"answer": text, "evidence": evidence or [], **extra}


def _missing_metric(metric_id, year, is_vi):
    if is_vi:
        return f"Không có số liệu {metric_id.replace('_', ' ')} năm {year} đã được xác thực trong dữ liệu có cấu trúc. Hãy kiểm tra bảng báo cáo gốc; tìm kiếm văn bản không được dùng để suy ra số liệu tài chính."
    return f"No validated {metric_id.replace('_', ' ')} value is available for {year}. Check the cited statement or review the extracted table; narrative text is not used to supply financial figures."


def _get_metric(data, ticker, year, metric_id):
    return get_financial_metric(data, ticker, year, metric_id, allow_derived=(metric_id == "net_revenue"))


def answer_question(question, data, language="English", data_root="data/processed", scope_ticker=None):
    q = question.casefold()
    mentioned_tickers = [ticker for ticker in TICKERS if re.search(rf"\b{ticker.casefold()}\b", q)]
    ticker = mentioned_tickers[0] if mentioned_tickers else (scope_ticker.upper() if scope_ticker else None)
    is_vi = language.lower().startswith("tiếng")
    years = [int(year) for year in re.findall(r"20\d\d", q)]
    year = years[-1] if years else None

    if scope_ticker:
        scope_ticker = scope_ticker.upper()
        conflicting = [name for name in mentioned_tickers if name != scope_ticker]
        if conflicting or (len(mentioned_tickers) > 1 and any(name != scope_ticker for name in mentioned_tickers)):
            return _answer(
                f"The selected company filter is {scope_ticker}, but the question asks about {', '.join(mentioned_tickers)}. Select All or choose a matching company."
                if not is_vi else
                f"Bộ lọc đang chọn {scope_ticker}, nhưng câu hỏi đề cập {', '.join(mentioned_tickers)}. Hãy chọn Tất cả hoặc công ty phù hợp."
            )
        data = data[data.ticker.astype(str).str.upper() == scope_ticker] if not data.empty else data

    if any(term in q for term in ("stock price", "share price", "giá cổ phiếu")):
        return _answer(
            "Stock-price data is not included in the project's financial-statement dataset."
            if not is_vi else "Bộ dữ liệu báo cáo tài chính của dự án không bao gồm giá cổ phiếu."
        )
    if year and year not in (2023, 2024, 2025):
        return _answer(
            f"{year} is outside the available 2023–2025 dataset."
            if not is_vi else f"Năm {year} nằm ngoài dữ liệu hiện có (2023–2025)."
        )
    if data.empty:
        return _answer("No processed financial data found. Run `python -m src.ingestion.preprocess` first.")

    compare = any(word in q for word in ("compare", "so sánh"))
    metric_id = next((value for key, value in sorted(ALIASES.items(), key=lambda item: -len(item[0])) if key in q), None)

    if compare and scope_ticker and len(mentioned_tickers) > 1:
        return _answer(f"Select All to compare multiple companies; the current filter is {scope_ticker}.")

    if compare and year and ("margin" in q or "biên lợi nhuận" in q):
        rows = []
        for company in TICKERS:
            profit = _get_metric(data, company, year, "net_profit")
            revenue = _get_metric(data, company, year, "net_revenue")
            if profit and revenue:
                value = net_profit_margin(profit["value"], revenue["value"])
                rows.append({"ticker": company, "year": year, "metric_id": "net_profit_margin", "value": value,
                             "unit": "percent", "source_file": profit["source_file"],
                             "source_page": profit["source_page"], "validation_status": "valid"})
        if rows:
            present = {row["ticker"] for row in rows}
            missing = [company for company in TICKERS if company not in present]
            if is_vi:
                lead = f"So sánh một phần biên lợi nhuận ròng năm {year}; chưa có dữ liệu hợp lệ cho {', '.join(missing)}: " if missing else f"Biên lợi nhuận ròng năm {year}: "
            else:
                lead = f"Partial net profit margin comparison for {year}; validated data unavailable for {', '.join(missing)}: " if missing else f"Net profit margin comparison for {year}: "
            return _answer(lead + "; ".join(f"{row['ticker']} {row['value']:.2f}%" for row in rows), rows,
                           formula="net profit / net revenue × 100")

    if ticker and year and ("cover" in q or "đủ" in q) and any(term in q for term in ("capital expenditure", "capex", "chi đầu tư")):
        cash_flow = _get_metric(data, ticker, year, "operating_cash_flow")
        capex = _get_metric(data, ticker, year, "capital_expenditure")
        if cash_flow and capex:
            covered = cash_flow["value"] >= abs(capex["value"])
            answer = f"{ticker}'s operating cash flow {'covered' if covered else 'did not cover'} capital expenditure in {year}."
            if is_vi:
                answer = f"Dòng tiền kinh doanh của {ticker} {'đủ' if covered else 'không đủ'} bù chi đầu tư năm {year}."
            return _answer(answer, [cash_flow, capex], formula="operating cash flow ≥ absolute capital expenditure")

    if compare and year and metric_id:
        rows = compare_companies(data, year, metric_id, allow_derived=(metric_id == "net_revenue"))
        if rows:
            available = {row["ticker"] for row in rows}
            missing = [company for company in TICKERS if company not in available]
            lead = f"Validated {metric_id} values for {year}: " if not missing else f"Partial comparison for {year}; unavailable for {', '.join(missing)}: "
            return _answer(lead + "; ".join(f"{row['ticker']} {row['value']:,.0f}" for row in rows), rows)

    derived = None
    denominator_id = None
    if "margin" in q or "biên lợi nhuận" in q:
        derived, metric_id, denominator_id = net_profit_margin, "net_profit", "net_revenue"
    elif "roe" in q or "return on equity" in q:
        derived, metric_id, denominator_id = roe, "net_profit", "total_equity"
    if derived and ticker and year:
        numerator = _get_metric(data, ticker, year, metric_id)
        denominator = _get_metric(data, ticker, year, denominator_id)
        if numerator and denominator:
            value = derived(numerator["value"], denominator["value"])
            if value is not None:
                return _answer(f"{ticker} {year}: {value:.2f}% (deterministic calculation).", [numerator, denominator],
                               formula=f"{metric_id} / {denominator_id} × 100")

    if "growth" in q or "tăng trưởng" in q:
        metric_id = "net_revenue" if "revenue" in q or "doanh thu" in q else "net_profit"
        if ticker and len(years) >= 2:
            current_year, previous_year = max(years), min(years)
            current = _get_metric(data, ticker, current_year, metric_id)
            previous = _get_metric(data, ticker, previous_year, metric_id)
            if current and previous:
                value = growth(current["value"], previous["value"])
                if value is not None:
                    return _answer(f"{ticker} {metric_id} growth from {previous_year} to {current_year}: {value:.2f}%.",
                                   [previous, current], formula="(current - previous) / previous × 100")

    if ticker and year and metric_id:
        row = _get_metric(data, ticker, year, metric_id)
        if row:
            name = row.get("metric_name_vi", metric_id) if is_vi else row.get("metric_name_en", metric_id.replace("_", " "))
            value_text = f"{row['value']:,.0f} {row.get('currency', 'VND')}"
            evidence = [row]
            formula = None
            qualifier = ""
            if row.get("validation_status") == "derived" and metric_id == "net_revenue":
                sales = get_financial_metric(data, ticker, year, "gross_sales", require_valid=False)
                deductions = get_financial_metric(data, ticker, year, "revenue_deductions", require_valid=False)
                evidence.extend(item for item in (sales, deductions) if item)
                formula = "gross sales − revenue deductions"
                qualifier = " (calculated from the statement's sales and deduction rows)" if not is_vi else " (đã tính từ doanh thu bán hàng trừ khoản giảm trừ)"
            answer = f"{ticker} năm {year}, {name}: {value_text}{qualifier}." if is_vi else f"{ticker} {year} {name}: {value_text}{qualifier}."
            return _answer(answer, evidence, formula=formula)
        return _answer(_missing_metric(metric_id, year, is_vi))

    if metric_id or any(term in q for term in ("revenue", "doanh thu", "net profit", "financial statement", "lợi nhuận")):
        return _answer(
            "Please specify a company and year. Financial values are answered only from validated structured data."
            if not is_vi else "Vui lòng nêu công ty và năm. Số liệu tài chính chỉ được trả lời từ dữ liệu có cấu trúc đã xác thực."
        )

    hits = search_financial_notes(question, ticker=ticker, year=year, root=data_root)
    if hits:
        return _answer(
            "Relevant report excerpts found. These are source passages, not a generated conclusion."
            if not is_vi else "Đã tìm thấy trích đoạn liên quan trong báo cáo; đây là nội dung nguồn, không phải kết luận được tạo tự động.",
            hits,
        )
    return _answer(
        "No sufficiently relevant, readable report passage was found. Try a more specific question or review the source PDF."
        if not is_vi else "Không tìm thấy đoạn văn đủ liên quan và dễ đọc. Hãy thử câu hỏi cụ thể hơn hoặc kiểm tra PDF gốc."
    )
