from pathlib import Path
import sys

# Streamlit may put only app/ on sys.path when launched from another directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.agent.agent import answer_question, detect_language
from src.retrieval.structured import load_metrics, load_report_metadata


@st.cache_data(show_spinner=False)
def cached_metrics(path, modified):
    return load_metrics(path)

@st.cache_data(show_spinner=False)
def cached_report_metadata(path, modified):
    return load_report_metadata(path)

def display_derivation(value, is_vi=False):
    labels = {
        "gross_sales - revenue_deductions": "calculated as sales less revenue deductions",
        "carried forward from the previous statement page": "shown as brought forward from the preceding statement page",
    }
    if is_vi:
        labels = {
            "gross_sales - revenue_deductions": "được tính bằng doanh thu bán hàng trừ các khoản giảm trừ",
            "carried forward from the previous statement page": "được chuyển từ trang báo cáo liền trước",
        }
    return labels.get(str(value), str(value).replace("_", " ")) if value else None


st.set_page_config(page_title="Vietnam Financial Intelligence", page_icon="🇻🇳", layout="wide")
st.title("🇻🇳 Vietnam Financial Intelligence & Research Agent")
metrics_path = PROJECT_ROOT / "data" / "processed" / "financial_metrics.csv"
metadata_path = PROJECT_ROOT / "data" / "metadata" / "reports.csv"
metrics_mtime = metrics_path.stat().st_mtime_ns if metrics_path.exists() else 0
metadata_mtime = metadata_path.stat().st_mtime_ns if metadata_path.exists() else 0
data = cached_metrics(str(metrics_path), metrics_mtime)
report_metadata = cached_report_metadata(str(metadata_path), metadata_mtime)
language = st.radio(
    "Answer language / Ngôn ngữ trả lời",
    ["Auto (match question)", "English", "Tiếng Việt"],
    horizontal=True,
    help="Mặc định, câu trả lời dùng cùng ngôn ngữ với câu hỏi. Chọn English hoặc Tiếng Việt để ghi đè. / By default, answers match the question language. Choose English or Tiếng Việt to override.",
)
companies = sorted(data.ticker.dropna().astype(str).str.upper().unique()) if not data.empty else []
company = st.selectbox("Company filter / Bộ lọc công ty", ["All", *companies])
question = st.text_area(
    "Question / Câu hỏi",
    placeholder="What was HPG's revenue in 2023?",
)

