"""Search the Judicial Yuan's official public judgment search UI.

The Open API exposes JList/JDoc, but not a general historical full-text search
endpoint. For keyword searches this module uses the same public search endpoint
used by the Judicial Yuan website, then fetches the official judgment pages.
"""
import html
import re
from urllib.parse import urljoin

import httpx

SEARCH_URL = "https://judgment.judicial.gov.tw/LAW_Mobile_FJUD/FJUD/qryresult.aspx"
DATA_BASE = "https://judgment.judicial.gov.tw/LAW_Mobile_FJUD/FJUD/"


def _clean_text(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|li|tr|h[1-6])\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s+", "\n", value)
    return value.strip()


def _result_links(page: str):
    """Extract official judgment detail links from a result page.

    The mobile and desktop versions have changed markup over time, so do not
    require a particular query-string ordering or the presence of ty=JD.
    """
    links = []
    for raw in re.findall(r"href=[\"']([^\"']+)[\"']", page, re.I):
        href = html.unescape(raw).replace("&amp;", "&")
        if not re.search(r"(?:/|\\)data\.aspx\?", href, re.I):
            continue
        if not re.search(r"(?:^|[?&])id=", href, re.I):
            continue
        url = urljoin(DATA_BASE, href)
        if url not in links:
            links.append(url)
    return links


def _fetch_judgment(client: httpx.Client, url: str):
    response = client.get(url)
    response.raise_for_status()
    raw = response.text
    text = _clean_text(raw)

    jid_match = re.search(r"(?:^|[?&])id=([^&\"']+)", url, re.I)
    jid = html.unescape(jid_match.group(1)) if jid_match else url
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    title = _clean_text(title_match.group(1)) if title_match else ""

    # The public judgment page normally contains a date and case number in
    # visible text; keep the full text as the authoritative content.
    return {
        "jid": jid,
        "title": title,
        "date": "",
        "case_no": "",
        "case_type": "",
        "year": "",
        "content": text,
        "snippet": text[:900],
        "source_url": url,
    }


def search_official(keyword: str, limit: int = 20):
    keyword = keyword.strip()
    if not keyword:
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JudicialCaseSearch/0.4)",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(
            SEARCH_URL,
            params={
                "judtype": "JUDBOOK",
                "kw": keyword,
                "sys": "M",
                "jud_court": "",
            },
        )
        response.raise_for_status()
        links = _result_links(response.text)

        # If the server returns a system/validation page rather than results,
        # fail loudly instead of silently showing "0".
        if not links:
            text = _clean_text(response.text)
            if "查詢設定錯誤" in text or "系統忙碌中" in text:
                raise RuntimeError("司法院官方搜尋目前拒絕了這次查詢，請稍後重試。")
            return []

        results = []
        for url in links:
            if len(results) >= limit:
                break
            try:
                item = _fetch_judgment(client, url)
                content = item["content"]
                if keyword in content or keyword.lower() in content.lower():
                    results.append(item)
            except Exception:
                continue
        return results
