"""Small bilingual intent router; all numbers come from reviewed rows/calculations."""
import re
import unicodedata

from src.finance.metrics import average_balance, growth, net_profit_margin, roe
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

METRIC_LABELS = {
    "total_assets": ("total assets", "tổng tài sản"),
    "total_equity": ("total equity", "vốn chủ sở hữu"),
    "net_revenue": ("net revenue", "doanh thu thuần"),
    "net_profit": ("net profit after tax", "lợi nhuận sau thuế"),
    "operating_cash_flow": ("operating cash flow", "lưu chuyển tiền từ hoạt động kinh doanh"),
    "capital_expenditure": ("capital expenditure", "chi đầu tư tài sản cố định"),
}


def _metric_label(metric_id, is_vi=False):
    labels = METRIC_LABELS.get(metric_id)
    return labels[1 if is_vi else 0] if labels else metric_id.replace("_", " ")


def _answer(text, evidence=None, **extra):
    return {"answer": text, "evidence": evidence or [], **extra}


def _missing_metric(metric_id, year, is_vi, inferred_year=False):
    label = _metric_label(metric_id, is_vi)
    if is_vi:
        period = f" năm mới nhất có dữ liệu ({year})" if inferred_year else f" năm {year}"
        return f"Không tìm thấy số liệu {label}{period} trong dữ liệu đã trích xuất. Hãy kiểm tra trang báo cáo hoặc bảng đã nhận dạng; ứng dụng không suy ra số liệu từ đoạn văn."
    period = f"the latest available year ({year})" if inferred_year else str(year)
    return f"No extracted {label} value is available for {period}. Review the report page or extracted table; narrative text is not used to supply financial figures."


def _get_metric(data, ticker, year, metric_id):
    return get_financial_metric(
        data, ticker, year, metric_id,
        allow_derived=(metric_id == "net_revenue"),
        allow_unverified=True,
    )


def _expand_evidence(data, rows):
    evidence = []
    seen = set()
    for row in rows:
        if not row:
            continue
        key = (row.get("ticker"), row.get("year"), row.get("metric_id"), row.get("source_page"))
        if key not in seen:
            evidence.append(row)
            seen.add(key)
        if row.get("metric_id") == "net_revenue" and row.get("derivation"):
            for component in ("gross_sales", "revenue_deductions"):
                source = get_financial_metric(
                    data, row["ticker"], row["year"], component, require_valid=False
                )
                if source:
                    source_key = (source.get("ticker"), source.get("year"), source.get("metric_id"), source.get("source_page"))
                    if source_key not in seen:
                        evidence.append(source)
                        seen.add(source_key)
    return evidence


def _fold_text(value):
    value = str(value).casefold().replace("đ", "d")
    return "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def detect_language(text):
    """Detect Vietnamese from accents and common unaccented Vietnamese finance terms."""
    value = str(text or "").casefold()
    decomposed = unicodedata.normalize("NFD", value)
    if "đ" in value or any(unicodedata.category(char) == "Mn" for char in decomposed):
        return "Tiếng Việt"
    folded = _fold_text(value)
    vietnamese_terms = (
        "so sanh", "doanh thu", "tong tai san", "loi nhuan", "bien loi nhuan",
        "bao nhieu", "dong tien", "von chu so huu", "nam nao", "tang truong",
    )
    if any(re.search(rf"\b{re.escape(term)}\b", folded) for term in vietnamese_terms):
        return "Tiếng Việt"
    return "English"