if st.button("Analyze / Phân tích", type="primary"):
    is_vi = (detect_language(question) == "Tiếng Việt"
             if language == "Auto (match question)" else language == "Tiếng Việt")
    if not question.strip():
        st.error("Vui lòng nhập câu hỏi." if is_vi else "Enter a question first.")
    else:
        if data.empty:
            st.error("Không tìm thấy dữ liệu tài chính đã xử lý. Hãy chạy `python -m src.ingestion.preprocess`." if is_vi else "No processed financial data found. Run `python -m src.ingestion.preprocess` first.")
        else:
            result = answer_question(
                question,
                data,
                None if language == "Auto (match question)" else language,
                data_root=PROJECT_ROOT / "data" / "processed",
                scope_ticker=None if company == "All" else company,
            )
            st.subheader("Answer / Trả lời")
            if language == "Auto (match question)":
                detected = "Tiếng Việt" if is_vi else "English"
                st.caption(f"Ngôn ngữ trả lời: {detected} (tự nhận diện từ câu hỏi)." if is_vi else f"Answer language: {detected} (detected from the question).")
            st.write(result["answer"])
            evidence = result.get("evidence", [])
            if any(item.get("validation_status") in {"warning", "error"} for item in evidence):
                st.warning("Đối chiếu số học phát hiện chênh lệch ở một hoặc nhiều dòng. Hãy kiểm tra trang báo cáo và chi tiết xác thực." if is_vi else "An arithmetic cross-check found a discrepancy in one or more rows. Review the cited report pages and validation details before using this result.")
            elif any(item.get("validation_status") == "unverified" for item in evidence):
                st.caption("Một số dòng nguồn chưa có đủ dữ liệu để đối chiếu số học; trích dẫn báo cáo được hiển thị bên dưới." if is_vi else "Some source rows do not have a complete equation available for an arithmetic cross-check; their report citations are shown below.")
            elif any(item.get("derivation") for item in evidence):
                st.info("Kết quả được tính từ các chỉ tiêu trong báo cáo. Công thức và các dòng dữ liệu đóng góp được hiển thị bên dưới." if is_vi else "The result is calculated from report line items. The formula and all contributing source rows are shown below.")
            if result.get("formula"):
                formula = result["formula"]
                if is_vi:
                    formula_labels = {
                        "gross sales − revenue deductions": "Doanh thu bán hàng − các khoản giảm trừ doanh thu",
                        "net profit divided by net revenue × 100": "Lợi nhuận sau thuế / doanh thu thuần × 100",
                        "net profit divided by average opening and closing total equity × 100": "Lợi nhuận sau thuế / vốn chủ sở hữu bình quân đầu kỳ và cuối kỳ × 100",
                        "net profit divided by average opening and closing equity × 100": "Lợi nhuận sau thuế / vốn chủ sở hữu bình quân đầu kỳ và cuối kỳ × 100",
                        "(current-period value − prior-period value) / prior-period value × 100": "(Giá trị kỳ này − giá trị kỳ trước) / giá trị kỳ trước × 100",
                        "(current − previous) / previous × 100": "(Giá trị kỳ này − giá trị kỳ trước) / giá trị kỳ trước × 100",
                        "current-period value − prior-period value; percentage change = difference / prior-period value × 100": "Mức thay đổi = giá trị kỳ này − giá trị kỳ trước; tỷ lệ thay đổi = mức thay đổi / giá trị kỳ trước × 100",
                        "current − previous) / previous × 100": "(Giá trị kỳ này − giá trị kỳ trước) / giá trị kỳ trước × 100",
                        "operating cash flow ≥ absolute capital expenditure": "Dòng tiền kinh doanh ≥ giá trị tuyệt đối của chi đầu tư",
                    }
                    formula = formula_labels.get(formula, formula)
                st.caption(f"{'Công thức' if is_vi else 'Formula'}: {formula}")

            if evidence:
                st.subheader("Bằng chứng nguồn" if is_vi else "Source evidence")
                for index, item in enumerate(evidence, start=1):
                    if "metric_id" in item:
                        if item.get("unit") == "percent":
                            amount = f"{item['value']:.2f}%"
                        else:
                            amount = f"{item['value']:,.0f} {item.get('currency', 'VND')}"
                        name = item.get("metric_name_vi" if is_vi else "metric_name_en", item["metric_id"].replace("_", " "))
                        if name and name.isupper():
                            name = name.capitalize() if is_vi else name.title()
                        st.markdown(f"**{item['ticker']} · {item['year']} · {name}: {amount}**")
                        status = item.get("validation_status", "unverified")
                        check_label = {
                            "valid": "đã đối chiếu số học" if is_vi else "arithmetic cross-check passed",
                            "unverified": "chưa đủ dữ liệu để đối chiếu số học" if is_vi else "no complete arithmetic cross-check",
                            "derived": "được tính từ các chỉ tiêu trong báo cáo" if is_vi else "calculated from reported line items",
                            "warning": "có chênh lệch số học; cần kiểm tra" if is_vi else "arithmetic discrepancy; review required",
                            "error": "đối chiếu số học không đạt" if is_vi else "arithmetic check failed",
                        }.get(status, status)
                        derivation = display_derivation(item.get("derivation"), is_vi)
                        detail = f" · {derivation}" if derivation else ""
                        metadata = report_metadata.get((str(item.get("ticker", "")).upper(), str(int(item.get("year")))))
                        source_url = metadata.get("source_url") if metadata else None
                        source_type = metadata.get("source_url_type") if metadata else None
                        if source_url:
                            source_label = (("Danh sách bên thứ ba (tìm theo mã và năm)" if is_vi else "Third-party listings (search ticker and year)") if source_type == "third_party_listing" else ("Trang công bố báo cáo" if is_vi else "Report publisher source"))
                            source_ref = f"[{source_label}]({source_url})"
                        else:
                            source_ref = "Chưa ghi nhận liên kết nguồn báo cáo" if is_vi else "Report source link not recorded"
                        page = item.get("source_page") or "?"
                        st.markdown(
                            f"{'Nguồn' if is_vi else 'Source'}: {source_ref} · {'trang báo cáo' if is_vi else 'report page'} {page} · {check_label}{detail}"
                        )
                    else:
                        metadata = report_metadata.get((str(item.get("ticker", "")).upper(), str(int(item.get("year")))))
                        source_url = metadata.get("source_url") if metadata else None
                        source_label = (("Danh sách bên thứ ba (tìm theo mã và năm)" if is_vi else "Third-party listings (search ticker and year)") if metadata and metadata.get("source_url_type") == "third_party_listing" else ("Nguồn báo cáo" if is_vi else "Report source"))
                        title = f"[{source_label}]({source_url})" if source_url else source_label
                        label = f"{item['ticker']} {item['year']} · {'trang' if is_vi else 'page'} {item['source_page']} · {title}"
                        with st.expander(label):
                            # Treat OCR output as plain text. Markdown in OCR must not
                            # become huge headings or formatting in the app.
                            st.text(item.get("text", ""))
st.divider()
st.caption("Bản minh họa nghiên cứu, không phải tư vấn đầu tư. Báo cáo được ghi nhận là đã kiểm toán trong metadata; đối chiếu phương trình chỉ kiểm tra tính nhất quán và ứng dụng không xác thực độc lập nguồn gốc trên website." if language == "Tiếng Việt" else "Research demonstration, not investment advice. PDFs are marked audited in report metadata; equation checks test consistency, and website provenance is not independently authenticated by the app.")
