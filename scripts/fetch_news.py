#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股產業焦點新聞 — 自動彙整腳本（全自動，不需人工編輯 data/news.js）

資料來源（皆為官方/公開提供的 RSS 訂閱服務，僅取用發布方自己提供的標題與短摘要，
不轉載全文、每則都附回原文連結）：
  1. Yahoo奇摩股市．台股動態  https://tw.stock.yahoo.com/rss?category=tw-market
  2. 中央社 CNA．產經證券      https://feeds.feedburner.com/rsscna/finance

處理流程：
  1. 抓取上述 RSS，解析出 標題 / 官方摘要 / 原文連結 / 發布時間 / 來源媒體
  2. 用 data/industries.json 裡「真實存在」的公司名稱與題材名稱做關鍵字比對，
     自動幫新聞掛上相關題材標籤——比對不到現有題材的新聞會直接略過，
     不會出現網站沒有收錄、點了卻無反應的題材標籤（例如「電商零售」這類我們
     供應鏈資料庫沒有的題材，就不會被選進來）
  3. 依日期分組寫回 data/news.js，維持與網站相同的資料結構，保留最近 KEEP_DAYS 天
  4. 完全不呼叫 AI、不生成任何摘要文字——摘要就是新聞來源自己提供的官方短摘要，
     避免產生「編輯觀點」或看起來像杜撰的內容

輸出：data/news.js
執行：python scripts/fetch_news.py
（正式環境建議接在 scripts/fetch_data.py 之後、同一個排程一起跑，
 見 .github/workflows/update.yml）

