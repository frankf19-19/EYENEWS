#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下載衛福部健保署「健保特約醫事機構」開放資料(診所 + 各級醫院),篩選有「眼科」者 → clinics.json
於 GitHub Actions 執行。欄位:名稱/區域/地址/電話/看診時間(固定看診時段)/類型。
負責醫師與門診醫師名單健保開放資料未提供,故不含(前端提供官方查詢連結)。
"""
import json, sys, io, csv, datetime, re
try:
    import requests
except ImportError:
    sys.stderr.write("need requests\n"); raise

HEAD = {"User-Agent": "Mozilla/5.0 (EyeVisionHub-Clinics/1.0)"}

# (類型顯示, data.gov.tw dataset id, 已知 NHI rId 備援)
DATASETS = [
    ("診所",     "39283", "A21030000I-D21004-009"),
    ("地區醫院", "39282", "A21030000I-D21003-003"),
    ("區域醫院", "39281", "A21030000I-D21002-005"),
    ("醫學中心", "39280", "A21030000I-D21001-004"),
]
CITIES = ["臺北市","台北市","新北市","基隆市","桃園市","新竹市","新竹縣","苗栗縣","臺中市","台中市",
          "彰化縣","南投縣","雲林縣","嘉義市","嘉義縣","臺南市","台南市","高雄市","屏東縣","宜蘭縣",
          "花蓮縣","臺東縣","台東縣","澎湖縣","金門縣","連江縣"]

def resolve_csv_url(ds_id, fallback_rid):
    # 從 data.gov.tw 資料集頁面抓取「目前」的 CSV 下載網址(rId 會隨每次更新變動)
    try:
        r = requests.get("https://data.gov.tw/dataset/" + ds_id, headers=HEAD, timeout=25)
        m = re.search(r"info\.nhi\.gov\.tw/api/iode0000s01/Dataset\?rId=[A-Za-z0-9\-]+", r.text)
        if m:
            return "https://" + m.group(0)
    except Exception as e:
        sys.stderr.write("[%s] resolve fail: %s\n" % (ds_id, e))
    # 再試 data.gov.tw API v2
    try:
        r = requests.get("https://data.gov.tw/api/v2/rest/dataset/" + ds_id, headers=HEAD, timeout=25)
        m = re.search(r"info\.nhi\.gov\.tw/api/iode0000s01/Dataset\?rId=[A-Za-z0-9\-]+", r.text)
        if m:
            return "https://" + m.group(0)
    except Exception:
        pass
    return "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=" + fallback_rid

def read_csv(url):
    r = requests.get(url, headers=HEAD, timeout=60)
    raw = r.content
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            text = raw.decode(enc)
            if "," in text and "\n" in text:
                return list(csv.DictReader(io.StringIO(text)))
        except Exception:
            continue
    return []

def col(row, *keys):
    for k in row.keys():
        for kk in keys:
            if kk in (k or ""):
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
        url = resolve_csv_url(ds_id, rid)
        try:
            rows = read_csv(url)
        except Exception as e:
            sys.stderr.write("[%s] download fail: %s\n" % (label, e)); rows = []
        cnt = 0
        for row in rows:
            name = col(row, "機構名稱", "名稱")
            spec = col(row, "診療科別", "科別", "服務項目")
            if not name:
                continue
            # 篩選:有眼科(科別含眼科,或診所名稱含眼科)
            is_eye = ("眼科" in spec) or ("眼科" in name)
            if not is_eye:
                continue
            # 排除已終止/歇業
            term = col(row, "終止合約", "歇業")
            if term:
                continue
            addr = col(row, "地址")
            code = col(row, "機構代碼", "代碼")
            key = code or (name + addr)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "name": name,
                "type": label,
                "region": region_of(addr),
                "addr": addr,
                "phone": col(row, "電話"),
                "hours": col(row, "固定看診時段", "看診時段", "服務時段"),
                "code": code,
            })
            cnt += 1
        sys.stderr.write("[%s] %d eye institutions\n" % (label, cnt))
    # 排序:區域(依序)、名稱
    order = {c.replace("台","臺"): i for i, c in enumerate(
        ["臺北市","新北市","基隆市","桃園市","新竹市","新竹縣","苗栗縣","臺中市","彰化縣","南投縣",
         "雲林縣","嘉義市","嘉義縣","臺南市","高雄市","屏東縣","宜蘭縣","花蓮縣","臺東縣","澎湖縣","金門縣","連江縣"])}
    out.sort(key=lambda c: (order.get(c["region"], 99), c["name"]))
    data = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "衛福部中央健康保險署 健保特約醫事機構開放資料",
        "clinics": out,
    }
    with open("clinics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    sys.stderr.write("total %d eye institutions written\n" % len(out))

if __name__ == "__main__":
    main()
