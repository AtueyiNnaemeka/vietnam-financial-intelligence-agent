from pathlib import Path

def find_report(root, ticker, year):
    """Find a report using the canonical ticker/year directory convention."""
    root = Path(root)
    path = root / ticker / f"{ticker}_{year}.pdf"
    return path if path.is_file() else None

def extract_page_text(path):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required. Install requirements.txt") from exc
    with fitz.open(path) as pdf:
        pages=[]
        for i,page in enumerate(pdf):
            text=page.get_text("text").strip()
            ocr_used=False
            # The opening pages are primarily audited statements and are covered by
            # table extraction. OCR narrative-note pages for local text retrieval.
            if not text and i>=14:
                try:
                    text=page.get_text("text", textpage=page.get_textpage_ocr(language="vie+eng",dpi=160,full=True)).strip()
                    ocr_used=bool(text)
                except Exception as exc:
                    print(f"Warning: OCR failed on page {i+1} of {path}: {exc}")
            pages.append({"page":i+1,"text":text,"ocr_used":ocr_used})
        return pages
