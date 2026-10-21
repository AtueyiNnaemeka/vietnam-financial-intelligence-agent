"""Conservative local search over extracted annual-report page text."""
import json
import math
import re
import unicodedata
from pathlib import Path

EXPANSIONS = {
    "segment": ("bộ phận theo lĩnh vực kinh doanh", "phân khúc kinh doanh", "business segment"),
    "segments": ("bộ phận theo lĩnh vực kinh doanh", "phân khúc kinh doanh", "business segment"),
    "business": ("kinh doanh",),
    "risk": ("rủi ro", "nguy cơ"),
    "risks": ("rủi ro", "nguy cơ"),
    "phân khúc": ("bộ phận theo lĩnh vực kinh doanh",),
    "rủi ro": ("risk", "risks", "nguy cơ"),
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to",
    "was", "what", "were", "which", "with", "year", "company", "report", "s",
    "major", "relevant", "disclosed", "show", "tell", "about", "please",
    "của", "các", "cho", "có", "gì", "là", "nào", "những", "trong", "về",
    "được", "hãy", "cho", "biết", "báo", "cáo", "năm",
}
RISK_DISCLOSURE_CONTEXT = (
    "rủi ro tài chính", "rủi ro tín dụng", "rủi ro thanh khoản", "rủi ro thị trường",
    "rủi ro tỷ giá", "rủi ro lãi suất", "quản lý rủi ro", "quản trị rủi ro",
    "financial risk", "credit risk", "liquidity risk", "market risk",
    "foreign exchange risk", "interest rate risk", "risk management", "risk exposure",
    "risk factors", "principal risks", "key risks", "risk mitigation",
)


def _fold(value):
    value = str(value).casefold().replace("đ", "d")
    return "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def _tokens(value):
    return re.findall(r"[^\W\d_]+", _fold(value), flags=re.UNICODE)


def _ocr_is_readable(text):
    """Reject OCR pages dominated by isolated characters and table noise."""
    words = _tokens(text)
    if len(words) < 35:
        return False
    readable = sum(len(word) >= 3 for word in words) / len(words)
    return readable >= 0.45


def _query_concepts(query):
    concepts = []
    for word in _tokens(query):
        if word in STOPWORDS or word in {"fpt", "vnm", "hpg"} or word.isdigit():
            continue
        alternatives = {word}
        alternatives.update(_fold(phrase) for phrase in EXPANSIONS.get(word, ()))
        concepts.append(alternatives)
    return concepts


def _excerpt(text, concepts, limit=1400):
    compact = " ".join(str(text).split())
    searchable = compact.casefold()
    positions = [
        searchable.find(term.casefold())
        for concept in concepts
        for term in concept
        if searchable.find(term.casefold()) >= 0
    ]
    if not positions or len(compact) <= limit:
        return compact[:limit]
    original_length = len(compact)
    start = max(0, min(positions) - limit // 5)
    end = min(len(compact), start + limit)
    if start:
        compact = "…" + compact[start:end]
    else:
        compact = compact[:end]
    if end < original_length:
        compact += "…"
    return compact


def search_financial_notes(query, ticker=None, year=None, root="data/processed", limit=5):
    """Return relevant, readable snippets; avoid substring matches and noisy OCR."""
    concepts = _query_concepts(query)
    if not concepts:
        return []

    hits = []
    for path in sorted(Path(root).glob("*_text.json")):
        match = re.fullmatch(r"([A-Z]+)_(20\d{2})_text", path.stem)
        if not match:
            continue
        doc_ticker, doc_year = match.group(1), int(match.group(2))
        if ticker and doc_ticker != ticker.upper():
            continue
        if year and doc_year != int(year):
            continue

        try:
            pages = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for page in pages:
            text = page.get("text", "")
            if not text or (page.get("ocr_used") and not _ocr_is_readable(text)):
                continue

            normalized_tokens = _tokens(text)
            normalized_text = " ".join(normalized_tokens)
            folded_query = _fold(query)
            risk_query = bool(re.search(r"\b(risks?|risk factors?|rui ro|nguy co)\b", folded_query))
            if risk_query and not any(_fold(phrase) in normalized_text for phrase in RISK_DISCLOSURE_CONTEXT):
                continue
            matched = 0
            frequency = 0
            for concept in concepts:
                count = 0
                for alternative in concept:
                    if " " in alternative:
                        count += normalized_text.count(alternative)
                    else:
                        count += normalized_tokens.count(alternative)
                if count:
                    matched += 1
                    frequency += min(count, 3)

            minimum = 1 if len(concepts) == 1 else max(2, math.ceil(len(concepts) * 0.4))
            if matched < minimum:
                continue
            score = matched + frequency * 0.05
            hits.append({
                "ticker": doc_ticker,
                "year": doc_year,
                "source_file": path.name.replace("_text.json", ".pdf"),
                "source_page": page.get("page", "?"),
                "text": _excerpt(text, concepts),
                "score": score,
            })

    return sorted(hits, key=lambda hit: (-hit["score"], hit["ticker"], hit["year"], hit["source_page"]))[:limit]
