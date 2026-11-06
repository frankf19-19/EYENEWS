#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TFDA 眼科醫材 / 眼藥 許可證動態 — 每週更新(免費、官方開放資料)
來源:食藥署「醫療器材許可證資料集」(data.gov.tw 9576)、「未註銷藥品許可證資料集」(9123)。
篩出眼科相關(醫器主類別 M 眼科學、或品名含眼科關鍵字;藥品以劑型含「眼」為主),
輸出 tfda_eye.json:最新核准、近期註銷、申請商/類別統計。於 GitHub Actions 執行。
"""
import sys, json, io, csv, re, zipfile, datetime, os, requests
from collections import Counter

HEAD = {"User-Agent": "Mozilla/5.0 EyeVisionHub-TFDA/1.0"}
DEV_DS, DRUG_DS = "9576", "9123"
DEV_FALLBACK = "https://data.fda.gov.tw/data/opendata/export/68/csv"
DRUG_FALLBACK = "https://data.fda.gov.tw/data/opendata/export/37/csv"

EYE_DEV_RE = re.compile(r"眼|隱形眼鏡|角膜|水晶體|視力|驗光|瞳|視網膜|淚|contact lens|intraocular|ophthalm|keratom|retina|tonomet|phoropter|slit ?lamp", re.I)
NOT_EYE_RE = re.compile(r"眼鏡框|護目鏡|眼罩(?!.*治療)|洗眼器|眼部按摩|監視器|呼吸|血壓|心臟|超音波(?!.*眼)", re.I)
TAGS = [
    ("角膜塑型", re.compile(r"角膜塑型|塑型片|ortho-?k|orthokeratolog", re.I)),
    ("隱形眼鏡", re.compile(r"隱形眼鏡|contact lens", re.I)),
    ("人工水晶體", re.compile(r"人工水晶體|intraocular lens|\bIOL\b", re.I)),
    ("眼科雷射", re.compile(r"雷射|laser|excimer|femtosecond", re.I)),
    ("診斷儀器", re.compile(r"OCT|斷層|眼底|地形|驗光|視野|眼壓|tonomet|生物測量|biomet|角膜內皮|裂隙燈|slit", re.I)),
    ("手術器械/耗材", re.compile(r"手術|刀|探頭|黏彈|套件|注射|植入|引流|超音波乳化|phaco|vitrect|玻璃體", re.I)),
    ("人工淚液/護理", re.compile(r"淚液|潤滑|保養液|清潔液|護理|保存液", re.I)),
    ("阿托品", re.compile(r"atropine|阿托品", re.I)),
    ("青光眼藥", re.compile(r"青光眼|眼壓|latanoprost|timolol|bimatoprost|travoprost|brimonidine|dorzolamide|brinzolamide|tafluprost", re.I)),
    ("乾眼藥", re.compile(r"乾眼|cyclosporin|ciclosporin|diquafosol|hyaluron|lifitegrast", re.I)),
    ("抗VEGF/眼內注射", re.compile(r"aflibercept|ranibizumab|faricimab|brolucizumab|bevacizumab|玻璃體內", re.I)),
    ("抗生素/抗發炎", re.compile(r"moxifloxacin|levofloxacin|tobramycin|dexamethasone|prednisolone|fluorometholone|ketorolac|nepafenac|bromfenac", re.I)),
    ("抗過敏", re.compile(r"olopatadine|epinastine|ketotifen|bepotastine|過敏", re.I)),
]

def log(*a): sys.stderr.write(" ".join(str(x) for x in a) + "\n")

def resolve_csv(ds, fallback):
    try:
        j = requests.get("https://data.gov.tw/api/v2/rest/dataset/" + ds, headers=HEAD, timeout=40).json()
        for d in (j.get("result") or {}).get("distribution", []):
            if (d.get("resourceFormat") or "").upper() == "CSV" and d.get("resourceDownloadUrl"):
                return d["resourceDownloadUrl"]
    except Exception as e:
        log("resolve fail", ds, e)
    return fallback

def read_rows(url):
    for i in range(3):
        try:
            r = requests.get(url, headers=HEAD, timeout=300); r.raise_for_status(); raw = r.content; break
        except Exception as e:
            log("download retry", i + 1, e); raw = None
    if not raw: return []
    if raw[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(raw)); raw = z.read(z.namelist()[0])
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            txt = raw.decode(enc); break
        except Exception:
            txt = None
    if txt is None: return []
    return list(csv.DictReader(io.StringIO(txt)))

def d8(s):
    s = (s or "").strip().replace("/", "-")
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else ""

def tags_of(text):
    return [t for t, rx in TAGS if rx.search(text)]

def clean(s): return re.sub(r"\s+", " ", (s or "")).strip()

def build_devices():
    rows = read_rows(resolve_csv(DEV_DS, DEV_FALLBACK))
    log("devices rows:", len(rows))
    out = []
    for r in rows:
        cats = " ".join(r.get(k, "") for k in ("醫器主類別一", "醫器次類別一", "醫器主類別二", "醫器次類別二", "醫器主類別三", "醫器次類別三"))
        name = clean(r.get("中文品名")); en = clean(r.get("英文品名"))
        is_m = re.search(r"(^|\s)M\s*眼科", cats) is not None
        hit = is_m or EYE_DEV_RE.search(name + " " + en)
        if not hit: continue
        if not is_m and NOT_EYE_RE.search(name + " " + en): continue
        sub = next((r.get(k, "") for k in ("醫器次類別一", "醫器次類別二", "醫器次類別三") if "眼科" in (r.get(k.replace("次", "主"), "") or "")), r.get("醫器次類別一", ""))
        limit = r.get("限制項目", "") or ""
        out.append({
            "lic": clean(r.get("許可證字號")), "doc": clean(r.get("通關簽審文件編號")),
            "name": name, "en": en, "cls": clean(r.get("醫療器材級數")), "sub": clean(sub),
            "applicant": clean(r.get("申請商名稱")), "maker": clean(r.get("製造商名稱")), "country": clean(r.get("製造廠國別")),
            "issued": d8(r.get("發證日期")), "expires": d8(r.get("有效日期")),
            "status": clean(r.get("註銷狀態")), "cancelled": d8(r.get("註銷日期")), "reason": clean(r.get("註銷理由")),
            "origin": "輸入" if "輸" in limit else ("製造" if "製" in limit else ""),
            "changed": d8(r.get("異動日期")),
            "tags": tags_of(name + " " + en + " " + cats),
        })
    return out

def build_drugs():
    rows = read_rows(resolve_csv(DRUG_DS, DRUG_FALLBACK))
    log("drugs rows:", len(rows))
    out = []
    for r in rows:
        form = clean(r.get("劑型")); name = clean(r.get("中文品名")); en = clean(r.get("英文品名"))
        ind = clean(r.get("適應症")); comp = clean(r.get("主成分略述"))
        is_eye = ("眼" in form) or re.search(r"青光眼|乾眼|白內障|黃斑|眼壓|視網膜|結膜炎|角膜|近視", ind or "") and re.search(r"眼|點眼|滴", form + name)
        if not is_eye: continue
        out.append({
            "lic": clean(r.get("許可證字號")), "doc": clean(r.get("通關簽審文件編號")),
            "name": name, "en": en, "form": form, "ind": ind[:160], "comp": comp[:120],
            "applicant": clean(r.get("申請商名稱")), "maker": clean(r.get("製造商名稱")), "country": clean(r.get("製造廠國別")),
            "issued": d8(r.get("發證日期")), "expires": d8(r.get("有效日期")),
            "status": clean(r.get("註銷狀態")), "cancelled": d8(r.get("註銷日期")), "reason": clean(r.get("註銷理由")),
            "origin": "輸入" if "輸" in (r.get("許可證字號") or "") else "製造",
            "tags": tags_of(name + " " + en + " " + comp + " " + ind),
        })
    return out

def summarize(items, kind):
    active = [i for i in items if not i["status"]]
    year = datetime.date.today().year
    new_year = [i for i in active if i["issued"].startswith(str(year))]
    top_app = Counter(i["applicant"] for i in active).most_common(15)
    key = "sub" if kind == "dev" else "form"
    top_cat = Counter(i.get(key, "") for i in active if i.get(key)).most_common(12)
    tagc = Counter(t for i in active for t in i["tags"]).most_common(14)
    return {"total": len(items), "active": len(active), "new_this_year": len(new_year),
            "top_applicants": top_app, "top_categories": top_cat, "tag_counts": tagc}

def main():
    devs = build_devices(); drugs = build_drugs()
    log("eye devices:", len(devs), "| eye drugs:", len(drugs))
    if not devs and not drugs:
        log("!! nothing parsed — keeping existing tfda_eye.json"); return
    def recent(items, n):
        return sorted([i for i in items if i["issued"]], key=lambda x: x["issued"], reverse=True)[:n]
    def cancelled(items, n):
        return sorted([i for i in items if i["cancelled"]], key=lambda x: x["cancelled"], reverse=True)[:n]
    data = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "衛福部食品藥物管理署 開放資料:醫療器材許可證資料集、未註銷藥品許可證資料集",
        "dev": {"stats": summarize(devs, "dev"), "recent": recent(devs, 600), "cancelled": cancelled(devs, 200)},
        "drug": {"stats": summarize(drugs, "drug"), "recent": recent(drugs, 400), "cancelled": cancelled(drugs, 120)},
    }
    with open("tfda_eye.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log("wrote tfda_eye.json")

if __name__ == "__main__":
    main()
