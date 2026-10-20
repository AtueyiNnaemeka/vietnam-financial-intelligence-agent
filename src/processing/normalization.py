"""Normalize Vietnamese/English financial number strings without guessing."""
from dataclasses import dataclass
import re
from typing import Optional

@dataclass(frozen=True)
class NumberResult:
    value: Optional[float]
    status: str
    reason: str = ""

def normalize_number(raw: object) -> NumberResult:
    if raw is None:
        return NumberResult(None, "unverified", "empty value")
    s = str(raw).strip().replace("−", "-").replace("–", "-").replace("₫", "").replace("VND", "")
    if "\n" in s or "\r" in s:
        return NumberResult(None, "warning", "multiple OCR values in one cell")
    if not s or s in {"-", "—", "–", "N/A", "n/a"}:
        return NumberResult(None, "unverified", "blank or dash")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("() ").replace(" ", "")
    # Ignore only known currency/unit labels. Arbitrary OCR letters (e.g. S52...) must
    # make the token ambiguous rather than silently turn it into a plausible amount.
    s = re.sub(r"(?i)\b(?:VND|VNĐ)\b", "", s)
    if re.search(r"[A-Za-zÀ-ỹ]", s):
        return NumberResult(None, "warning", f"unexpected letters in OCR number: {raw}")
    s = re.sub(r"[^\d,.'+-]", "", s)
    if not re.search(r"\d", s):
        return NumberResult(None, "warning", f"unrecognized number: {raw}")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        parts = s.split(sep)
        groups=parts[0].lstrip("+-")
        if len(parts)>2 or (len(parts)==2 and len(parts[-1])==3):
            if not (1<=len(groups)<=3 and all(len(part)==3 for part in parts[1:])):
                return NumberResult(None,"warning",f"invalid digit grouping in {raw}")
            s = "".join(parts)
        elif len(parts) == 2:
            return NumberResult(None, "warning", f"ambiguous separator in {raw}")
    try:
        value = float(s)
        return NumberResult(-abs(value) if neg else value, "valid")
    except ValueError:
        return NumberResult(None, "warning", f"could not parse: {raw}")
