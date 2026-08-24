import os
import time
import httpx

BASE = "https://data.judicial.gov.tw/jdg/api"
USER = os.getenv("JUDICIAL_USER")
PASSWORD = os.getenv("JUDICIAL_PASSWORD")
DELAY = float(os.getenv("JUDICIAL_REQUEST_DELAY", "0.25"))

class JudicialAPIError(RuntimeError):
    pass

class JudicialClient:
    def __init__(self):
        if not USER or not PASSWORD:
            raise JudicialAPIError("JUDICIAL_USER / JUDICIAL_PASSWORD 未設定")
        self.token = None
        self.http = httpx.Client(timeout=60, follow_redirects=True)

    def authenticate(self):
        r = self.http.post(f"{BASE}/Auth", json={"user": USER, "password": PASSWORD})
        r.raise_for_status()
        data = r.json()
        if "Token" not in data:
            raise JudicialAPIError(data.get("error", "司法院 API 驗證失敗"))
        self.token = data["Token"]
        return self.token

    def _ensure_token(self):
        if not self.token:
            self.authenticate()

    def _post(self, endpoint, payload):
        self._ensure_token()
        r = self.http.post(f"{BASE}/{endpoint}", json=payload)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            if "驗證" in str(data["error"]):
                self.authenticate()
                r = self.http.post(f"{BASE}/{endpoint}", json={**payload, "token": self.token})
                r.raise_for_status()
                data = r.json()
            if isinstance(data, dict) and data.get("error"):
                raise JudicialAPIError(data["error"])
        return data

    def changed_jids(self):
        return self._post("JList", {"token": self.token})

    def get_document(self, jid):
        time.sleep(DELAY)
        return self._post("JDoc", {"token": self.token, "j": jid})

def normalize_document(data):
    full = data.get("JFULLX") or {}
    jid = data.get("JID", "")
    parts = jid.split(",")
    return {
        "jid": jid,
        "year": data.get("JYEAR", parts[1] if len(parts) > 1 else ""),
        "case_type": data.get("JCASE", parts[2] if len(parts) > 2 else ""),
        "case_no": data.get("JNO", parts[3] if len(parts) > 3 else ""),
        "date": data.get("JDATE", ""),
        "title": data.get("JTITLE", ""),
        "content": full.get("JFULLCONTENT", "") or "",
        "full_type": full.get("JFULLTYPE", ""),
        "pdf_url": full.get("JFULLPDF", "") or "",
    }
