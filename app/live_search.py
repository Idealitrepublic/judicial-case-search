"""Live full-text search against public Taiwanese judgment indexes."""
import html
import re
from urllib.parse import urljoin

import httpx

SEARCH_URL = "https://judgment.judicial.gov.tw/FJUD/qryresult.aspx"
DATA_BASE = "https://judgment.judicial.gov.tw/FJUD/"
LAWPLAYER_SEARCH = "https://lawplayer.com/search/judgment/"


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
    links = []
    patterns = [
        r"(?:https?://judgment\.judicial\.gov\.tw)?(?:/)?FJUD/(?:data|printData)\.aspx\?[^\"'<>\s]+",
        r"(?:https?://judgment\.judicial\.gov\.tw)?(?:/)?LAW_Mobile_FJUD/FJUD/(?:data|printData)\.aspx\?[^\"'<>\s]+",
        r"href=[\"']([^\"']*(?:data|printData)\.aspx\?[^\"']+)[\"']",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, page, re.I):
            href = html.unescape(raw).replace("&amp;", "&")
            if href.startswith("href="):
                href = href.split("=", 1)[1].strip("\"'")
            if not re.search(r"(?:^|/)(?:data|printData)\.aspx\?", href, re.I):
                continue
            if not re.search(r"(?:^|[?&])id=", href, re.I):
                continue
            url = urljoin(DATA_BASE, href)
            if url not in links:
                links.append(url)
    return links


def _lawplayer_links(page: str):
    links = []
    for raw in re.findall(r"href=[\"']([^\"']*?/judgment/[^\"']+)[\"']", page, re.I):
        href = html.unescape(raw)
        url = urljoin("https://lawplayer.com", href)
        if url not in links:
            links.append(url)
    return links


def _fetch_judgment(client: httpx.Client, url: str, source: str = "official"):
    response = client.get(url)
    response.raise_for_status()
    raw = response.text
    text = _clean_text(raw)
    jid_match = re.search(r"(?:^|[?&])id=([^&\"']+)", url, re.I)
    jid = html.unescape(jid_match.group(1)) if jid_match else url
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    title = _clean_text(title_match.group(1)) if title_match else "裁判書"
    return {
        "jid": jid, "title": title, "date": "", "case_no": "",
        "case_type": "", "year": "", "content": text,
        "snippet": text[:900], "source_url": url, "source": source,
    }


def _search_official(client, keyword: str, limit: int):
    response = client.get(
        SEARCH_URL,
        params={"judtype": "JUDBOOK", "kw": keyword, "sys": "A", "jud_court": ""},
    )
    response.raise_for_status()
    page = response.text
    text = _clean_text(page)
    if "查詢設定錯誤" in text:
        raise RuntimeError("司法院拒絕了這組查詢條件，請縮小關鍵字後重試。")
    if "系統忙碌中" in text:
        raise RuntimeError("司法院裁判書系統目前忙碌，請稍後重試。")

    links = _result_links(page)
    results = []
    for url in links:
        if len(results) >= limit:
            break
        try:
            item = _fetch_judgment(client, url, "official")
            if keyword in item["content"] or keyword.lower() in item["content"].lower():
                results.append(item)
        except Exception:
            continue
    return results


def _search_lawplayer(client, keyword: str, limit: int):
    response = client.get(LAWPLAYER_SEARCH + keyword)
    response.raise_for_status()
    links = _lawplayer_links(response.text)
    results = []
    for url in links:
        if len(results) >= limit:
            break
        try:
            item = _fetch_judgment(client, url, "lawplayer")
            if keyword in item["content"] or keyword.lower() in item["content"].lower():
                results.append(item)
        except Exception:
            continue
    return results


def search_official(keyword: str, limit: int = 20):
    keyword = keyword.strip()
    if not keyword:
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
        "Referer": "https://judgment.judicial.gov.tw/FJUD/default.aspx",
    }

    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        # Prefer the official source. If the official result page is reachable
        # but its dynamic result links cannot be parsed from a server request,
        # fall back to LawPlayer's public index of the same Judicial Yuan data.
        try:
            results = _search_official(client, keyword, limit)
            if results:
                return results
        except Exception:
            pass

        fallback = _search_lawplayer(client, keyword, limit)
        if fallback:
            return fallback

        raise RuntimeError("找不到裁判結果：司法院官方搜尋與公開裁判索引目前都沒有可用結果。")
