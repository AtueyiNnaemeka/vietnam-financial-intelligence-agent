# 🇻🇳 Vietnam Financial Intelligence & Research Agent

A small local portfolio project that turns Vietnamese listed-company annual financial statements into searchable evidence and deterministic financial calculations. This is a research demonstration, not investment advice or a production financial platform.

## Scope and status

The target dataset is nine audited consolidated annual reports: FPT, VNM and HPG for 2023–2025. PDFs are expected under `data/raw/<ticker>/<TICKER>_<year>.pdf`, including `data/raw/FPT/FPT_<year>.pdf`. Source PDFs may have redistribution restrictions and are ignored by Git. No downloading or scraping occurs.

The repository supplies an offline extraction pipeline, schema and mappings, local retrieval, deterministic calculations, a bilingual question interface, evaluation prompts, and tests. OCR/table extraction varies with each report's layout. Inspect extracted tables and citations before using any value. Only unambiguous label/value pairs are promoted automatically; the rest remain in the raw table artifacts for review. Source URL and document date fields in `data/metadata/reports.csv` should be completed from the exact downloaded editions when available.

## Architecture

```text
Manually obtained PDFs → PyMuPDF text + img2table/Tesseract (vie+eng)
  → raw page/table artifacts → conservative metric mapping and number normalization
  → validated structured CSV + local keyword retrieval
  → deterministic Python calculations and evidence → Streamlit
```

No cloud service, paid API, vector database, or LLM is required. The small query router uses direct Python and local keyword matching, so numerical answers remain available without an LLM. Narrative retrieval is lexical and may miss paraphrases; no embedding model is required for this nine-report corpus.

## Data model and source evidence

`financial_metrics.csv` uses `company, ticker, year, statement_type, metric_id, metric_name_vi, metric_name_en, value, currency, unit, source_file, source_page, validation_status, derivation`. Values are normalized numeric amounts in the report's stated unit; the app labels unit as `as_reported` unless confirmed. Raw page text and detected tables are written per company/year under `data/processed/`. Page numbering is one-based.

The canonical mapping in `src/processing/cleaning.py` covers key balance-sheet, income-statement, and cash-flow items in English and Vietnamese. Financial functions are pure Python and do not ask an LLM to do arithmetic. Supported functions include growth, gross/operating/net margins, ROA/ROE, leverage, liquidity, operating-cash-flow coverage, and simplified free cash flow. Missing values and zero denominators produce no computed ratio.

Validation helpers check the balance-sheet equation and revenue less cost of sales against gross profit with a 1% tolerance. A mismatch is a warning; values are never corrected automatically. OCR candidates that cannot be parsed unambiguously are not promoted.

## Setup

Use Python 3.10 or newer. Install Tesseract and its Vietnamese and English language packs (`vie` and `eng`) using your operating system's package manager, then:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Check `tesseract --list-langs` includes `vie` and `eng`. Put permitted PDFs in the expected directories. Do not add restricted source PDFs to Git.

## Preprocessing

OCR is an explicit offline step, not run when Streamlit starts:

```bash
python -m src.ingestion.preprocess
```

This produces `*_text.json`, `*_tables.json`, and `financial_metrics.csv` in `data/processed/`. Review the raw tables, reported units, ambiguous labels, and financial validation before relying on data. Tesseract/img2table extraction is layout-sensitive; the prototype does not claim that all required line items can be automatically mapped in every report.

Narrative page text is OCRed with `vie+eng` from page 15 onward; the opening financial statement pages are covered by table extraction. For a quick narrative OCR refresh after changing text extraction, run `python -m src.ingestion.preprocess --text-only`. To rebuild canonical metrics and validation from already extracted table JSON without rerunning table detection, run `python -m src.ingestion.preprocess --reuse-tables`. OCR runs offline and may take several minutes for scanned reports.

The app's structured retrieval returns rows marked `valid` and clearly identified derivations. Warnings and unverified values are withheld from numerical answers. For example, net revenue can be derived from extracted sales less revenue deductions when the report's net-revenue cell was missed; the app labels the calculation and shows both source rows. Narrative search filters low-quality OCR, requires multiple query terms for longer questions, and displays source text as plain text so OCR characters cannot become Markdown headings. Financial questions never fall back to narrative snippets for a numeric answer.

## Run the app

```bash
streamlit run app/streamlit_app.py
```

The app resolves the project root from its own file location, so the command also works when Streamlit is started from another working directory. The company filter defaults to All. If the selected company conflicts with a ticker in the question, the app asks you to align the filter instead of returning cross-company evidence.

Example questions:

- What was HPG's revenue in 2023?
- What was FPT's net profit margin in 2025?
- HPG có bao nhiêu tổng tài sản năm 2025?
- What are HPG's major business segments?

Unsupported years and stock-price questions are explicitly declined. Each numerical result displays its source file, page, and validation status. Answers only work when the corresponding values were extracted and reviewed. English/Vietnamese intent and metric labels are supported, though the current response phrasing is intentionally compact and bilingual coverage is limited to mapped intents.

## Evaluation and tests

Fifteen fixed questions are listed in `evaluations/questions.json`. Expected numerical answers must be generated from the reviewed processed dataset; they are not hard-coded because OCR results depend on the source report. Run deterministic unit tests with:

```bash
pytest
```

## Limitations and future improvements

- Annual-report tables differ by issuer and year; verify OCR figures against the cited pages.
- Statement units need report-by-report review; source figures may be in VND, thousand VND, or million VND.
- The initial mapping focuses on required financial metrics and does not reconstruct every comparative column reliably.
- Narrative search is local keyword matching, not semantic search.
- The query router supports a deliberately small set of question forms; unsupported questions should be treated as unavailable.
- No real-time prices, forecasting, trading recommendations, investment advice, scraping, accounts, cloud services, or production monitoring are included.
- Screenshots can be captured locally after preprocessing and running the app; none are committed because the project has no reviewed dataset snapshot yet.

## Sources and licensing

`data/metadata/reports.csv` records the company/year/report descriptors and local paths. Fill each `source_url` with the exact official source used and confirm report edition, document date, currency, and unit. Public availability does not automatically grant permission to redistribute a PDF. The repository's project code uses the license in `LICENSE`; report rights remain with their respective publishers.
