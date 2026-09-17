import argparse
import html
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

SITE = "https://www.yad2.co.il/realestate/rent"
FEED = "https://gw.yad2.co.il/realestate-feed/rent/feed"
ITEM = "https://www.yad2.co.il/realestate/item/{}"
# Every listing bucket the feed returns; yad1 is projects, skipped on purpose.
POOLS = ("private", "agency", "platinum", "trio", "booster", "leadingBroker", "kingOfTheHar")
SENT_FILE = Path("sent_posts.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def load_sent():
    try:
        return set(json.loads(SENT_FILE.read_text("utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent(sent):
    SENT_FILE.write_text(json.dumps(sorted(sent), ensure_ascii=False, indent=4), "utf-8")


def open_yad2(pw):
    # ponytail: Radware bot-manager blocks plain HTTP clients. One real page load
    # earns the cookies; every feed call then runs as fetch() inside that page.
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(user_agent=UA, locale="he-IL")
    page.goto(SITE, wait_until="domcontentloaded")
    for _ in range(12):
        page.wait_for_timeout(2500)
        if "Radware" not in page.title():
            break
    log.info("yad2 page title: %s", page.title())
    return browser, page


def fetch_feed(page, params):
    url = f"{FEED}?{urlencode(params)}"
    for attempt in range(2):
        try:
            res = page.evaluate(
                "async (u) => { try { const r = await fetch(u, {credentials: 'include', signal: AbortSignal.timeout(20000)});"
                " return {status: r.status, body: await r.text()}; }"
                " catch (e) { return {status: 0, body: String(e)}; } }", url)
            if res["status"] == 200:
                return json.loads(res["body"]).get("data", {})
            log.warning("feed %s -> %s %s (page title: %s)", url, res["status"], res["body"][:200], page.title())
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
        except Exception as e:  # ponytail: Mac dozing mid-run makes any Playwright call hang or time out; give up on this page, next hour retries
            log.warning("feed %s attempt %s failed: %s", url, attempt + 1, str(e).splitlines()[0][:200])
    return None


def iter_items(data):
    for pool in POOLS:
        for item in data.get(pool) or []:
            if item.get("token"):
                yield item


def format_message(item, search_name):
    a = item.get("address", {})
    d = item.get("additionalDetails", {})
    house = a.get("house", {})
    where = ", ".join(filter(None, [a.get("city", {}).get("text"), a.get("neighborhood", {}).get("text")]))
    street = " ".join(str(x) for x in [a.get("street", {}).get("text"), house.get("number")] if x)
    facts = " | ".join(filter(None, [
        f"{d.get('roomsCount')} חד'" if d.get("roomsCount") else None,
        f"{d.get('squareMeter')} מ\"ר" if d.get("squareMeter") else None,
        f"קומה {house.get('floor')}" if house.get("floor") is not None else None,
        d.get("property", {}).get("text"),
    ]))
    price = f"{item['price']:,} ₪" if isinstance(item.get("price"), (int, float)) else "ללא מחיר"
    return "\n".join([
        f"<b>{html.escape(search_name, quote=False)}</b>",
        html.escape(where, quote=False),
        html.escape(street, quote=False),
        html.escape(facts, quote=False),
        f"<b>{price}</b>",
        ITEM.format(item["token"]),
    ])


def send(token, chat_ids, text):
    ok = True
    for chat_id in chat_ids:
        for _ in range(3):
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=30)
            if r.ok:
                break
            if r.status_code == 429:
                time.sleep(r.json().get("parameters", {}).get("retry_after", 5))
                continue
            log.error("telegram %s -> %s %s", chat_id, r.status_code, r.text[:200])
            ok = False
            break
    return ok


def run(searches_file, dry_run, seed):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = [v for k, v in os.environ.items() if k.startswith("CHAT_ID_")]
    if not dry_run and not seed and not (token and chat_ids):
        log.error("TELEGRAM_BOT_TOKEN / CHAT_ID_* missing")
        return
    searches = json.loads(Path(searches_file).read_text("utf-8"))
    sent = load_sent()
    new = fetched = 0
    with sync_playwright() as pw:
        browser, page = open_yad2(pw)
        for s in searches:
            pageno, total_pages = 1, 1
            while pageno <= min(total_pages, s.get("max_pages", 200)):
                data = fetch_feed(page, {**s["params"], "page": pageno})
                if data is None:
                    break
                fetched += 1
                total_pages = data.get("pagination", {}).get("totalPages", 0)
                items = list(iter_items(data))
                log.info("%s page %s/%s: %s items", s["name"], pageno, total_pages, len(items))
                pageno += 1
                for item in items:
                    if item["token"] in sent:
                        continue
                    msg = format_message(item, s["name"])
                    if dry_run:
                        print(msg, "\n")
                    elif not seed and not send(token, chat_ids, msg):
                        continue
                    sent.add(item["token"])
                    new += 1
                page.wait_for_timeout(1000)
        browser.close()
    if not dry_run:
        save_sent(sent)
    log.info("done: %s new listings", new)
    if not fetched:
        sys.exit("no feed page could be fetched")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Yad2 rent notifier")
    ap.add_argument("--searches", default="searches.json")
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending, don't save")
    ap.add_argument("--seed", action="store_true", help="mark everything as sent without sending")
    args = ap.parse_args()
    run(args.searches, args.dry_run, args.seed)
