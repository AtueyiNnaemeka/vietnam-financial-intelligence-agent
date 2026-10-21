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
    s = str(raw).strip().replace("−", "-").replace("–", "-").replace("₫", "")
    if "\n" in s or "\r" in s:
        return NumberResult(None, "warning", "multiple OCR values in one cell")
    if not s or s in {"-", "—", "–", "N/A", "n/a"}:
        return NumberResult(None, "unverified", "blank or dash")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("() ").replace(" ", "")
    # Ignore only known currency/unit labels. Arbitrary OCR letters (e.g. S52...) must
    # make the token ambiguous rather than silently turn it into a plausible amount.
    s = re.sub(r"(?i)^\s*(?:VND|VNĐ)\s*|\s*(?:VND|VNĐ)\s*$", "", s)
    if re.search(r"[A-Za-zÀ-ỹ]", s):
        return NumberResult(None, "warning", f"unexpected letters in OCR number: {raw}")
    if re.search(r"[^\d,.'+\-()]", s):
        return NumberResult(None, "warning", f"unexpected OCR character in number: {raw}")
    s = re.sub(r"[^\d,.'+-]", "", s)
    if not re.search(r"\d", s):
        return NumberResult(None, "warning", f"unrecognized number: {raw}")
    if "," in s and "." in s:
        # OCR often mixes comma and dot in Vietnamese integer amounts while every
        # group still has three digits (for example 52,625.174.861.333).
        groups = re.split(r"[.,]", s)
        if len(groups) > 2 and 1 <= len(groups[0].lstrip("+-")) <= 3 and all(len(group) == 3 for group in groups[1:]):
            s = "".join(groups)
        else:
            if s.rfind(",") > s.rfind("."):
                integer, decimal = s.rsplit(",", 1)
                groups = integer.split(".")
                if not (1 <= len(groups[0].lstrip("+-")) <= 3 and all(len(group) == 3 for group in groups[1:]) and 1 <= len(decimal) <= 2):
                    return NumberResult(None, "warning", f"ambiguous mixed separators in {raw}")
                s = "".join(groups) + "." + decimal
            else:
                integer, decimal = s.rsplit(".", 1)
                groups = integer.split(",")
                if not (1 <= len(groups[0].lstrip("+-")) <= 3 and all(len(group) == 3 for group in groups[1:]) and 1 <= len(decimal) <= 2):
                    return NumberResult(None, "warning", f"ambiguous mixed separators in {raw}")
                s = "".join(groups) + "." + decimal
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
