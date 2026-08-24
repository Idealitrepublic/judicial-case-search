import logging
from dotenv import load_dotenv

load_dotenv()

from app.db import init_db, upsert_judgment, delete_judgment
from app.judicial import JudicialAPIError, JudicialClient, normalize_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    init_db()
    client = JudicialClient()
    client.authenticate()
    days = client.changed_jids()
    total = 0
    removed = 0

    for day in days:
        date = day.get("date", "")
        jids = day.get("list", []) or []
        logging.info("%s: %d JID", date, len(jids))
        for jid in jids:
            total += 1
            try:
                data = client.get_document(jid)
                if isinstance(data, dict) and data.get("error"):
                    delete_judgment(jid)
                    removed += 1
                    logging.info("removed: %s", jid)
                    continue
                doc = normalize_document(data)
                if doc["jid"]:
                    upsert_judgment(doc)
            except JudicialAPIError as exc:
                # Official API may report a previously-public judgment as removed.
                if "查無資料" in str(exc) or "移除" in str(exc):
                    delete_judgment(jid)
                    removed += 1
                    logging.info("removed: %s", jid)
                else:
                    logging.warning("skip %s: %s", jid, exc)
            except Exception:
                logging.exception("unexpected error for %s", jid)

    logging.info("sync complete: processed=%d removed=%d", total, removed)

if __name__ == "__main__":
    main()