注意：這個檔案每次執行都會整批覆寫 data/news.js，請不要手動編輯內容本身；
若要調整新聞來源、比對邏輯、Premium 設定，請改這支腳本裡的常數。
"""
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

TPE = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; twstockmap/1.0; personal research)",
}

# 新聞來源（官方 RSS，非爬蟲）
FEEDS = [
    {"url": "https://tw.stock.yahoo.com/rss?category=tw-market", "source": "Yahoo奇摩股市"},
    {"url": "https://feeds.feedburner.com/rsscna/finance", "source": "中央社"},
]

KEEP_DAYS = 14          # 網站上保留最近幾天的新聞
MAX_PER_DAY = 10        # 每天最多顯示幾則，避免洗版
MAX_TOPICS_PER_ITEM = 3  # 每則新聞最多掛幾個題材標籤
SUMMARY_MAX_LEN = 120   # 摘要最多字數（原文摘要截斷，不做全文轉載）

# Premium 鎖定設定（原本 data/news.js 手動維護的部分，改成寫在這裡；
# 之後要調整解鎖張數/贊助連結，改這裡即可）
PREMIUM = {
    "free": 3,
    "title": "Premium 限定",
    "desc": "一個月一杯咖啡支持作者，解鎖今日全部焦點",
    "cta": "立即升級",
    "url": "",  # 填你的贊助/訂閱連結；留空則點「立即升級」會顯示提示
}


def fetch_bytes(url, retries=3, timeout=20):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last_err = e
            print(f"  retry {i+1}/{retries} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    print(f"  FAILED: {url}: {last_err}", file=sys.stderr)
    return None


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
           .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_rss(xml_bytes, source_name):
    """解析標準 RSS 2.0 格式，單一來源失敗不影響其他來源"""
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  XML 解析失敗（{source_name}）：{e}", file=sys.stderr)
        return items
    for item in root.iter("item"):
        def get(tag):
            el = item.find(tag)
            return el.text if el is not None and el.text else ""
        title = strip_html(get("title"))
        link = get("link").strip()
        desc = strip_html(get("description"))
        pub = get("pubDate")
        dt = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub).astimezone(TPE)
            except Exception:
                dt = None
        if not title or not dt:
            continue
        summary = desc[:SUMMARY_MAX_LEN] + ("…" if len(desc) > SUMMARY_MAX_LEN else "")
        items.append({
            "title": title,
            "summary": summary,
            "url": link,
            "source": source_name,
            "date": dt.strftime("%Y-%m-%d"),
        })
    return items


def build_keyword_map(industries):
    """回傳依關鍵字長度由長到短排序的 [(關鍵字, {(題材id, 題材名稱), ...}), ...]，
    關鍵字長到短排序是為了避免短字串（例如公司名稱裡的單一個字）先比對造成誤判"""
    kmap = {}
    for t in industries.get("themes", []):
        ref = (t["id"], t["name"])
        kmap.setdefault(t["name"], set()).add(ref)
        for tier in t.get("chain", {}).values():
            for group in tier:
                for c in group.get("companies", []):
                    nm = c.get("name")
                    if nm and len(nm) >= 2:
                        kmap.setdefault(nm, set()).add(ref)
    return sorted(kmap.items(), key=lambda kv: -len(kv[0]))


def match_topics(text, keyword_list, limit=MAX_TOPICS_PER_ITEM):
    matched_kws = [kw for kw, _refs in keyword_list if kw in text]
    kw_set = set(matched_kws)
    # 較短的關鍵字如果只是另一個「已比對到的較長關鍵字」的子字串，就略過，
    # 避免例如「南亞」（1303）被「南亞科」（2408）這種不同公司的新聞誤觸發
    filtered = [kw for kw in matched_kws if not any(kw != other and kw in other for other in kw_set)]
    kw_map = dict(keyword_list)
    found = {}
    for kw in filtered:
        for tid, tname in kw_map[kw]:
            if tid not in found:
                found[tid] = tname
            if len(found) >= limit:
                return [{"id": k, "name": v} for k, v in found.items()]
    return [{"id": k, "name": v} for k, v in found.items()]


def main():
    print("[1/2] 抓取 RSS 新聞來源 ...")
    all_items = []
    for feed in FEEDS:
        raw = fetch_bytes(feed["url"])
        if not raw:
            continue
        parsed = parse_rss(raw, feed["source"])
        print(f"  {feed['source']}：{len(parsed)} 則")
        all_items.extend(parsed)

    if not all_items:
        print("沒有抓到任何新聞（所有來源都失敗），保留現有 data/news.js 不覆寫", file=sys.stderr)
        return

    print("[2/2] 比對題材標籤 ...")
    with open(os.path.join(DATA_DIR, "industries.json"), encoding="utf-8") as f:
        industries = json.load(f)
    kw_list = build_keyword_map(industries)

    tagged = []
    seen_titles = set()
    for it in all_items:
        if it["title"] in seen_titles:
            continue
        topics = match_topics(it["title"] + " " + it["summary"], kw_list)
        if not topics:
            continue  # 比對不到現有題材就略過，不亂貼標籤、也不會出現點了沒反應的 tag
        seen_titles.add(it["title"])
        it["topics"] = topics
        tagged.append(it)

    by_date = {}
    for it in tagged:
        by_date.setdefault(it["date"], []).append(it)

    cutoff = (datetime.now(TPE) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    days_out = {}
    for d, items in sorted(by_date.items(), reverse=True):
        if d < cutoff:
            continue
        items = items[:MAX_PER_DAY]
        days_out[d] = [
            {"source": it["source"], "title": it["title"], "summary": it["summary"],
             "url": it["url"], "topics": it["topics"]}
            for it in items
        ]

    out = {
        "meta": {
            "updated": datetime.now(TPE).strftime("%Y-%m-%d"),
            "note": "新聞由 Yahoo奇摩股市／中央社 RSS 自動彙整並依題材比對，非即時、排定每日隨盤後資料更新",
        },
        "premium": PREMIUM,
        "days": days_out,
    }

    news_path = os.path.join(DATA_DIR, "news.js")
    with open(news_path, "w", encoding="utf-8") as f:
        f.write("// 此檔案由 scripts/fetch_news.py 自動產生並定期覆寫，請勿手動編輯\n")
        f.write("// 如需調整新聞來源、比對規則、Premium 設定，請改 scripts/fetch_news.py\n")
        f.write("window.DATA_NEWS = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    total = sum(len(v) for v in days_out.values())
    print(f"完成：{len(days_out)} 天、共 {total} 則新聞 -> data/news.js")


if __name__ == "__main__":
    main()