def answer_question(question, data, language=None, data_root="data/processed", scope_ticker=None):
    q = question.casefold()
    dataset_tickers = sorted(data.ticker.dropna().astype(str).str.upper().unique()) if not data.empty else []
    mentioned_tickers = [ticker for ticker in dataset_tickers if re.search(rf"\b{re.escape(ticker.casefold())}\b", q)]
    ticker = mentioned_tickers[0] if mentioned_tickers else (scope_ticker.upper() if scope_ticker else None)
    selected_language = language or "Auto"
    is_vi = (
        detect_language(question) == "Tiếng Việt"
        if selected_language.casefold() in {"auto", "automatic", "match question"}
        else selected_language.casefold().startswith(("tiếng", "vietnamese", "vi"))
    )
    years = [int(year) for year in re.findall(r"20\d\d", q)]
    year = years[-1] if years else None

    if scope_ticker:
        scope_ticker = scope_ticker.upper()
        conflicting = [name for name in mentioned_tickers if name != scope_ticker]
        if conflicting or (len(mentioned_tickers) > 1 and any(name != scope_ticker for name in mentioned_tickers)):
            return _answer(
                f"Bộ lọc đang chọn {scope_ticker}, nhưng câu hỏi đề cập {', '.join(mentioned_tickers)}. Hãy chọn Tất cả hoặc công ty phù hợp."
                if is_vi else f"The selected company filter is {scope_ticker}, but the question asks about {', '.join(mentioned_tickers)}. Select All or choose a matching company."
            )
        data = data[data.ticker.astype(str).str.upper() == scope_ticker] if not data.empty else data

    if any(term in q for term in ("stock price", "share price", "giá cổ phiếu")):
        return _answer(
            "Stock-price data is not included in the project's financial-statement dataset."
            if not is_vi else "Bộ dữ liệu báo cáo tài chính của dự án không bao gồm giá cổ phiếu."
        )
    if data.empty:
        return _answer("Không tìm thấy dữ liệu tài chính đã xử lý. Hãy chạy `python -m src.ingestion.preprocess`." if is_vi else "No processed financial data found. Run `python -m src.ingestion.preprocess` first.")

    available_years = sorted(data.year.dropna().astype(int).unique())
    compare = any(word in q for word in ("compare", "so sánh"))
    rank_query = any(term in q for term in ("which company", "highest", "lowest", "cao nhất", "thấp nhất"))
    metric_id = next((value for key, value in sorted(ALIASES.items(), key=lambda item: -len(item[0])) if key in q), None)
    inferred_year = False
    if year is None and available_years and (ticker or compare or rank_query) and metric_id:
        year = max(available_years)
        inferred_year = True
    if year and year not in available_years:
        years_label = ", ".join(map(str, available_years)) or ("không có" if is_vi else "none")
        return _answer(
            f"{year} is not present in this dataset. Available years: {years_label}."
            if not is_vi else f"Không có dữ liệu năm {year}. Các năm hiện có: {years_label}."
        )

    if (compare or rank_query) and scope_ticker and len(dataset_tickers) > 1:
        return _answer(f"Hãy chọn Tất cả để so sánh nhiều công ty; bộ lọc hiện tại là {scope_ticker}." if is_vi else f"Select All to compare multiple companies; the current filter is {scope_ticker}.")
    if (compare or rank_query) and len(dataset_tickers) < 2:
        return _answer("Cần ít nhất hai công ty trong dữ liệu để so sánh." if is_vi else "A company comparison needs at least two companies in the loaded dataset.")

    if (compare or rank_query) and year and ("margin" in q or "biên lợi nhuận" in q):
        comparison_tickers = (
            mentioned_tickers if len(mentioned_tickers) > 1 else dataset_tickers
        )
        rows = []
        for company in comparison_tickers:
            profit = _get_metric(data, company, year, "net_profit")
            revenue = _get_metric(data, company, year, "net_revenue")
            if profit and revenue:
                value = net_profit_margin(profit["value"], revenue["value"])
                rows.append({"ticker": company, "year": year, "metric_id": "net_profit_margin", "value": value,
                             "unit": "percent", "source_file": profit["source_file"],
                             "source_page": profit["source_page"],
                             "validation_status": "valid" if profit.get("validation_status") == "valid" and revenue.get("validation_status") == "valid" else "unverified",
                             "derivation": "net_profit / net_revenue × 100"})
        if rows:
            present = {row["ticker"] for row in rows}
            missing = [company for company in comparison_tickers if company not in present]
            if rank_query:
                best = max(rows, key=lambda row: row["value"])
                missing = [company for company in comparison_tickers if company not in {row["ticker"] for row in rows}]
                answer = (
                    f"{best['ticker']} had the highest net profit margin in {year} "
                    f"among companies with available data: {best['value']:.2f}%"
                )
                if missing:
                    answer += f"; data unavailable for {', '.join(missing)}."
                else:
                    answer += "."
                if is_vi:
                    answer = (
                        f"Trong các công ty có dữ liệu, {best['ticker']} có biên lợi nhuận ròng cao nhất "
                        f"năm {year}: {best['value']:.2f}%"
                    )
                    answer += f"; chưa có dữ liệu cho {', '.join(missing)}." if missing else "."
                evidence_rows = [value for company in comparison_tickers for value in (
                    _get_metric(data, company, year, "net_profit"),
                    _get_metric(data, company, year, "net_revenue"),
                ) if value]
                if inferred_year:
                    answer += f" (latest year in the loaded dataset{': ' + str(year) if not is_vi else ', năm mới nhất trong dữ liệu'})."
                return _answer(answer, _expand_evidence(data, evidence_rows),
                               formula="net profit divided by net revenue × 100")
            if is_vi:
                lead = f"So sánh một phần biên lợi nhuận ròng năm {year}; chưa có dữ liệu cho {', '.join(missing)}: " if missing else f"Biên lợi nhuận ròng năm {year}: "
            else:
                lead = f"Partial net profit margin comparison for {year}; data unavailable for {', '.join(missing)}: " if missing else f"Net profit margin comparison for {year}: "
            base_evidence = []
            for company in comparison_tickers:
                base_evidence.extend(
                    value for value in (
                        _get_metric(data, company, year, "net_profit"),
                        _get_metric(data, company, year, "net_revenue"),
                    ) if value
                )
            return _answer(lead + "; ".join(f"{row['ticker']} {row['value']:.2f}%" for row in rows),
                           _expand_evidence(data, base_evidence),
                           formula="net profit divided by net revenue × 100")

    if ticker and year and ("cover" in q or "đủ" in q) and any(term in q for term in ("capital expenditure", "capex", "chi đầu tư")):
        cash_flow = _get_metric(data, ticker, year, "operating_cash_flow")
        capex = _get_metric(data, ticker, year, "capital_expenditure")
        if cash_flow and capex:
            covered = cash_flow["value"] >= abs(capex["value"])
            answer = f"{ticker}'s operating cash flow {'covered' if covered else 'did not cover'} capital expenditure in {year}."
            if is_vi:
                answer = f"Dòng tiền kinh doanh của {ticker} {'đủ' if covered else 'không đủ'} bù chi đầu tư năm {year}."
            if inferred_year:
                answer += f" ({'latest available report year: ' + str(year) if not is_vi else 'năm báo cáo mới nhất có trong dữ liệu'})."
            return _answer(answer, [cash_flow, capex], formula="operating cash flow ≥ absolute capital expenditure")
        missing = [label for label, row in (("dòng tiền kinh doanh" if is_vi else "operating cash flow", cash_flow), ("chi đầu tư" if is_vi else "capital expenditure", capex)) if row is None]
        period = (f"năm mới nhất có dữ liệu ({year})" if is_vi else f"latest available year ({year})") if inferred_year else str(year)
        return _answer(
            f"Không thể xác định dòng tiền kinh doanh có đủ bù chi đầu tư của {ticker} trong {period} hay không; thiếu số liệu: {', '.join(missing)}." if is_vi else f"Cannot assess whether operating cash flow covered capital expenditure for {ticker} in {period}; missing extracted value(s): {', '.join(missing)}.",
            [row for row in (cash_flow, capex) if row],
        )

    if "change" in q or "thay đổi" in q or "changed" in q:
        change_metric = metric_id
        if ticker and change_metric:
            period = years[-2:] if len(years) >= 2 else available_years[-2:]
            if len(period) == 2:
                previous_year, current_year = period
                previous = _get_metric(data, ticker, previous_year, change_metric)
                current = _get_metric(data, ticker, current_year, change_metric)
                if previous and current:
                    delta = current["value"] - previous["value"]
                    pct = growth(current["value"], previous["value"])
                    answer = (
                        f"{ticker}'s {_metric_label(change_metric)} changed by {delta:,.0f} "
                        f"from {previous_year} to {current_year}"
                    )
                    if pct is not None:
                        answer += f" ({pct:+.2f}%)."
                    else:
                        answer += ". The percentage change is undefined because the earlier value is zero."
                    if is_vi:
                        answer = f"{_metric_label(change_metric, True)} của {ticker} thay đổi {delta:,.0f} VND từ năm {previous_year} đến {current_year}"
                        answer += f" ({pct:+.2f}%)." if pct is not None else ". Không thể tính tỷ lệ phần trăm vì giá trị kỳ trước bằng 0."
                    if len(years) < 2:
                        answer += f" ({'latest two available years' if not is_vi else 'hai năm mới nhất có dữ liệu'})."
                    return _answer(answer, _expand_evidence(data, [previous, current]),
                                   formula="current-period value − prior-period value; percentage change = difference / prior-period value × 100")
                if previous or current:
                    return _answer(
                        f"Không thể tính mức thay đổi của {_metric_label(change_metric, True)} của {ticker} từ {previous_year} đến {current_year}; thiếu một hoặc cả hai số liệu báo cáo." if is_vi else f"Cannot calculate the change in {_metric_label(change_metric)} for {ticker} from {previous_year} to {current_year}; one or both report values are missing from the extracted dataset.",
                        _expand_evidence(data, [previous, current]),
                    )

    if ("growth" in q or "tăng trưởng" in q) and compare:
        growth_metric = "net_revenue" if "revenue" in q or "doanh thu" in q else "net_profit"
        comparison_tickers = mentioned_tickers if len(mentioned_tickers) > 1 else dataset_tickers
        period = years[-2:] if len(years) >= 2 else available_years[-2:]
        if len(period) == 2:
            previous_year, current_year = period
            rows, evidence_rows = [], []
            for company in comparison_tickers:
                previous = _get_metric(data, company, previous_year, growth_metric)
                current = _get_metric(data, company, current_year, growth_metric)
                if previous and current:
                    value = growth(current["value"], previous["value"])
                    if value is not None:
                        rows.append((company, value))
                        evidence_rows.extend((previous, current))
            if rows:
                present = {company for company, _ in rows}
                missing = [company for company in comparison_tickers if company not in present]
                period_label = f"{previous_year} to {current_year}"
                metric_label = _metric_label(growth_metric)
                if is_vi:
                    answer = (f"Tăng trưởng {metric_label} {period_label}"
                              + (f"; thiếu dữ liệu đã trích xuất cho {', '.join(missing)}" if missing else "")
                              + ": " + "; ".join(f"{company} {value:.2f}%" for company, value in rows))
                else:
                    answer = (f"{metric_label.title()} growth from {period_label}"
                              + (f"; extracted data unavailable for {', '.join(missing)}" if missing else "")
                              + ": " + "; ".join(f"{company} {value:.2f}%" for company, value in rows))
                if len(years) < 2:
                    answer += f" ({'latest two available years' if not is_vi else 'hai năm mới nhất có dữ liệu'})."
                else:
                    answer += "."
                return _answer(answer, _expand_evidence(data, evidence_rows),
                               formula="(current-period value − prior-period value) / prior-period value × 100")

    if compare and year and metric_id:
        comparison_tickers = mentioned_tickers if len(mentioned_tickers) > 1 else dataset_tickers
        rows = compare_companies(
            data, year, metric_id,
            tickers=comparison_tickers,
            allow_derived=(metric_id == "net_revenue"),
            allow_unverified=True,
        )
        if rows:
            available = {row["ticker"] for row in rows}
            missing = [company for company in comparison_tickers if company not in available]
            provisional = any(row.get("validation_status") != "valid" for row in rows)
            metric_name = metric_id.replace("_", " ").title()
            if missing:
                lead = f"Available {metric_name} values for {year} (missing {', '.join(missing)}): "
            elif provisional:
                lead = f"Reported {metric_name} values for {year}: "
            else:
                lead = f"{metric_name} values for {year} (VND): "
            return _answer(lead + "; ".join(f"{row['ticker']} {row['value']:,.0f}" for row in rows),
                           _expand_evidence(data, rows),
                           formula="gross sales − revenue deductions" if metric_id == "net_revenue" else None)

    derived = None
    denominator_id = None
    if "margin" in q or "biên lợi nhuận" in q:
        derived, metric_id, denominator_id = net_profit_margin, "net_profit", "net_revenue"
    elif "roe" in q or "return on equity" in q:
        derived, metric_id, denominator_id = roe, "net_profit", "total_equity"
    if derived and ticker and year:
        numerator = _get_metric(data, ticker, year, metric_id)
        is_roe = derived is roe
        prior_years = [available_year for available_year in available_years if available_year < year]
        opening_year = max(prior_years) if prior_years else None
        opening_balance = _get_metric(data, ticker, opening_year, denominator_id) if is_roe and opening_year else None
        closing_balance = _get_metric(data, ticker, year, denominator_id)
        denominator = (
            average_balance(opening_balance["value"], closing_balance["value"])
            if is_roe and opening_balance and closing_balance
            else (closing_balance["value"] if closing_balance else None)
        )
        if numerator and denominator:
            value = derived(numerator["value"], denominator)
            if value is not None:
                evidence_rows = [numerator, closing_balance]
                if is_roe and opening_balance:
                    evidence_rows.append(opening_balance)
                formula = (
                    "net profit divided by average opening and closing total equity × 100"
                    if is_roe else "net profit divided by net revenue × 100"
                )
                label = "ROE" if is_roe else "net profit margin"
                return _answer(f"{ticker} {year} {label}: {value:.2f}%.",
                               _expand_evidence(data, evidence_rows), formula=formula)
            return _answer(
            f"Cannot calculate {('ROE' if is_roe else 'net profit margin')} for {ticker} in {year}; denominator is zero.",
                [numerator, closing_balance],
                formula=("net profit divided by average opening and closing equity × 100" if is_roe else "net profit divided by net revenue × 100"),
            )
        missing = [name for name, row in ((metric_id, numerator), (denominator_id, closing_balance)) if row is None]
        if is_roe and opening_balance is None:
            missing.append(f"prior-year {denominator_id}")
        evidence = [row for row in (numerator, opening_balance, closing_balance) if row]
        label = "ROE" if is_roe else "net profit margin"
        return _answer(
            f"Cannot calculate {label} for {ticker} in {year}; missing extracted value(s): {', '.join(missing)}.",
            evidence,
            formula=("net profit divided by average opening and closing total equity × 100" if is_roe else "net profit divided by net revenue × 100"),
        )

    if "growth" in q or "tăng trưởng" in q:
        metric_id = "net_revenue" if "revenue" in q or "doanh thu" in q else "net_profit"
        if ticker and len(years) >= 2:
            previous_year, current_year = years[-2], years[-1]
            current = _get_metric(data, ticker, current_year, metric_id)
            previous = _get_metric(data, ticker, previous_year, metric_id)
            if current and previous:
                value = growth(current["value"], previous["value"])
                if value is not None:
                    metric_name = metric_id.replace("_", " ")
                    return _answer(f"{ticker} {metric_name} growth from {previous_year} to {current_year}: {value:.2f}%.",
                                   _expand_evidence(data, [previous, current]), formula="(current − previous) / previous × 100")

    if ticker and year and metric_id:
        row = _get_metric(data, ticker, year, metric_id)
        if row:
            name = row.get("metric_name_vi", metric_id) if is_vi else row.get("metric_name_en", metric_id.replace("_", " "))
            if name and name.isupper():
                name = name.capitalize() if is_vi else name.title()
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
            return _answer(answer, _expand_evidence(data, evidence), formula=formula)
        return _answer(_missing_metric(metric_id, year, is_vi, inferred_year))

    if metric_id or any(term in q for term in ("revenue", "doanh thu", "net profit", "financial statement", "lợi nhuận")):
        return _answer(
            "Please specify a company and year. Financial figures are answered from cited report rows or explicitly shown calculations."
            if not is_vi else "Vui lòng nêu công ty và năm. Số liệu tài chính chỉ được trả lời từ dữ liệu có cấu trúc đã xác thực."
        )

    hits = search_financial_notes(question, ticker=ticker, year=year, root=data_root)
    if hits:
        if ticker == "HPG" and any(term in q for term in ("segment", "business line", "bộ phận", "phân khúc")):
            source_text = _fold_text(" ".join(hit["text"] for hit in hits))
            segments = []
            if "thep" in source_text:
                segments.append("sản xuất và kinh doanh thép" if is_vi else "steel production and trading")
            if "nong nghiep" in source_text or "nongnghiep" in source_text:
                segments.append("nông nghiệp" if is_vi else "agriculture")
            if "bat dong san" in source_text:
                segments.append("bất động sản" if is_vi else "real estate")
            if segments:
                answer = ("Các lĩnh vực kinh doanh chính gồm " if is_vi else "The report lists these business segments: ")
                return _answer(answer + "; ".join(segments) + ".", hits)
        return _answer(
            "Relevant report excerpts found. These are source passages, not a generated conclusion."
            if not is_vi else "Đã tìm thấy trích đoạn liên quan trong báo cáo; đây là nội dung nguồn, không phải kết luận được tạo tự động.",
            hits,
        )
    risk_question = bool(re.search(r"\b(risks?|risk factors?|rui ro|nguy co)\b", _fold_text(question)))
    if risk_question:
        return _answer(
            "The loaded report text does not contain a sufficiently specific risk-disclosure passage. Search surfaced incidental uses of “risk” in accounting notes, which are not enough to identify HPG's disclosed risk factors. Check the full annual report's risk management or principal risks section."
            if not is_vi else "Trong phần văn bản báo cáo đã nạp, không tìm thấy đoạn công bố rủi ro đủ cụ thể. Tìm kiếm chỉ thấy các lần nhắc tình cờ đến “rủi ro” trong thuyết minh kế toán, chưa đủ căn cứ để xác định các rủi ro HPG công bố. Hãy kiểm tra mục quản trị rủi ro hoặc các rủi ro trọng yếu trong báo cáo thường niên đầy đủ."
        )
    return _answer(
        "No sufficiently relevant, readable report passage was found. Try a more specific question or review the source PDF."
        if not is_vi else "Không tìm thấy đoạn văn đủ liên quan và dễ đọc. Hãy thử câu hỏi cụ thể hơn hoặc kiểm tra PDF gốc."
    )
