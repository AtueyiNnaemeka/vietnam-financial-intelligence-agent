"""Run the fixed question set against reviewed processed data; outputs exact current results."""
import json
from pathlib import Path
from src.agent.agent import answer_question, detect_language
from src.retrieval.structured import load_metrics

def run():
    data=load_metrics()
    questions=json.loads(Path("evaluations/questions.json").read_text(encoding="utf-8"))
    results=[]
    for item in questions:
        question=item["question"]
        language=detect_language(question)
        answer=answer_question(question,data)
        results.append({**item,"language":language,"answer":answer["answer"],"evidence":answer["evidence"]})
    Path("data/processed/evaluation_results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(f"Wrote {len(results)} dataset-derived responses to data/processed/evaluation_results.json")

if __name__=="__main__": run()
