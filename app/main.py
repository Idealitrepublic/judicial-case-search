from html import escape
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()
from app.db import get_judgment, init_db, search_judgments
from app.extract import extract_defendants

app = FastAPI(title="Judicial Case Search", version="0.2.0")
init_db()


def enrich(row):
    item = dict(row)
    full = get_judgment(item["jid"])
    content = (full or {}).get("content", "")
    item["defendants"] = extract_defendants(content)
    item["content"] = content
    return item


@app.get("/api/search")
def api_search(q: str = Query(min_length=1), limit: int = Query(20, ge=1, le=100)):
    try:
        rows = search_judgments(q, limit)
        results = [enrich(r) for r in rows]
        return {"query": q, "total": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/judgment/{jid:path}")
def api_judgment(jid: str):
    item = get_judgment(jid)
    if not item:
        raise HTTPException(status_code=404, detail="找不到裁判書")
    item["defendants"] = extract_defendants(item.get("content", ""))
    return item


@app.get("/", response_class=HTMLResponse)
def home(q: str = ""):
    results = []
    error = ""
    if q.strip():
        try:
            results = [enrich(r) for r in search_judgments(q.strip(), 50)]
        except Exception as exc:
            error = str(exc)

    cards = []
    for r in results:
        people = "".join(
            f"<span class='person'>{escape(p['name'])}</span>" for p in r.get("defendants", [])
        ) or "<span class='none'>未能從公開裁判文字安全辨識被告姓名</span>"
        cards.append(f"""
        <article class='card'>
          <div class='meta'>{escape(r.get('date',''))} · {escape(r.get('jid',''))}</div>
          <h2><a href='/judgment/{escape(r['jid'], quote=True)}'>{escape(r.get('title') or '未提供案由')}</a></h2>
          <div class='label'>被告人</div>
          <div class='people'>{people}</div>
          <div class='snippet'>{r.get('snippet') or ''}</div>
        </article>
        """)

    return f"""<!doctype html>
<html lang='zh-Hant'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>司法院裁判書搜尋</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans TC',sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;background:#f6f7f9;color:#202124}}
h1{{margin-bottom:8px}} .sub{{color:#666;margin-bottom:24px}}
form{{display:flex;gap:8px;margin-bottom:24px}} input{{flex:1;padding:13px;border:1px solid #ccc;border-radius:8px;font-size:16px}}button{{padding:13px 22px;border:0;border-radius:8px;background:#111;color:white;cursor:pointer}}
.card{{background:white;border:1px solid #ddd;border-radius:10px;padding:18px;margin:12px 0}}h2{{font-size:18px;margin:8px 0}}a{{color:#174ea6;text-decoration:none}}.meta{{font-size:13px;color:#777}}.snippet{{line-height:1.7;color:#444;margin-top:12px}}mark{{background:#fff0a8}}.error{{color:#b00020}}.label{{font-weight:700;margin-top:12px}}.people{{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}}.person{{background:#fff0f0;border:1px solid #e5b4b4;border-radius:999px;padding:5px 10px}}.none{{color:#888}}
</style></head><body>
<h1>司法院裁判書搜尋</h1><div class='sub'>全文關鍵字搜尋 · 自動整理判決中的被告姓名</div>
<form><input name='q' value='{escape(q, quote=True)}' placeholder='例如：竹聯幫、組織犯罪、某人姓名'><button>搜尋</button></form>
{f"<p class='error'>{escape(error)}</p>" if error else ''}
<p>找到 {len(results)} 筆</p>
{''.join(cards) if cards else '<p>輸入關鍵字開始搜尋。</p>'}
</body></html>"""


@app.get("/judgment/{jid:path}", response_class=HTMLResponse)
def judgment_page(jid: str):
    item = get_judgment(jid)
    if not item:
        raise HTTPException(status_code=404, detail="找不到裁判書")
    defendants = extract_defendants(item.get("content", ""))
    people = "".join(f"<li>{escape(p['name'])}</li>" for p in defendants) or "<li>未能安全辨識</li>"
    content = escape(item.get("content") or "").replace("\n", "<br>")
    return f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>{escape(item.get('title') or '裁判書')}</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans TC',sans-serif;max-width:1000px;margin:40px auto;padding:0 20px}}.meta{{color:#666}}.doc{{line-height:1.9}}.box{{background:#fff5f5;border:1px solid #ecc;padding:15px;border-radius:10px;margin:20px 0}}</style></head><body>
<p><a href='/'>← 回搜尋</a></p><h1>{escape(item.get('title') or '裁判書')}</h1>
<div class='meta'>{escape(item.get('jid',''))} · {escape(item.get('date',''))}</div>
<div class='box'><strong>判決文字自動辨識之被告</strong><ul>{people}</ul><small>姓名僅依公開裁判文字中的「被告」欄位抽取，請以原文核驗。</small></div><hr>
<div class='doc'>{content}</div></body></html>"""
