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
    # 先找完全相符的欄位,再退子字串;keys 由精確到寬鬆
    ks = {(k or "").replace(" ", "").replace("\u3000", ""): k for k in row.keys()}
    for want in keys:
        if want in ks:
            return (row[ks[want]] or "").strip()
    for want in keys:
        for kk, k in ks.items():
            if want in kk:
                return (row[k] or "").strip()
    return ""

def region_of(addr):
    a = addr or ""
    for c in CITIES:
        if a.startswith(c):
            return c.replace("台", "臺")
    return ""

def norm_name(n):
    return re.sub(r"[\s()()【】\-––]", "", (n or ""))

def fetch_mohw_doctor_counts():
    """衛福部 醫療機構與人員基本資料(dataset 15393, ODS)→ {正規化機構名稱: A醫師人數}"""
    try:
        r = requests.get("https://data.gov.tw/dataset/15393", headers=HEAD, timeout=30)
        m = re.search(r"https://www\.mohw\.gov\.tw/dl-[0-9a-zA-Z\-]+\.html", r.text)
        if not m:
            log("mohw: no ODS url found"); return {}
        url = m.group(0)
        log("mohw ODS url:", url)
        rr = requests.get(url, headers=HEAD, timeout=180)
        log("mohw GET ->", rr.status_code, len(rr.content), "bytes")
        import io as _io
        try:
            import pandas as pd
        except ImportError:
            log("mohw: pandas not available"); return {}
        df = pd.read_excel(_io.BytesIO(rr.content), engine="odf")
        log("mohw columns:", list(df.columns)[:12], "rows:", len(df))
        namecol = next((c for c in df.columns if "機構名稱" in str(c)), None)
        doccol = next((c for c in df.columns if "醫師" in str(c) and "中醫" not in str(c) and "牙醫" not in str(c)), None)
        if not namecol or not doccol:
            log("mohw: columns not matched"); return {}
        out = {}
        for _, row in df.iterrows():
            n = norm_name(str(row.get(namecol, "")))
            try:
                v = int(float(row.get(doccol, 0) or 0))
            except Exception:
                v = 0
            if n and v > 0:
                out[n] = v
        log("mohw doctor-count entries:", len(out))
        return out
    except Exception as e:
        log("mohw fail:", e)
        return {}

def fetch_owner_from_nhi(code, sess):
    """健保署特約院所查詢頁(政府網站)抓負責醫師;失敗回 None"""
    try:
        url = "https://info.nhi.gov.tw/INAE1000/INAE1000S02?hOrderno=" + code
        r = sess.get(url, headers=HEAD, timeout=20)
        if r.status_code != 200:
            return None
        t = r.text
        m = re.search(r"負責(?:醫師|人)[^\u4e00-\u9fff]{0,30}([\u4e00-\u9fff]{2,4})", t)
        return m.group(1) if m else None
    except Exception:
        return None

def enrich_owners(out):
    """對已篩出的眼科院所逐家查負責醫師(節流 0.25s;任何失敗不影響主資料)"""
    import time
    try:
        sess = requests.Session()
        ok = fail = 0
        probe = fetch_owner_from_nhi(next((c["code"] for c in out if c.get("code")), ""), sess)
        log("owner probe:", repr(probe))
        if probe is None:
            log("owner enrich: probe failed (page likely JS-rendered) — skip")
            return
        for i, c in enumerate(out):
            if not c.get("code") or c.get("owner"):
                continue
            o = fetch_owner_from_nhi(c["code"], sess)
            if o:
                c["owner"] = o; ok += 1
            else:
                fail += 1
            if i % 100 == 0:
                log("owner enrich progress:", i, "/", len(out), "ok=", ok)
            time.sleep(0.25)
        log("owner enrich done: ok=", ok, "fail=", fail)
    except Exception as e:
        log("owner enrich error:", e)

def fetch_roster_owners():
    """健保特約醫療院所名冊(dataset 168341)→ {醫事機構代碼: 負責醫師}"""
    url = resolve_csv_url("168341", "A21030000I-D2100G-001")
    rows = read_csv(url)
    owners = {}
    for r in rows:
        code = col(r, "醫事機構代碼", "機構代碼")
        owner = col(r, "負責醫師", "負責人")
        if code and owner:
            owners[code] = owner
    log("roster owners:", len(owners))
    if rows:
        log("roster headers:", list(rows[0].keys()))
    return owners

def main():
    log("=== update_clinics SCRAPER v4 ===")
    out, seen = [], set()
    owners = {}
    try:
        owners = fetch_roster_owners()
    except Exception as e:
        log("roster fail:", e)
    doc_counts = fetch_mohw_doctor_counts()
    for label, ds_id, rid in DATASETS:
        log("[%s] dataset %s" % (label, ds_id))
        url = resolve_csv_url(ds_id, rid)
        rows = read_csv(url)
        # 診斷:整列含「眼科」的列數 + 前 2 列樣本
        neye = sum(1 for r in rows if "眼科" in " ".join((v or "") for v in r.values()))
        log("    rows containing 眼科:", neye)
        for r in rows[:2]:
            log("    sample name:", col(r, "醫事機構名稱", "機構名稱"), "| 科別:", col(r, "診療科別"))
        cnt = 0
        dbg = 0
        for row in rows:
            # 最穩篩選:整列任一欄位含「眼科」(名稱或診療科別)
            rowvals = " ".join((v or "") for v in row.values())
            if "眼科" not in rowvals:
                continue
            name = col(row, "醫事機構名稱", "機構名稱", "名稱")
            if not name:
                # 名稱抓不到:用第一個含「眼科」的欄位值當名稱(保底)
                for v in row.values():
                    if v and "眼科" in v and len(v) <= 40:
                        name = v.strip(); break
            if dbg < 3:
                log("    eye-sample:", repr(name), "| 終止欄=", repr(col(row, "終止合約或歇業日期", "終止合約", "歇業")))
                dbg += 1
            if not name:
                continue
            addr = col(row, "地址")
            code = col(row, "醫事機構代碼", "機構代碼", "代碼")
            key = code or (name + addr)
            if key in seen:
                continue
            seen.add(key)
            rec = {
                "name": name, "type": label, "region": region_of(addr), "addr": addr,
                "phone": col(row, "電話"),
                "hours": col(row, "固定看診時段", "看診時段", "服務時段"),
                "code": code,
            }
            if code and owners.get(code):
                rec["owner"] = owners[code]
            nd = doc_counts.get(norm_name(name))
            if nd:
                rec["ndoc"] = nd
            out.append(rec)
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
    enrich_owners(out)
    # 抓到 0 筆時保留原有 clinics.json(不要覆蓋成空的)
    if not out:
        log("!! 0 institutions parsed — keeping existing clinics.json, NOT overwriting")
        return
    with open("clinics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log("total %d eye institutions written" % len(out))

if __name__ == "__main__":
    main()
