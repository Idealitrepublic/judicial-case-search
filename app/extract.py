"""Conservative extraction of defendants from Taiwanese judgment text.

This module does NOT infer criminal/organizational membership. It only extracts
names from explicit defendant sections and preserves the source text so users
can verify each result against the judgment.
"""
import re
from typing import List, Dict


def extract_defendants(text: str) -> List[Dict[str, str]]:
    """Extract likely defendant names from common judgment headings.

    Taiwanese judgments commonly contain headings such as "被告○○○" or
    "被告 XXX 等". We intentionally keep the extractor conservative.
    """
    if not text:
        return []

    results = []
    seen = set()

    patterns = [
        r"被\s*告\s*([\u4e00-\u9fff]{2,4})",
        r"被告\s*([\u4e00-\u9fff]{2,4})\s*(?:等|、)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if name in {"人姓名", "姓名", "等"} or name in seen:
                continue
            seen.add(name)
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 120)
            results.append({"name": name, "context": text[start:end]})

    return results


def search_and_extract(rows, keyword: str):
    """Filter stored judgments by keyword and attach extracted defendants."""
    output = []
    for row in rows:
        text = row.get("text", "") or ""
        if keyword.lower() not in text.lower():
            continue
        defendants = extract_defendants(text)
        output.append({**row, "defendants": defendants})
    return output
