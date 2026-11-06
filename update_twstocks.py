#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灣眼視光概念股 — 每日收盤行情(免費、免金鑰)
來源:臺灣證券交易所 OpenAPI(上市)+ 櫃買中心 OpenAPI(上櫃)。
寫入 tw_stocks.json,並保留近 60 日收盤序列供趨勢顯示。由 GitHub Actions 每交易日收盤後執行。
"""
import json, sys, datetime, os
import requests

HEAD = {"User-Agent": "Mozilla/5.0 (EyeVisionHub-TWStocks/1.0)", "Accept": "application/json"}
TWSE = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TPEX_ESB = "https://www.tpex.org.tw/openapi/v1/tpex_esb_latest_statistics"  # 興櫃

# 追蹤清單:代號 → (顯示名, 公司 id(對應 COMPANIES), 類別)
WATCH = {
    "6491": ("晶碩光學", "pegavision", "隱形眼鏡"),
    "6782": ("視陽光學", "viscovision", "隱形眼鏡"),
    "1565": ("精華光學", "stshine", "隱形眼鏡"),
    "8215": ("明基材料", "benqm", "隱形眼鏡/材料"),
    "4150": ("優你康", "unicon", "隱形眼鏡"),
    "4771": ("望隼科技", "visionsky", "隱形眼鏡"),
    "3218": ("大學光", "dagroup", "眼科通路"),
    "5312": ("寶島科", "formosa-optical", "眼鏡通路"),
    "6885": ("全福生技", "brim", "眼藥新藥"),
    "6696": ("仁新醫藥", "linbio", "眼藥新藥"),
    "6796": ("晉弘科技", "medimaging", "眼科醫材"),
    "4164": ("承業醫", "chc", "眼科醫材"),
    "3008": ("大立光", "largamed", "光學(星歐母公司)"),
}

def log(*a):
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")

def num(v):
    try:
        return float(str(v).replace(",", "").replace("+", "").strip())
    except Exception:
        return None

def pick(d, *cands):
    """依欄位名子字串(不分大小寫)取值"""
    for k, v in d.items():
        kl = (k or "").lower()
        for c in cands:
            if c.lower() in kl:
                return v
    return None

def fetch_twse():
    out = {}
    try:
        r = requests.get(TWSE, headers=HEAD, timeout=60)
        rows = r.json()
        log("TWSE rows:", len(rows), "| sample keys:", list(rows[0].keys()) if rows else [])
        for d in rows:
            code = str(pick(d, "Code") or "").strip()
            if code in WATCH:
                close = num(pick(d, "ClosingPrice", "Close"))
                chg = num(pick(d, "Change"))
                out[code] = {"close": close, "change": chg,
                             "open": num(pick(d, "OpeningPrice", "Open")), "high": num(pick(d, "HighestPrice", "High")),
                             "low": num(pick(d, "LowestPrice", "Low")), "vol": num(pick(d, "TradeVolume", "TradingShares")),
                             "market": "上市"}
    except Exception as e:
        log("TWSE fail:", e)
    return out

def fetch_tpex():
    out = {}
    try:
        r = requests.get(TPEX, headers=HEAD, timeout=60)
        rows = r.json()
        log("TPEx rows:", len(rows), "| sample keys:", list(rows[0].keys()) if rows else [])
        for d in rows:
            code = str(pick(d, "SecuritiesCompanyCode", "Code") or "").strip()
            if code in WATCH:
                out[code] = {"close": num(pick(d, "Close")), "change": num(pick(d, "Change")),
                             "open": num(pick(d, "Open")), "high": num(pick(d, "High")), "low": num(pick(d, "Low")),
                             "vol": num(pick(d, "TradingShares", "TradeVolume")), "market": "上櫃"}
    except Exception as e:
        log("TPEx fail:", e)
    return out

def fetch_tpex_esb():
    """興櫃(優你康、仁新等)"""
    out = {}
    try:
        r = requests.get(TPEX_ESB, headers=HEAD, timeout=60)
        rows = r.json()
        log("TPEx ESB rows:", len(rows), "| sample keys:", list(rows[0].keys()) if rows else [])
        for d in rows:
            code = str(pick(d, "SecuritiesCompanyCode", "Code") or "").strip()
            if code in WATCH:
                close = num(pick(d, "LatestPrice", "Close", "Latest", "Last"))
                prev = num(pick(d, "PreviousAverage", "Previous", "Reference"))
                chg = num(pick(d, "Change"))
                if chg is None and close is not None and prev:
                    chg = close - prev
                out[code] = {"close": close, "change": chg, "open": num(pick(d, "Open")), "high": num(pick(d, "High")),
                             "low": num(pick(d, "Low")), "vol": num(pick(d, "TradingShares", "Volume")), "market": "興櫃"}
                log("  ESB", code, {k: d[k] for k in list(d.keys())[:10]})
    except Exception as e:
        log("TPEx ESB fail:", e)
    return out

def main():
    today = datetime.date.today().isoformat()
    quotes = {}
    quotes.update(fetch_tpex_esb())
    quotes.update(fetch_tpex())
    quotes.update(fetch_twse())  # 上市覆蓋(同代號不會重複)
    log("matched:", len(quotes), "/", len(WATCH), "→", sorted(quotes.keys()))
    if not quotes:
        log("!! no quotes — keeping existing tw_stocks.json")
        return
    # 載入舊歷史
    hist = {}
    prev_date = ""
    if os.path.exists("tw_stocks.json"):
        try:
            old = json.load(open("tw_stocks.json", encoding="utf-8"))
            hist = old.get("hist", {}) or {}
            prev_date = old.get("date", "")
        except Exception:
            pass
    items = []
    for code, (name, cid, cat) in WATCH.items():
        q = quotes.get(code)
        if not q or q.get("close") is None:
            continue
        close, chg = q["close"], q.get("change") or 0.0
        prev = close - chg
        pct = (chg / prev * 100.0) if prev else 0.0
        # 歷史序列(同日覆蓋)
        h = [x for x in hist.get(code, []) if x[0] != today]
        h.append([today, close])
        hist[code] = h[-60:]
        items.append({"code": code, "name": name, "cid": cid, "cat": cat, "market": q["market"],
                      "close": close, "change": round(chg, 2), "pct": round(pct, 2),
                      "open": q.get("open"), "high": q.get("high"), "low": q.get("low"), "vol": q.get("vol")})
    items.sort(key=lambda x: -abs(x["pct"]))
    data = {"updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "date": today,
            "source": "臺灣證券交易所 OpenAPI / 櫃買中心 OpenAPI(收盤資料)", "items": items, "hist": hist}
    with open("tw_stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log("wrote tw_stocks.json:", len(items), "stocks, date", today)

if __name__ == "__main__":
    main()
