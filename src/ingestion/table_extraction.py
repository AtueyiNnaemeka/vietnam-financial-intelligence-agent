"""Offline img2table + Tesseract extraction. Tables retain one-based source page."""
from pathlib import Path

def extract_tables(pdf_path, language="vie+eng"):
    try:
        from img2table.document import PDF
        from img2table.ocr import TesseractOCR
    except ImportError as exc:
        raise RuntimeError("img2table and pytesseract are required; install requirements.txt") from exc
    document = PDF(src=str(pdf_path), pages=None, detect_rotation=True, pdf_text_extraction=True)
    ocr = TesseractOCR(lang=language, n_threads=1, psm=6)
    tables = document.extract_tables(ocr=ocr, implicit_rows=True, borderless_tables=True,
                                     min_confidence=50)
    result = []
    for page_index, page_tables in tables.items():
        for table_index, table in enumerate(page_tables):
            df = table.df.fillna("").astype(str)
            result.append({"source_page": int(page_index) + 1, "table_index": table_index,
                           "data": df.values.tolist()})
    return result
