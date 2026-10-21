from pathlib import Path
import sys

# Streamlit may put only app/ on sys.path when launched from another directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.agent.agent import answer_question
from src.retrieval.structured import load_metrics


st.set_page_config(page_title="Vietnam Financial Intelligence", page_icon="🇻🇳", layout="centered")
st.title("🇻🇳 Vietnam Financial Intelligence & Research Agent")
language = st.radio("Language / Ngôn ngữ", ["English", "Tiếng Việt"], horizontal=True)
company = st.selectbox("Company filter / Bộ lọc công ty", ["All", "FPT", "VNM", "HPG"])
question = st.text_area(
    "Question / Câu hỏi",
    placeholder="What was HPG's revenue in 2023?",
)

if st.button("Analyze / Phân tích", type="primary"):
    if not question.strip():
        st.error("Enter a question first.")
    else:
        metrics_path = PROJECT_ROOT / "data" / "processed" / "financial_metrics.csv"
        data = load_metrics(metrics_path)
        if data.empty:
            st.error("No processed financial data found. Run `python -m src.ingestion.preprocess` first.")
        else:
            result = answer_question(
                question,
                data,
                language,
                data_root=PROJECT_ROOT / "data" / "processed",
                scope_ticker=None if company == "All" else company,
            )
            st.subheader("Answer / Trả lời")
            st.write(result["answer"])
            if result.get("formula"):
                st.caption(f"Formula / Công thức: {result['formula']}")

            evidence = result.get("evidence", [])
            if evidence:
                st.subheader("Source evidence / Bằng chứng nguồn")
                for index, item in enumerate(evidence, start=1):
                    if "metric_id" in item:
                        if item.get("unit") == "percent":
                            amount = f"{item['value']:.2f}%"
                        else:
                            amount = f"{item['value']:,.0f} {item.get('currency', 'VND')}"
                        name = item.get("metric_name_en", item["metric_id"].replace("_", " "))
                        st.markdown(f"**{item['ticker']} · {item['year']} · {name}: {amount}**")
                        st.caption(
                            f"Source: {item.get('source_file', '')}, page {item.get('source_page', '?')} · "
                            f"validation: {item.get('validation_status', 'unverified')}"
                        )
                    else:
                        label = f"{item['ticker']} {item['year']} · page {item['source_page']} · {item['source_file']}"
                        with st.expander(label):
                            # Treat OCR output as plain text. Markdown in OCR must not
                            # become huge headings or formatting in the app.
                            st.text(item.get("text", ""))
            else:
                st.info("No source evidence supports this response.")

st.divider()
st.caption(
    "Portfolio research demonstration. Not investment advice. Financial values require review against the cited statements."
)
