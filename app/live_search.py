"""Fallback search against the official Judicial Yuan public judgment search UI.

The Judicial Yuan Open API exposes JList/JDoc, but it does not expose a keyword
full-text search endpoint. JList only returns a rolling change list. For a
keyword such as 竹聯幫, this module uses the Judicial Yuan's public search UI to
locate historical judgments, then fetches the official judgment pages and
extracts the public text. API synchronization remains the preferred local
source when available.
"""
import html
import re
from urllib.parse import quote, urljoin

import httpx

SEARCH_URL = "https://judgment.judicial.gov.tw/FJUD/qryresult.aspx"
DATA_BASE = "https://judgment.judicial.gov.tw/FJUD/"


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
    # Official result pages expose judgment links as FJUD/data.aspx URLs.
    links = []
    pattern = re.compile(r"href=[\"']([^\"']*(?:data|printData)\.aspx\?[^\"']+)[\"']", re.I)
    for raw in pattern.findall(page):
        href = html.unescape(raw).replace("&amp;", "&")
        if "id=" not in href or "ty=JD" not in href:
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
    match = re.search(r"id=([^&\"']+)", url, re.I)
    jid = match.group(1) if match else url
    title = ""
    # Prefer the page title, then the first heading-like text.
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    if title_match:
        title = _clean_text(title_match.group(1))
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

    headers = {"User-Agent": "Mozilla/5.0 (compatible; JudicialCaseSearch/0.3)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        # M = 刑事. This is the intended first search for criminal/organization
        # keywords; the user can still search any public judgment term.
        response = client.get(
            SEARCH_URL,
            params={"judtype": "JUDBOOK", "kw": keyword, "sys": "M", "jud_court": ""},
        )
        response.raise_for_status()
        links = _result_links(response.text)[:limit]
        results = []
        for url in links:
            try:
                item = _fetch_judgment(client, url)
                # Keep only pages that actually contain the requested term.
                if keyword in item["content"] or keyword.lower() in item["content"].lower():
                    results.append(item)
            except Exception:
                continue
        return results
