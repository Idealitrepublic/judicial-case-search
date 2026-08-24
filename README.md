# judicial-case-search

司法院裁判書開放 API 的個人搜尋與同步工具。

## 功能

- 使用司法院資料開放平台帳號取得 6 小時有效 Token
- 每日自動抓取司法院提供的「7 日前裁判書異動清單」
- 取得刑事、民事、行政、懲戒、憲法裁判全文並以 JID 去重
- SQLite FTS5 全文搜尋，可搜尋任意關鍵字
- 簡易 Web UI 與 JSON API
- 若司法院撤下既有裁判，依官方規則從本地資料庫移除
- 密碼只透過環境變數提供，絕不寫入 repository

## 重要限制

司法院官方 API 每日服務時間為台灣時間 00:00–06:00；API 本身只提供「7 日前」的異動清單。因此本專案的自動同步是持續累積資料，而不是一次取得全部歷史裁判。要建立更完整的歷史資料庫，需要讓同步程式持續運行，或另外取得合法的歷史資料來源。

官方 API 規格：https://opendata.judicial.gov.tw/api/Newses/42/file

## 設定

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

填入：

```text
JUDICIAL_USER=你的司法院資料開放平台帳號
JUDICIAL_PASSWORD=你的司法院資料開放平台密碼
```

不要把 `.env`、密碼或 Token commit 到 Git。

## 本機執行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.sync
uvicorn app.main:app --reload
```

開啟 `http://127.0.0.1:8000`。

搜尋 API 範例：

```text
GET /api/search?q=竹聯幫&limit=20
```

## GitHub Actions

`.github/workflows/judicial-sync.yml` 每日於司法院 API 開放時段執行同步。請在 GitHub repository 的 **Settings → Secrets and variables → Actions** 建立：

- `JUDICIAL_USER`
- `JUDICIAL_PASSWORD`

目前 workflow 將資料庫作為 artifact 保存，避免把裁判資料或帳密提交到 Git。

## 資料判讀

本工具是全文檢索工具，不會因為某人的姓名出現在判決中，就自動判定其為犯罪組織成員。若後續加入人物/組織 Entity Extraction，應區分「法院明確認定」、「判決描述涉及」、「僅文字出現」等證據層級。

## License

Code: MIT. 裁判書內容之使用仍應遵守司法院資料開放平台的使用規範及相關法律。