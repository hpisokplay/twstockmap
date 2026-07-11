#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""產生示範資料（本機預覽用）。正式部署後由 fetch_data.py 以真實盤後資料覆蓋。"""
import json, os, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
random.seed(42)

with open(os.path.join(DATA, "industries.json"), encoding="utf-8") as f:
    ind = json.load(f)

codes = {}
for t in ind["themes"]:
    for tier in t["chain"].values():
        for g in tier:
            for c in g["companies"]:
                codes[c["code"]] = c["name"]

stocks, companies = {}, {}
for code, name in sorted(codes.items()):
    base = random.uniform(20, 1200)
    pct = random.uniform(-6, 8)
    close = round(base, 1)
    chg = round(base * pct / 100, 2)
    stocks[code] = {
        "name": name, "market": "TWSE",
        "close": close, "change": chg, "pct": round(pct, 2),
        "open": round(base * (1 - pct / 200), 1),
        "high": round(base * (1 + abs(pct) / 120), 1),
        "low": round(base * (1 - abs(pct) / 120), 1),
        "volume": random.randint(500, 80000) * 1000,
        "value": None,
        "pe": round(random.uniform(8, 60), 1),
        "pb": round(random.uniform(0.8, 12), 2),
        "yield": round(random.uniform(0.3, 6), 2),
        "foreign_net": random.randint(-8000, 12000) * 1000,
        "trust_net": random.randint(-2000, 4000) * 1000,
        "inst_net": random.randint(-9000, 15000) * 1000,
    }
    companies[code] = {
        "industry": "半導體業", "chairman": "—", "founded": "—",
        "website": "", "address": "台灣",
        "shares": None, "mktcap_e": round(random.uniform(50, 20000), 1),
        "rev_month": "11505", "rev": random.randint(3, 3000) * 1e5,
        "rev_yoy": round(random.uniform(-20, 80), 1),
        "rev_cum_yoy": round(random.uniform(-15, 60), 1),
    }

indices = [
    {"id": "taiex", "name": "台灣加權", "close": 45355.0, "change": -379.8, "pct": -0.83},
    {"id": "^sox", "name": "費城半導體", "close": 12967.0, "change": 7.16, "pct": 0.06},
    {"id": "^spx", "name": "S&P 500", "close": 7575.39, "change": 31.75, "pct": 0.42},
    {"id": "^ndq", "name": "那斯達克", "close": 24810.5, "change": 120.4, "pct": 0.49},
    {"id": "^nkx", "name": "日經 225", "close": 69320.0, "change": 235.0, "pct": 0.34},
    {"id": "tsm.us", "name": "台積電 ADR", "close": 434.11, "change": -2.85, "pct": -0.65},
    {"id": "nvda.us", "name": "輝達 NVDA", "close": 210.96, "change": 8.18, "pct": 4.03},
    {"id": "usdtwd", "name": "美元/台幣", "close": 29.85, "change": -0.06, "pct": -0.2},
]
funds = {"date": "2026-07-10", "rows": [
    ["自營商(自行買賣)", 9.5e9, 11.5e9, -2.0e9],
    ["自營商(避險)", 27.7e9, 33.4e9, -5.6e9],
    ["投信", 30.2e9, 10.3e9, 19.9e9],
    ["外資及陸資(不含外資自營商)", 367.9e9, 415.1e9, -47.3e9],
    ["外資自營商", 0, 0, 0],
    ["合計", 435.3e9, 470.3e9, -35.0e9],
]}
margin = {"date": "2026-07-10", "rows": [
    ["融資(交易單位)", 373000, 342000, 7000, 9591000, 9615000],
    ["融券(交易單位)", 24000, 24000, 2116, 206116, 204000],
    ["融資金額(仟元)", 31200000, 24800000, 600000, 613800000, 619600000],
]}
mops = [
    {"code": "2330", "name": "台積電", "date": "1150711", "time": "18:30:00", "subject": "（示範公告）本公司受邀參加法人說明會相關資訊", "market": "上市"},
    {"code": "8033", "name": "雷虎", "date": "1150711", "time": "17:05:00", "subject": "（示範公告）澄清媒體報導相關事宜", "market": "上市"},
    {"code": "3661", "name": "世芯-KY", "date": "1150710", "time": "19:12:00", "subject": "（示範公告）公告本公司董事會決議日期及相關事項", "market": "上市"},
    {"code": "2317", "name": "鴻海", "date": "1150710", "time": "16:44:00", "subject": "（示範公告）公告本公司取得機器設備之公告", "market": "上市"},
]
# 歷史收盤（25 個交易日隨機走勢，供週/月漲幅示範）
dates = []
d0 = 20260605
from datetime import date as _date, timedelta as _td
cur = _date(2026, 6, 5)
while len(dates) < 25:
    if cur.weekday() < 5:
        dates.append(cur.strftime("%Y-%m-%d"))
    cur += _td(days=1)
history = {}
walks = {c: stocks[c]["close"] for c in stocks}
for d in reversed(dates):
    history[d] = {c: round(v, 1) for c, v in walks.items()}
    for c in walks:
        walks[c] *= 1 + random.uniform(-0.03, 0.03)
history = {d: history[d] for d in dates}
# TDCC 大戶比率（兩週）
tdcc = {"2026-06-26": {c: round(random.uniform(15, 75), 2) for c in stocks}}
tdcc["2026-07-03"] = {c: round(min(max(v + random.uniform(-1.5, 2.5), 1), 90), 2) for c, v in tdcc["2026-06-26"].items()}

meta = {"updated": "示範資料（部署後自動更新）", "trade_date": "demo", "source": "示範資料", "demo": True}
payload = {"meta": meta, "indices": indices, "funds": funds, "margin": margin, "mops": mops, "stocks": stocks}
json.dump(payload, open(os.path.join(DATA, "market.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(history, open(os.path.join(DATA, "history.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(tdcc, open(os.path.join(DATA, "tdcc.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(companies, open(os.path.join(DATA, "companies.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(meta, open(os.path.join(DATA, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 同步輸出 .js 版（讓網頁不經伺服器、直接雙擊 index.html 也能載入資料）
def write_js(name, var, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        f.write(f"window.{var} = ")
        json.dump(obj, f, ensure_ascii=False)
        f.write(";")

write_js("market.js", "DATA_MARKET", payload)
write_js("companies.js", "DATA_COMPANIES", companies)
write_js("industries.js", "DATA_INDUSTRIES", ind)
write_js("history.js", "DATA_HISTORY", history)
write_js("tdcc.js", "DATA_TDCC", tdcc)
print(f"demo data: {len(stocks)} stocks")
