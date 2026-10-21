"""Map extracted table labels to canonical metrics; ambiguous values stay flagged."""
import unicodedata
from src.processing.normalization import normalize_number

def _fold(value):
    value=str(value).casefold().replace("đ","d")
    return "".join(c for c in unicodedata.normalize("NFD",value) if unicodedata.category(c)!="Mn")

def _current_year_column(data,year):
    for row_index,row in enumerate(data[:8]):
        for col,cell in enumerate(row):
            value=_fold(cell)
            adjacent=" ".join(_fold(r[col]) for r in data[max(0,row_index-1):min(len(data),row_index+2)] if col<len(r))
            if str(year) in value and any(tag in (value+" "+adjacent) for tag in ("vnd","/","ngay","date")):
                return col
            if "nam nay" in value or "so cuoi nam" in value:
                return col
    return None

METRICS = {
 "cash_and_equivalents": ("Tiền và các khoản tương đương tiền", "Cash and cash equivalents"),
 "opening_cash": ("Tiền và tương đương tiền đầu năm", "Cash and cash equivalents at beginning of year"),
 "closing_cash": ("Tiền và tương đương tiền cuối năm", "Cash and cash equivalents at end of year"),
 "short_term_investments": ("Đầu tư tài chính ngắn hạn", "Short-term financial investments"),
 "accounts_receivable": ("Các khoản phải thu", "Accounts receivable"),
 "inventory": ("Hàng tồn kho", "Inventories"), "current_assets": ("Tài sản ngắn hạn", "Current assets"),
 "noncurrent_assets": ("Tài sản dài hạn", "Non-current assets"),
 "total_assets": ("TỔNG CỘNG TÀI SẢN", "Tổng tài sản", "TOTAL ASSETS"),
 "current_liabilities": ("Nợ ngắn hạn", "Current liabilities"),
 "short_term_borrowings": ("Vay và nợ thuê tài chính ngắn hạn", "Vay ngắn hạn", "Short-term borrowings"),
 "long_term_borrowings": ("Vay và nợ thuê tài chính dài hạn", "Vay dài hạn", "Long-term borrowings"),
 "total_liabilities": ("TỔNG CỘNG NỢ PHẢI TRẢ", "Nợ phải trả", "TOTAL LIABILITIES"),
 "total_equity": ("VỐN CHỦ SỞ HỮU", "TOTAL EQUITY"),
 "charter_capital": ("Vốn góp của chủ sở hữu", "Share capital"), "retained_earnings": ("Lợi nhuận sau thuế chưa phân phối", "Undistributed earnings"),
 "gross_sales": ("Doanh thu bán hàng và cung cấp", "Revenue from sales of goods and rendering services"),
 "revenue_deductions": ("Các khoản giảm trừ doanh thu", "Revenue deductions"),
 "net_revenue": ("Doanh thu thuần", "Net revenue"), "cost_of_goods_sold": ("Giá vốn hàng bán", "Cost of goods sold"),
 "gross_profit": ("Lợi nhuận gộp", "Gross profit"), "operating_profit": ("Lợi nhuận thuần từ hoạt động kinh doanh", "Operating profit"),
 "financial_income": ("Doanh thu hoạt động tài chính", "Financial income"), "financial_expenses": ("Chi phí tài chính", "Financial expenses"),
 "profit_before_tax": ("Lợi nhuận kế toán trước thuế", "Profit before tax"),
 "net_profit": ("Lợi nhuận sau thuế thu nhập doanh nghiệp", "Lợi nhuận sau thuế TNDN", "Profit after tax"),
 "parent_net_profit": ("Lợi nhuận sau thuế của cổ đông công ty mẹ", "Lợi nhuận sau thuế của chủ sở hữu công ty mẹ", "Profit attributable to owners"),
 "basic_eps": ("Lãi cơ bản trên cổ phiếu", "Basic earnings per share"),
 "operating_cash_flow": ("Lưu chuyển tiền thuần từ hoạt động kinh doanh", "Net cash from operating activities"),
 "investing_cash_flow": ("Lưu chuyển tiền thuần từ hoạt động đầu tư", "Net cash from investing activities"),
 "financing_cash_flow": ("Lưu chuyển tiền thuần từ hoạt động tài chính", "Net cash from financing activities"),
 "capital_expenditure": ("Tiền chi để mua sắm, xây dựng tài sản cố định", "Tiền chi mua sắm tài sản cố định", "Purchase and construction of fixed assets"),
 "net_change_cash": ("Lưu chuyển tiền thuần trong kỳ", "Net increase in cash"),
}

