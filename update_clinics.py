#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下載衛福部健保署「健保特約醫事機構」開放資料(診所 + 各級醫院),篩選有眼科者 → clinics.json
於 GitHub Actions 執行。含詳細 log 便於除錯。
"""
import json, sys, io, csv, datetime, re
try:
    import requests
except ImportError:
    sys.stderr.write("need requests\n"); raise

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 EyeVisionHub/1.0"}

DATASETS = [
    ("診所",     "39283", "A21030000I-D21004-009"),
    ("地區醫院", "39282", "A21030000I-D21003-003"),
    ("區域醫院", "39281", "A21030000I-D21002-005"),
    ("醫學中心", "39280", "A21030000I-D21001-004"),
]
CITIES = ["臺北市","台北市","新北市","基隆市","桃園市","新竹市","新竹縣","苗栗縣","臺中市","台中市",
          "彰化縣","南投縣","雲林縣","嘉義市","嘉義縣","臺南市","台南市","高雄市","屏東縣","宜蘭縣",
          "花蓮縣","臺東縣","台東縣","澎湖縣","金門縣","連江縣"]

def log(*a):
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")

def resolve_csv_url(ds_id, fallback_rid):
    pat = r"info\.nhi\.gov\.tw/api/iode0000s01/Dataset\?rId=[A-Za-z0-9\-]+"
    for u in ("https://data.gov.tw/dataset/" + ds_id,
              "https://data.gov.tw/api/v2/rest/dataset/" + ds_id):
        try:
            r = requests.get(u, headers=HEAD, timeout=30)
            m = re.search(pat, r.text)
            if m:
                log("    resolved via", u, "->", m.group(0))
                return "https://" + m.group(0)
        except Exception as e:
            log("    resolve fail", u, e)
    log("    using fallback rId", fallback_rid)
    return "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=" + fallback_rid

def read_csv(url):
    try:
        r = requests.get(url, headers=HEAD, timeout=120)
    except Exception as e:
        log("    download error:", e); return []
    raw = r.content
    log("    GET ->", r.status_code, len(raw), "bytes,", r.headers.get("Content-Type", ""))
    text = None
    for enc in ("utf-8-sig", "utf-8", "big5-hkscs", "big5", "cp950"):
        try:
            text = raw.decode(enc); log("    decoded as", enc); break
        except Exception:
            continue
    if text is None:
        text = raw.decode("utf-8", "ignore")
    first = text.split("\n", 1)[0][:250]
    log("    first line:", first)
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception as e:
        log("    csv parse fail:", e); return []
    log("    parsed rows:", len(rows), "| headers:", (list(rows[0].keys()) if rows else []))
    return rows

def col(row, *keys):
    for k in row.keys():
        kk = (k or "").replace(" ", "")
        for want in keys:
            if want in kk:
                return (row[k] or "").strip()
    return ""

def region_of(addr):
    a = addr or ""
    for c in CITIES:
        if a.startswith(c):
            return c.replace("台", "臺")
    return ""

def main():
    out, seen = [], set()
    for label, ds_id, rid in DATASETS:
        log("[%s] dataset %s" % (label, ds_id))
        url = resolve_csv_url(ds_id, rid)
        rows = read_csv(url)
        cnt = 0
        for row in rows:
            name = col(row, "機構名稱", "名稱")
            spec = col(row, "診療科別", "科別", "服務項目", "服務科別")
            if not name:
                continue
            if ("眼科" not in spec) and ("眼科" not in name):
                continue
            if col(row, "終止合約", "歇業", "終止"):
                continue
            addr = col(row, "地址")
            code = col(row, "機構代碼", "代碼")
            key = code or (name + addr)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "name": name, "type": label, "region": region_of(addr), "addr": addr,
                "phone": col(row, "電話"),
                "hours": col(row, "固定看診時段", "看診時段", "服務時段", "看診時間"),
                "code": code,
            })
            cnt += 1
        log("[%s] matched %d eye institutions" % (label, cnt))
    order = {c.replace("台", "臺"): i for i, c in enumerate(
        ["臺北市","新北市","基隆市","桃園市","新竹市","新竹縣","苗栗縣","臺中市","彰化縣","南投縣",
         "雲林縣","嘉義市","嘉義縣","臺南市","高雄市","屏東縣","宜蘭縣","花蓮縣","臺東縣","澎湖縣","金門縣","連江縣"])}
    out.sort(key=lambda c: (order.get(c["region"], 99), c["name"]))
    data = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "衛福部中央健康保險署 健保特約醫事機構開放資料",
        "clinics": out,
    }
    # 抓到 0 筆時保留原有 clinics.json(不要覆蓋成空的)
    if not out:
        log("!! 0 institutions parsed — keeping existing clinics.json, NOT overwriting")
        return
    with open("clinics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log("total %d eye institutions written" % len(out))

if __name__ == "__main__":
    main()
