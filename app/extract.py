"""Conservative extraction of defendants from Taiwanese judgment text.

The extractor only uses the party/header section of a judgment. It does not
infer gang membership, criminality, or identity from mentions elsewhere in the
opinion.
"""
import re
from typing import List, Dict

# Common labels that delimit a party name in the judgment header.
_ROLE_LABELS = (
    "被告", "原告", "上訴人", "被上訴人", "聲請人", "相對人", "抗告人",
    "再抗告人", "訴訟代理人", "代理人", "代表人", "法定代理人", "輔助參加人",
    "參加人", "共同訴訟代理人", "選任辯護人", "辯護人", "公訴人",
)

# These strongly suggest the extracted text is an institution/company rather
# than a person's name. We keep those out of the "被告人" chips.
_NON_PERSON_SUFFIXES = (
    "股份有限公司", "有限公司", "基金會", "協會", "委員會", "管理局", "警察局",
    "分局", "派出所", "法院", "檢察署", "檢察院", "法務部", "內政部", "國防部",
    "財政部", "教育部", "交通部", "行政院", "縣政府", "市政府", "公所", "營業處",
    "事務所", "銀行", "公司", "學校", "醫院", "局", "部", "署", "處",
)


def _header(text: str) -> str:
    """Return the party/header portion, before the main reasoning begins."""
    if not text:
        return ""
    # Party information is normally near the beginning. Stop before 主文/理由
    # to prevent ordinary prose such as "被告認為..." from becoming a name.
    head = text[:5000]
    for marker in ("主\u3000文", "主 文", "主文", "理\u3000由", "理由"):
        pos = head.find(marker)
        if pos > 150:
            head = head[:pos]
            break
    return head


def _clean_candidate(value: str) -> str:
    value = re.sub(r"[\s\u3000]+", "", value)
    value = re.sub(r"[：:，,。；;、].*$", "", value)
    return value.strip()


def _is_person_name(candidate: str) -> bool:
    # Taiwanese judgment redactions can be 甲○○/乙○○, while normal names are
    # 2–4 Han characters. Accept both forms but reject obvious institutions.
    if not candidate or len(candidate) < 2 or len(candidate) > 8:
        return False
    if any(suffix in candidate for suffix in _NON_PERSON_SUFFIXES):
        return False
    if not re.fullmatch(r"[\u4e00-\u9fff○●〇]{2,8}", candidate):
        return False
    return True


def extract_defendants(text: str) -> List[Dict[str, str]]:
    """Extract names explicitly listed after a party label in the header."""
    head = _header(text)
    if not head:
        return []

    results: List[Dict[str, str]] = []
    seen = set()

    # Work line-by-line first. The official mobile judgment pages generally
    # preserve party rows such as: "被      告  李○○".
    lines = [line.strip() for line in head.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if not re.search(r"被\s*告", line):
            continue

        # Remove the label and whitespace; stop at another party-role label.
        value = re.sub(r"^.*?被\s*告\s*", "", line, count=1)
        for role in _ROLE_LABELS:
            if role == "被告":
                continue
            value = re.split(rf"{re.escape(role)}\s*", value, maxsplit=1)[0]
        candidate = _clean_candidate(value)

        # If the page put the name on the next line, try that line too.
        candidates = [candidate]
        if not candidate and i + 1 < len(lines):
            candidates.append(_clean_candidate(lines[i + 1]))

        for cand in candidates:
            # A row can contain "李○○、王○○" or "李○○等".
            for part in re.split(r"(?:、|,|，|\s+等\s*)", cand):
                part = _clean_candidate(part)
                if _is_person_name(part) and part not in seen:
                    seen.add(part)
                    results.append({"name": part, "context": line})

    return results


def search_and_extract(rows, keyword: str):
    """Filter stored judgments by keyword and attach extracted defendants."""
    output = []
    for row in rows:
        text = row.get("text", "") or ""
        if keyword.lower() not in text.lower():
            continue
        output.append({**row, "defendants": extract_defendants(text)})
    return output
