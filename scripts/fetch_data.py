#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股產業地圖 — 盤後資料抓取腳本
資料來源（全部為官方公開 API，免金鑰）：
  1. TWSE 上市個股日成交資訊  https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
  2. TWSE 上市個股本益比/殖利率/淨值比  https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL
  3. TWSE 上市公司基本資料  https://openapi.twse.com.tw/v1/opendata/t187ap03_L
  4. TWSE 上市公司每月營收  https://openapi.twse.com.tw/v1/opendata/t187ap05_L
  5. TWSE 三大法人買賣超（個股）  https://www.twse.com.tw/rwd/zh/fund/T86
  6. TPEx 上櫃個股日成交資訊  https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes
  7. TPEx 上櫃個股本益比等  https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis

輸出：
  data/market.json     個股行情 + 估值 + 法人（給網站用）
  data/companies.json  公司基本資料（市值、產業別、董事長、網址…）
  data/meta.json       更新時間戳
執行：python scripts/fetch_data.py
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; twstockmap/1.0; personal research)",
    "Accept": "application/json",
}


def fetch_json(url, retries=3, timeout=30):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            last_err = e
            print(f"  retry {i+1}/{retries} for {url}: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    print(f"  FAILED: {url}: {last_err}", file=sys.stderr)
    return None


def num(s):
    """把 '1,234.56' / '--' / '' 轉成 float 或 None"""
    if s is None:
        return None
    s = str(s).replace(",", "").replace("+", "").strip()
    if s in ("", "--", "-", "N/A", "除權息", "0.00%"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def roc_to_iso(roc):
    """民國日期 1150711 或 115/07/11 -> 2026-07-11"""
    if not roc:
        return None
    s = str(roc).replace("/", "")
    if len(s) == 7:
        return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"
    if len(s) == 8:  # 西元
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None


def fetch_csv(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8").strip().splitlines()
    except Exception as e:  # noqa
        print(f"  csv fail {url}: {e}", file=sys.stderr)
        return None


def fetch_indices():
    """指數面板：台股加權（TWSE）＋ 國際指數/ADR（stooq 公開 CSV）"""
    out = []
    # --- 台灣加權：FMTQIK 當月每日市場成交統計（含加權指數）---
    j = fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK", retries=2)
    if j and len(j) >= 2:
        try:
            last, prev = j[-1], j[-2]
            c = num(last.get("TAIEX")) or num(last.get("發行量加權股價指數"))
            p = num(prev.get("TAIEX")) or num(prev.get("發行量加權股價指數"))
            if c and p:
                out.append({"id": "taiex", "name": "台灣加權", "close": c,
                            "change": round(c - p, 2), "pct": round((c - p) / p * 100, 2)})
        except Exception as e:  # noqa
            print(f"  taiex parse fail: {e}", file=sys.stderr)
    # --- 國際：stooq 日線 CSV，取最後兩筆算漲跌 ---
    symbols = [
        ("^sox", "費城半導體"), ("^spx", "S&P 500"), ("^ndq", "那斯達克"),
        ("^nkx", "日經 225"), ("tsm.us", "台積電 ADR"), ("nvda.us", "輝達 NVDA"),
        ("usdtwd", "美元/台幣"),
    ]
    for sym, name in symbols:
        lines = fetch_csv(f"https://stooq.com/q/d/l/?s={sym}&i=d")
        if not lines or len(lines) < 3:
            continue
        try:
            rows = [l.split(",") for l in lines[-2:]]
            c, p = float(rows[1][4]), float(rows[0][4])
            out.append({"id": sym, "name": name, "close": round(c, 2),
                        "change": round(c - p, 2), "pct": round((c - p) / p * 100, 2)})
        except Exception:  # noqa
            continue
        time.sleep(1)
    print(f"  指數 {len(out)} 檔")
    return out


def fetch_market_funds():
    """三大法人買賣金額統計（市場合計，BFI82U）"""
    for back in range(0, 7):
        d = (datetime.now(TPE) - timedelta(days=back)).strftime("%Y%m%d")
        j = fetch_json(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={d}&type=day&response=json", retries=1)
        if j and j.get("stat") == "OK" and j.get("data"):
            rows = [[r[0], num(r[1]), num(r[2]), num(r[3])] for r in j["data"]]
            return {"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "rows": rows}
        time.sleep(1)
    return None


def fetch_margin():
    """信用交易統計（融資融券市場合計，MI_MARGN）"""
    for back in range(0, 7):
        d = (datetime.now(TPE) - timedelta(days=back)).strftime("%Y%m%d")
        j = fetch_json(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d}&selectType=MS&response=json", retries=1)
        tables = (j or {}).get("tables") or ([j] if j and j.get("data") else [])
        for t in tables:
            data = t.get("data") or []
            if data and any("融資" in str(r[0]) for r in data):
                rows = [[r[0]] + [num(x) for x in r[1:6]] for r in data]
                return {"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "rows": rows}
        time.sleep(1)
    return None


def fetch_mops():
    """上市/上櫃當日重大訊息（官方公開資訊）"""
    out = []
    for url, mk in (("https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "上市"),
                    ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O", "上櫃")):
        rows = fetch_json(url) or []
        for r in rows:
            subj = (r.get("主旨 ") or r.get("主旨") or "").strip()
            code = (r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip()
            if not subj or not code:
                continue
            out.append({
                "code": code,
                "name": (r.get("公司名稱") or r.get("CompanyName") or "").strip(),
                "date": (r.get("發言日期") or "").strip(),
                "time": (r.get("發言時間") or "").strip(),
                "subject": subj[:120],
                "market": mk,
            })
    out = out[-60:]
    print(f"  重大訊息 {len(out)} 則")
    return out


def update_history(stocks, trade_date, keep=26):
    """累積每日收盤價歷史（供週/月漲幅排行用），保留最近 keep 個交易日"""
    path = os.path.join(DATA_DIR, "history.json")
    hist = {}
    if os.path.exists(path):
        try:
            hist = json.load(open(path, encoding="utf-8"))
        except Exception:  # noqa
            hist = {}
    if trade_date:
        hist[trade_date] = {c: s["close"] for c, s in stocks.items() if s.get("close") is not None}
    dates = sorted(hist.keys())[-keep:]
    hist = {d: hist[d] for d in dates}
    json.dump(hist, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return hist


def update_tdcc(keep=5):
    """集保戶股權分散表（每週）：計算各股 400 張以上大戶持股比率並累積歷史"""
    path = os.path.join(DATA_DIR, "tdcc.json")
    hist = {}
    if os.path.exists(path):
        try:
            hist = json.load(open(path, encoding="utf-8"))
        except Exception:  # noqa
            hist = {}
    lines = fetch_csv("https://opendata.tdcc.com.tw/getOD.ashx?id=1-5", timeout=120)
    if lines and len(lines) > 100:
        big = {}
        date = None
        for ln in lines[1:]:
            p = ln.split(",")
            if len(p) < 6:
                continue
            date = date or p[0]
            code, level = p[1].strip(), p[2].strip()
            # 分級 12–15 = 持股 400,001 股以上（>400 張）
            if level in ("12", "13", "14", "15"):
                try:
                    big[code] = round(big.get(code, 0) + float(p[5]), 2)
                except ValueError:
                    pass
        if date and big:
            d_iso = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else date
            hist[d_iso] = big
            print(f"  TDCC {d_iso}: {len(big)} 檔大戶比率")
    dates = sorted(hist.keys())[-keep:]
    hist = {d: hist[d] for d in dates}
    json.dump(hist, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return hist


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    stocks = {}

    # ---------- 1. 上市收盤行情 ----------
    print("[1/7] TWSE 上市收盤行情 ...")
    rows = fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL") or []
    trade_date = None
    for r in rows:
        code = r.get("Code", "").strip()
        if not code:
            continue
        trade_date = trade_date or roc_to_iso(r.get("Date"))
        close = num(r.get("ClosingPrice"))
        chg = num(r.get("Change"))
        prev = (close - chg) if (close is not None and chg is not None) else None
        stocks[code] = {
            "name": r.get("Name", "").strip(),
            "market": "TWSE",
            "close": close,
            "change": chg,
            "pct": round(chg / prev * 100, 2) if (chg is not None and prev) else None,
            "open": num(r.get("OpeningPrice")),
            "high": num(r.get("HighestPrice")),
            "low": num(r.get("LowestPrice")),
            "volume": num(r.get("TradeVolume")),
            "value": num(r.get("TradeValue")),
        }
    print(f"  {len(stocks)} 檔上市")

    # ---------- 2. 上市估值 ----------
    print("[2/7] TWSE 本益比/殖利率/淨值比 ...")
    rows = fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL") or []
    for r in rows:
        code = r.get("Code", "").strip()
        if code in stocks:
            stocks[code]["pe"] = num(r.get("PEratio"))
            stocks[code]["pb"] = num(r.get("PBratio"))
            stocks[code]["yield"] = num(r.get("DividendYield"))

    # ---------- 3. 上櫃收盤行情 ----------
    print("[3/7] TPEx 上櫃收盤行情 ...")
    rows = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes") or []
    for r in rows:
        code = (r.get("SecuritiesCompanyCode") or r.get("Code") or "").strip()
        if not code:
            continue
        close = num(r.get("Close") or r.get("ClosingPrice"))
        chg = num(r.get("Change"))
        prev = (close - chg) if (close is not None and chg is not None) else None
        stocks[code] = {
            "name": (r.get("CompanyName") or r.get("Name") or "").strip(),
            "market": "TPEx",
            "close": close,
            "change": chg,
            "pct": round(chg / prev * 100, 2) if (chg is not None and prev) else None,
            "open": num(r.get("Open") or r.get("OpeningPrice")),
            "high": num(r.get("High") or r.get("HighestPrice")),
            "low": num(r.get("Low") or r.get("LowestPrice")),
            "volume": num(r.get("TradingShares") or r.get("TradeVolume")),
            "value": num(r.get("TransactionAmount") or r.get("TradeValue")),
        }

    # ---------- 4. 上櫃估值 ----------
    print("[4/7] TPEx 本益比等 ...")
    rows = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis") or []
    for r in rows:
        code = (r.get("SecuritiesCompanyCode") or r.get("Code") or "").strip()
        if code in stocks:
            stocks[code]["pe"] = num(r.get("PriceEarningRatio") or r.get("PEratio"))
            stocks[code]["pb"] = num(r.get("PriceBookRatio") or r.get("PBratio"))
            stocks[code]["yield"] = num(r.get("YieldRatio") or r.get("DividendYield"))

    # ---------- 5. 三大法人（上市，T86） ----------
    print("[5/7] TWSE 三大法人買賣超 ...")
    for back in range(0, 7):  # 往前找最近一個有資料的交易日
        d = (datetime.now(TPE) - timedelta(days=back)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALLBUT0999&response=json"
        j = fetch_json(url, retries=1)
        if j and j.get("stat") == "OK" and j.get("data"):
            fields = j.get("fields", [])
            try:
                i_code = fields.index("證券代號")
                i_foreign = next(i for i, f in enumerate(fields) if "外陸資買賣超" in f)
                i_trust = fields.index("投信買賣超股數")
                i_total = fields.index("三大法人買賣超股數")
            except (ValueError, StopIteration):
                i_code, i_foreign, i_trust, i_total = 0, 4, 10, len(fields) - 1
            n = 0
            for row in j["data"]:
                code = str(row[i_code]).strip()
                if code in stocks:
                    stocks[code]["foreign_net"] = num(row[i_foreign])
                    stocks[code]["trust_net"] = num(row[i_trust])
                    stocks[code]["inst_net"] = num(row[i_total])
                    n += 1
            print(f"  {d}: {n} 檔法人資料")
            break
        time.sleep(2)

    # ---------- 6. 公司基本資料 ----------
    print("[6/7] 上市/上櫃公司基本資料 ...")
    companies = {}
    for url in (
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
    ):
        rows = fetch_json(url) or []
        for r in rows:
            code = (r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip()
            if not code:
                continue
            capital = num(r.get("實收資本額") or r.get("Paidin.Capital.NTDollars"))
            shares = capital / 10 if capital else None  # 面額10元 -> 發行股數
            close = stocks.get(code, {}).get("close")
            companies[code] = {
                "industry": (r.get("產業別") or r.get("SecuritiesIndustryCode") or "").strip(),
                "chairman": (r.get("董事長") or r.get("Chairman") or "").strip(),
                "founded": (r.get("成立日期") or r.get("DateOfIncorporation") or "").strip()[:7],
                "listed": (r.get("上市日期") or r.get("DateOfListing") or "").strip(),
                "website": (r.get("網址") or r.get("WebAddress") or "").strip(),
                "address": (r.get("住址") or r.get("Address") or "").strip(),
                "shares": shares,
                "mktcap_e": round(close * shares / 1e8, 1) if (close and shares) else None,  # 億元
            }

    # ---------- 7. 每月營收 ----------
    print("[7/7] 每月營收 ...")
    for url in (
        "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
    ):
        rows = fetch_json(url) or []
        for r in rows:
            code = (r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip()
            if code in companies:
                companies[code]["rev_month"] = (r.get("資料年月") or "").strip()
                companies[code]["rev"] = num(r.get("營業收入-當月營收"))
                companies[code]["rev_yoy"] = num(r.get("營業收入-去年同月增減(%)"))
                companies[code]["rev_cum_yoy"] = num(r.get("累計營業收入-前期比較增減(%)"))

    # ---------- 指數面板 ----------
    print("[8/12] 指數面板 ...")
    indices = fetch_indices()

    # ---------- 三大法人市場統計 / 資券 / 重大訊息 ----------
    print("[9/12] 三大法人買賣金額 ...")
    funds = fetch_market_funds()
    print("[10/12] 融資融券統計 ...")
    margin = fetch_margin()
    print("[11/12] 重大訊息 ...")
    mops = fetch_mops()

    # ---------- 歷史累積（週/月漲幅、大戶持股） ----------
    print("[12/12] 歷史資料累積 ...")
    history = update_history(stocks, trade_date)
    tdcc = update_tdcc()

    # ---------- 輸出 ----------
    now = datetime.now(TPE)
    meta = {
        "updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": trade_date,
        "source": "TWSE / TPEx 公開資訊",
        "demo": False,
    }
    payload = {"meta": meta, "indices": indices, "funds": funds, "margin": margin,
               "mops": mops, "stocks": stocks}
    with open(os.path.join(DATA_DIR, "market.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA_DIR, "companies.json"), "w", encoding="utf-8") as f:
        json.dump(companies, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 同步輸出 .js 版（讓網頁不經伺服器、直接雙擊 index.html 也能載入資料）
    def write_js(name, var, obj):
        with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
            f.write(f"window.{var} = ")
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
            f.write(";")

    write_js("market.js", "DATA_MARKET", payload)
    write_js("companies.js", "DATA_COMPANIES", companies)
    write_js("history.js", "DATA_HISTORY", history)
    write_js("tdcc.js", "DATA_TDCC", tdcc)
    with open(os.path.join(DATA_DIR, "industries.json"), encoding="utf-8") as f:
        write_js("industries.js", "DATA_INDUSTRIES", json.load(f))
    print(f"完成：{len(stocks)} 檔行情、{len(companies)} 家公司基本資料，交易日 {trade_date}")


if __name__ == "__main__":
    main()
