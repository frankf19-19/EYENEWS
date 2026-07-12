#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全球臨床試驗 — 每日更新腳本(免費、免金鑰)
依「眼視光/眼科類別」查詢 ClinicalTrials.gov 官方 API v2,寫入 trials.json。
由 GitHub Actions 每日排程執行。※ 完全免費、不需付費 API 金鑰。
"""
import json, time, os, sys, datetime
import urllib.request, urllib.parse

API = "https://clinicaltrials.gov/api/v2/studies"
UA = "eye-vision-hub"
PAGESIZE = 100  # 每類最多筆數(調高以涵蓋更多試驗)

# 對應前端臨床類別(與臨床文獻相同的 8 類)
QUERIES = {
    "myopia":      {"cond": "myopia", "term": "control OR orthokeratology OR atropine OR defocus OR progression OR axial"},
    "contactlens": {"cond": "contact lens", "term": ""},
    "lens":        {"cond": "", "term": "spectacle lens OR presbyopia OR progressive addition lens OR optometry"},
    "refractive":  {"cond": "refractive surgery OR myopia", "term": "LASIK OR SMILE OR ICL OR PRK OR phakic"},
    "cataract":    {"cond": "cataract", "term": "intraocular lens OR phacoemulsification OR IOL"},
    "glaucoma":    {"cond": "glaucoma", "term": ""},
    "retina":      {"cond": "macular degeneration OR diabetic macular edema OR retinal vein occlusion", "term": "anti-VEGF OR aflibercept OR ranibizumab OR faricimab"},
    "dryeye":      {"cond": "dry eye OR meibomian gland dysfunction", "term": ""},
}

STATUS_MAP = {
    "RECRUITING": "招募中", "NOT_YET_RECRUITING": "尚未招募",
    "ENROLLING_BY_INVITATION": "邀請制招募", "ACTIVE_NOT_RECRUITING": "進行中(不招募)",
    "COMPLETED": "已完成", "SUSPENDED": "暫停", "TERMINATED": "已終止",
    "WITHDRAWN": "已撤回", "UNKNOWN": "狀態未知", "AVAILABLE": "可取得",
}
PHASE_MAP = {
    "NA": "不適用", "EARLY_PHASE1": "早期一期", "PHASE1": "一期",
    "PHASE2": "二期", "PHASE3": "三期", "PHASE4": "四期",
}
TYPE_MAP = {"INTERVENTIONAL": "介入型", "OBSERVATIONAL": "觀察型", "EXPANDED_ACCESS": "擴大使用"}

COUNTRY_MAP = [
    ("Taiwan", "台灣"), ("Hong Kong", "香港"), ("China", "中國"), ("Japan", "日本"),
    ("Korea", "韓國"), ("Singapore", "新加坡"), ("Malaysia", "馬來西亞"), ("India", "印度"),
    ("Thailand", "泰國"), ("Vietnam", "越南"), ("Australia", "澳洲"), ("New Zealand", "紐西蘭"),
    ("United States", "美國"), ("United Kingdom", "英國"), ("Canada", "加拿大"),
    ("Germany", "德國"), ("France", "法國"), ("Netherlands", "荷蘭"), ("Spain", "西班牙"),
    ("Italy", "義大利"), ("Switzerland", "瑞士"), ("Sweden", "瑞典"), ("Denmark", "丹麥"),
    ("Belgium", "比利時"), ("Ireland", "愛爾蘭"), ("Turkey", "土耳其"), ("Israel", "以色列"),
    ("Brazil", "巴西"), ("Mexico", "墨西哥"), ("Egypt", "埃及"), ("Iran", "伊朗"),
    ("Poland", "波蘭"), ("Austria", "奧地利"), ("Portugal", "葡萄牙"), ("Greece", "希臘"),
    ("Saudi Arabia", "沙烏地"), ("United Arab Emirates", "阿聯"),
]


def zh_country(name):
    for kw, zh in COUNTRY_MAP:
        if kw.lower() == (name or "").strip().lower():
            return zh
    return name or ""


def _get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write(f"  retry {i+1}: {e}\n")
            time.sleep(2 + i * 2)
    return None


def fetch(cond, term, page_size=PAGESIZE):
    params = {"format": "json", "pageSize": str(page_size),
              "sort": "LastUpdatePostDate:desc"}
    if cond:
        params["query.cond"] = cond
    if term:
        params["query.term"] = term
    url = API + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    if not raw:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    return data.get("studies", []) or []


def parse(studies):
    out = []
    for s in studies:
        ps = s.get("protocolSection", {}) or {}
        idm = ps.get("identificationModule", {}) or {}
        nct = idm.get("nctId", "")
        title = idm.get("briefTitle") or idm.get("officialTitle") or ""
        if not nct or not title:
            continue
        stm = ps.get("statusModule", {}) or {}
        status = stm.get("overallStatus", "") or ""
        start = ((stm.get("startDateStruct") or {}).get("date") or "")
        comp = ((stm.get("completionDateStruct") or {}).get("date")
                or (stm.get("primaryCompletionDateStruct") or {}).get("date") or "")
        updated = ((stm.get("lastUpdatePostDateStruct") or {}).get("date") or "")
        dm = ps.get("designModule", {}) or {}
        phases = dm.get("phases", []) or []
        phase = "/".join(PHASE_MAP.get(p, p) for p in phases) if phases else ""
        stype = TYPE_MAP.get(dm.get("studyType", ""), dm.get("studyType", "") or "")
        enroll = ((dm.get("enrollmentInfo") or {}).get("count") or "")
        conds = (ps.get("conditionsModule", {}) or {}).get("conditions", []) or []
        intrs = []
        for it in (ps.get("armsInterventionsModule", {}) or {}).get("interventions", []) or []:
            nm = it.get("name", "")
            ty = it.get("type", "")
            if nm:
                intrs.append((ty + ": " + nm) if ty else nm)
        sponsor = ((ps.get("sponsorCollaboratorsModule", {}) or {}).get("leadSponsor", {}) or {}).get("name", "")
        locs = (ps.get("contactsLocationsModule", {}) or {}).get("locations", []) or []
        countries = []
        for L in locs:
            c = (L.get("country") or "").strip()
            if c and c not in countries:
                countries.append(c)
        zh = []
        for c in countries:
            z = zh_country(c)
            if z not in zh:
                zh.append(z)
        country = "" if not zh else (zh[0] if len(zh) == 1 else zh[0] + " 等")
        out.append({
            "nct": nct, "title": title,
            "status": status, "status_zh": STATUS_MAP.get(status, status),
            "phase": phase, "type": stype,
            "conditions": conds[:6], "interventions": intrs[:6],
            "sponsor": sponsor, "country": country,
            "enroll": enroll, "start": start, "completion": comp, "updated": updated,
        })
    return out


def main():
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "ClinicalTrials.gov API v2(全球臨床試驗登錄)",
        "items": {},
    }
    total = 0
    for key, q in QUERIES.items():
        sys.stderr.write(f"[{key}] querying ClinicalTrials.gov…\n")
        studies = fetch(q["cond"], q["term"])
        items = parse(studies)
        result["items"][key] = items
        total += len(items)
        sys.stderr.write(f"[{key}] {len(items)} trials\n")
        time.sleep(0.5)

    if total == 0 and os.path.exists("trials.json"):
        sys.stderr.write("No results — keeping existing trials.json\n")
        return
    with open("trials.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote trials.json ({total} trials)\n")


if __name__ == "__main__":
    main()
