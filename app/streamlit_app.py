import streamlit as st
from src.retrieval.structured import load_metrics
from src.agent.agent import answer_question

st.set_page_config(page_title="Vietnam Financial Intelligence", page_icon="🇻🇳", layout="centered")
st.title("🇻🇳 Vietnam Financial Intelligence & Research Agent")
language=st.radio("Language / Ngôn ngữ",["English","Tiếng Việt"],horizontal=True)
company=st.selectbox("Company / Công ty",["All","FPT","VNM","HPG"])
question=st.text_area("Question / Câu hỏi",placeholder="Compare 2025 net profit margins of FPT, VNM and HPG")
if st.button("Analyze / Phân tích",type="primary"):
    data=load_metrics()
    if company!="All" and not data.empty: data=data[data.ticker==company]
    if not question.strip(): st.error("Enter a question first.")
    else:
        result=answer_question(question,data,"English" if language=="English" else "Vietnamese")
        st.subheader("Answer / Trả lời"); st.write(result["answer"])
        if result.get("formula"): st.caption("Formula: "+result["formula"])
        st.subheader("Financial evidence / Bằng chứng tài chính")
        if not result["evidence"]: st.info("No source evidence was found for this answer.")
        for item in result["evidence"]:
            if "metric_id" in item:
                st.write(f"**{item['ticker']} · {item['year']} · {item.get('metric_name_en',item['metric_id'])}** — {item['value']:,.0f} {item.get('currency','VND')}")
                st.caption(f"Source: {item.get('source_file','')} · page {item.get('source_page','?')} · validation: {item.get('validation_status','unverified')}")
            else:
                st.write(f"**{item['ticker']} {item['year']} · page {item['source_page']}** — {item['text'][:1400]}")
                st.caption(f"Source: {item['source_file']}")
st.divider()
st.caption("Portfolio research demonstration. Not investment advice. Figures depend on OCR extraction and should be checked against cited statements.")
