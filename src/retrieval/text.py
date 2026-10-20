import json
from pathlib import Path

def search_financial_notes(query, ticker=None, year=None, root="data/processed", limit=5):
    terms={x.casefold() for x in query.split() if len(x)>2}
    hits=[]
    for path in Path(root).glob("*_text.json"):
        parts=path.stem.split("_"); doc_ticker,doc_year=parts[0],int(parts[1])
        if ticker and doc_ticker!=ticker.upper(): continue
        if year and doc_year!=int(year): continue
        for page in json.loads(path.read_text(encoding="utf-8")):
            text=page.get("text","")
            score=sum(text.casefold().count(term) for term in terms)
            if score: hits.append({"ticker":doc_ticker,"year":doc_year,"source_file":path.name.replace("_text.json",".pdf"),"source_page":page["page"],"text":text,"score":score})
    return sorted(hits,key=lambda h:h["score"],reverse=True)[:limit]