def canonical_rows(tables, *, ticker, company, year, source_file):
    rows=[]
    statement_types={
      "cash_and_equivalents":"balance_sheet","short_term_investments":"balance_sheet","accounts_receivable":"balance_sheet",
      "opening_cash":"cash_flow","closing_cash":"cash_flow",
      "inventory":"balance_sheet","current_assets":"balance_sheet","noncurrent_assets":"balance_sheet","total_assets":"balance_sheet","short_term_borrowings":"balance_sheet",
      "long_term_borrowings":"balance_sheet","total_liabilities":"balance_sheet","total_equity":"balance_sheet","charter_capital":"balance_sheet",
      "retained_earnings":"balance_sheet","gross_sales":"income_statement","revenue_deductions":"income_statement",
      "net_revenue":"income_statement","cost_of_goods_sold":"income_statement","gross_profit":"income_statement",
      "operating_profit":"income_statement","financial_income":"income_statement","financial_expenses":"income_statement","profit_before_tax":"income_statement",
      "net_profit":"income_statement","parent_net_profit":"income_statement","basic_eps":"income_statement","operating_cash_flow":"cash_flow",
      "investing_cash_flow":"cash_flow","financing_cash_flow":"cash_flow","capital_expenditure":"cash_flow","net_change_cash":"cash_flow"}
    target=str(year)
    by_page={}
    for table in tables:
      page=int(table.get("source_page",999))
      if page<=14: by_page.setdefault(page,[]).append(table)
    page_columns={}
    for page,page_tables in by_page.items():
      current_col=None; header_width=None
      for table in page_tables:
        current_col=_current_year_column(table.get("data",[]),year)
        if current_col is not None:
          header_width=max(map(len,table.get("data",[])[:8]),default=0); break
        if current_col is not None: break
      if current_col is not None: page_columns[page]=(current_col,header_width)
    for table in tables:
      page=int(table.get("source_page",999))
      # Note pages repeat statement labels with unrelated dimensions. These audited
      # consolidated statements occupy the first fourteen report pages.
      if page not in page_columns: continue
      data=table.get("data",[])
      local_col=_current_year_column(data,year)
      if local_col is None:
        base_col,header_width=page_columns[page]
        local_width=max(map(len,data),default=header_width)
        # img2table often omits the leftmost description column from a detached header.
        # The body adds that one label column; further width differences are usually OCR
        # artifacts or blank trailing columns and must not shift into a comparative year.
        value_col=base_col+(1 if local_width>(header_width or local_width) else 0)
      else:
        value_col=local_col
      for cells in data:
        if value_col>=len(cells): continue
        value_lines=[line.strip() for line in str(cells[value_col]).splitlines()]
        if not value_lines: continue
        for label_col,cell in enumerate(cells):
          if label_col==value_col: continue
          label_lines=[line.strip() for line in str(cell).splitlines()]
          matched=[]
          for index,label in enumerate(label_lines):
            folded=_fold(label)
            candidates=[(key,pair) for key,pair in METRICS.items() if any(_fold(alias) in folded for alias in pair)]
            unique={key:pair for key,pair in candidates}
            if len(unique)==1: matched.append((index,label,next(iter(unique.items()))))
          if len(label_lines)==len(value_lines):
            aligned=[(label_index,label,candidate,value_lines[label_index]) for label_index,label,candidate in matched]
          elif len(value_lines)==1 and len(matched)==1:
            # Some reports split a heading/formula over two lines but keep one amount.
            aligned=[(matched[0][0],matched[0][1],matched[0][2],value_lines[0])]
          else:
            continue
          for index,label,(key,aliases),raw_value in aligned:
            folded=_fold(label); vi,en=aliases[0],aliases[-1]
            # Generic equity wording also appears in reserve/retained-earnings labels;
            # require the actual statement heading for total equity.
            if key=="total_equity" and not folded.strip().startswith(("von chu so huu","total equity")):
              continue
            if key=="current_assets" and ("khac" in folded or not folded.strip().startswith(("tai san ngan han","current assets"))): continue
            if key=="noncurrent_assets" and ("khac" in folded or not folded.strip().startswith(("tai san dai han","non-current assets"))): continue
            if key=="inventory" and ("du phong" in folded or not folded.strip().startswith(("hang ton kho","inventories"))): continue
            if key=="accounts_receivable" and ("dai han" in folded or "long-term" in folded): continue
            if key=="total_liabilities" and not folded.strip().startswith(("no phai tra","total liabilities")): continue
            if key=="total_assets" and not folded.strip().startswith(("tong tai san","tong cong tai san","total assets")): continue
            result=normalize_number(raw_value)
            if result.value is None: continue
            rows.append({"company":company,"ticker":ticker,"year":year,"statement_type":statement_types.get(key,"unknown"),
              "metric_id":key,"metric_name_vi":vi,"metric_name_en":en,"value":result.value,
              "currency":"VND","unit":"as_reported","source_file":source_file,
              "source_page":page,"validation_status":"unverified"})
    # Derive net revenue only when the statement's sales and deduction amounts
    # were both extracted independently and the direct net-revenue cell is absent.
    by_metric = {}
    for row in rows:
      by_metric.setdefault(row["metric_id"], row)
    sales = by_metric.get("gross_sales")
    deductions = by_metric.get("revenue_deductions")
    if "net_revenue" not in by_metric and sales and deductions:
      rows.append({**sales,
        "metric_id":"net_revenue",
        "metric_name_vi":"Doanh thu thuần",
        "metric_name_en":"Net revenue",
        "value":sales["value"]-deductions["value"],
        "source_page":sales["source_page"],
        "validation_status":"derived",
        "derivation":"gross_sales - revenue_deductions"})
    # Multiple tables may repeat a metric in notes. Keep the earliest statement occurrence.
    deduped=[]; seen=set()
    for row in sorted(rows,key=lambda r:r["source_page"]):
      key=(row["ticker"],row["year"],row["metric_id"])
      if key not in seen: deduped.append(row); seen.add(key)
    return deduped
