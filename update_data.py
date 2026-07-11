#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
眼視光/眼科臨床文獻 — 每日更新腳本(免費、免金鑰)
依「臨床類別」查詢 PubMed 近期文獻,並用免費翻譯端點產生繁中標題與重點,寫入 data.json。

資料來源: NCBI E-utilities(esearch + efetch)。翻譯: translate.googleapis.com 免費端點。
由 GitHub Actions 每日排程執行。可在 repo Secrets 設 NCBI_API_KEY 提高速率(非必要)。
※ 完全免費、不需付費 API 金鑰。
"""
import json, time, os, sys, datetime, re
import xml.etree.ElementTree as ET
import urllib.request, urllib.parse

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "eye-vision-hub"
EMAIL = os.environ.get("NCBI_EMAIL", "example@example.com")
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()

# 依臨床類別的 PubMed 查詢(對應前端 LIT_LABEL)
QUERIES = {
    "myopia":     '(myopia) AND (control OR progression OR "axial length") AND (orthokeratology OR atropine OR defocus OR "red light" OR outdoor OR spectacle OR "contact lens")',
    "contactlens":'("contact lens" OR "contact lenses") AND (silicone hydrogel OR "ocular surface" OR comfort OR "dry eye" OR keratitis OR multifocal OR toric)',
    "lens":       '("spectacle lens" OR "progressive addition lens" OR "presbyopia" OR "ophthalmic lens" OR optometry) AND (visual OR performance OR correction)',
    "refractive": '(LASIK OR SMILE OR "small incision lenticule" OR PRK OR "refractive surgery" OR "phakic intraocular lens" OR ICL) AND (outcomes OR safety OR "dry eye")',
    "cataract":   '(cataract) AND ("intraocular lens" OR IOL OR phacoemulsification OR "femtosecond") AND (outcomes OR EDOF OR multifocal OR toric)',
    "glaucoma":   '(glaucoma) AND ("intraocular pressure" OR MIGS OR "minimally invasive" OR trabeculectomy OR "selective laser" OR prostaglandin)',
    "retina":     '("age-related macular degeneration" OR "diabetic macular edema" OR "retinal vein occlusion") AND (anti-VEGF OR aflibercept OR ranibizumab OR faricimab)',
    "dryeye":     '("dry eye" OR "meibomian gland dysfunction") AND (cyclosporine OR lifitegrast OR "intense pulsed light" OR treatment OR management)',
}

RELDATE_DAYS = 3650   # 近 10 年
RETMAX = 120          # 每類上限(檔案大小考量;不限年份,跨年代收錄)


def _params(extra):
    p = {"tool": TOOL, "email": EMAIL}
    if API_KEY:
        p["api_key"] = API_KEY
    p.update(extra)
    return urllib.parse.urlencode(p)


def _get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": TOOL})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write(f"  retry {i+1}: {e}\n")
            time.sleep(2 + i * 2)
    return None


def esearch(query, sort="date", reldate=None, retmax=RETMAX):
    p = {"db": "pubmed", "term": query, "retmax": retmax,
         "sort": sort, "datetype": "pdat"}
    if reldate:
        p["reldate"] = reldate
    url = f"{EUTILS}/esearch.fcgi?" + _params(p)
    raw = _get(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
        return [e.text for e in root.findall(".//IdList/Id") if e.text]
    except ET.ParseError:
        return []


def _text(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else ""


# ---- 國家(作者單位)與研究類型解析 ----
COUNTRY_MAP = [
    ("Taiwan", "台灣"), ("China", "中國"), ("Hong Kong", "香港"), ("Japan", "日本"),
    ("Korea", "韓國"), ("Singapore", "新加坡"), ("Malaysia", "馬來西亞"), ("India", "印度"),
    ("Thailand", "泰國"), ("Vietnam", "越南"), ("Australia", "澳洲"), ("New Zealand", "紐西蘭"),
    ("United States", "美國"), ("USA", "美國"), (" U.S.A", "美國"), (" US ", "美國"),
    ("United Kingdom", "英國"), ("England", "英國"), ("Scotland", "英國"), (" UK", "英國"),
    ("Canada", "加拿大"), ("Germany", "德國"), ("France", "法國"), ("Netherlands", "荷蘭"),
    ("Spain", "西班牙"), ("Italy", "義大利"), ("Switzerland", "瑞士"), ("Sweden", "瑞典"),
    ("Denmark", "丹麥"), ("Norway", "挪威"), ("Belgium", "比利時"), ("Ireland", "愛爾蘭"),
    ("Austria", "奧地利"), ("Portugal", "葡萄牙"), ("Poland", "波蘭"), ("Turkey", "土耳其"),
    ("Israel", "以色列"), ("Brazil", "巴西"), ("Mexico", "墨西哥"), ("Saudi", "沙烏地"),
    ("Egypt", "埃及"), ("Iran", "伊朗"), ("Finland", "芬蘭"), ("Greece", "希臘"),
]
def parse_country(art):
    affs = [ "".join(a.itertext()).strip() for a in art.findall(".//AffiliationInfo/Affiliation") ]
    affs = [a for a in affs if a]
    if not affs:
        return ""
    # 國家幾乎都在單位字串『末端』;只比對最後兩個逗號片段,避免誤中大學名(如 National Taiwan University)
    text = affs[0].rstrip(". ")
    segs = [s.strip() for s in text.split(",") if s.strip()]
    tail = ", ".join(segs[-2:]) if len(segs) >= 2 else text
    tail_l = " " + tail.lower() + " "
    for kw, zh in COUNTRY_MAP:
        if kw.lower() in tail_l:
            return zh
    return ""

PTYPE_PRIORITY = [
    ("Randomized Controlled Trial", "隨機對照試驗(RCT)"),
    ("Meta-Analysis", "統合分析"),
    ("Systematic Review", "系統性回顧"),
    ("Multicenter Study", "多中心研究"),
    ("Clinical Trial, Phase III", "臨床試驗(III期)"),
    ("Clinical Trial, Phase II", "臨床試驗(II期)"),
    ("Clinical Trial", "臨床試驗"),
    ("Observational Study", "觀察性研究"),
    ("Cohort Studies", "世代研究"),
    ("Comparative Study", "比較性研究"),
    ("Case Reports", "病例報告"),
    ("Review", "文獻回顧"),
    ("Guideline", "臨床指引"),
    ("Practice Guideline", "臨床指引"),
]
def parse_ptype(art):
    types = { ("".join(p.itertext()).strip()) for p in art.findall(".//PublicationType") }
    for kw, zh in PTYPE_PRIORITY:
        if kw in types:
            return zh
    return ""


def efetch(pmids):
    if not pmids:
        return []
    url = f"{EUTILS}/efetch.fcgi?" + _params({
        "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
    })
    raw = _get(url)
    if not raw:
        return []
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    for art in root.findall(".//PubmedArticle"):
        pmid = _text(art, ".//PMID")
        title = _text(art, ".//ArticleTitle")
        journal = _text(art, ".//Journal/ISOAbbreviation") or _text(art, ".//Journal/Title")
        year = _text(art, ".//JournalIssue/PubDate/Year")
        if not year:
            md = _text(art, ".//JournalIssue/PubDate/MedlineDate")
            year = md[:4] if md else ""
        parts, concl = [], ""
        for ab in art.findall(".//Abstract/AbstractText"):
            txt = "".join(ab.itertext()).strip()
            if not txt:
                continue
            label = (ab.get("Label") or "").strip()
            parts.append((label + ": " if label else "") + txt)
            up = label.upper()
            if "CONCLUSION" in up or "RESULT" in up:
                concl = txt
        full = " ".join(parts).strip()
        # 顯示用:優先結論,否則整段摘要開頭
        summary = concl or full
        if len(summary) > 340:
            cut = summary[:340]
            dot = cut.rfind(". ")
            summary = (cut[:dot + 1] if dot > 170 else cut) + " …"
        # 搜尋用:保留較長的完整摘要(英文原文,免翻譯即可搜)
        abstract = full[:900]
        country = parse_country(art)
        ptype = parse_ptype(art)
        if title:
            out.append({"title": title, "journal": journal, "date": year,
                        "pmid": pmid, "summary": summary, "abstract": abstract,
                        "country": country, "ptype": ptype})
    return out


# ---- 免費翻譯(translate.googleapis.com,無需金鑰) ----
def translate(text, retries=3):
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) > 1200:
        text = text[:1200]
    q = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-TW", "dt": "t", "q": text})
    url = "https://translate.googleapis.com/translate_a/single?" + q
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
        except Exception as e:
            sys.stderr.write(f"  translate retry {i+1}: {e}\n")
            time.sleep(2.5)
    return ""


def translate_batch(texts, budget_until, chunk=20):
    """批次翻譯:一次多則(換行分隔),超過時間預算即停。回傳 index->中文。"""
    out = {}
    for start in range(0, len(texts), chunk):
        if time.time() > budget_until:
            sys.stderr.write("translate budget reached — stop translating\n")
            break
        part = [(texts[start + k] or "").replace("\n", " ").strip() for k in range(min(chunk, len(texts) - start))]
        zh = translate("\n".join(part))
        lines = zh.split("\n") if zh else []
        if len(lines) == len(part):
            for k, ln in enumerate(lines):
                if ln.strip():
                    out[start + k] = ln.strip()
        time.sleep(0.6)
    return out


EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _striptxt(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def country_from_text(text):
    text = (text or "").rstrip(". ")
    if not text:
        return ""
    segs = [s.strip() for s in text.split(",") if s.strip()]
    tail = ", ".join(segs[-2:]) if len(segs) >= 2 else text
    tl = " " + tail.lower() + " "
    for kw, zh in COUNTRY_MAP:
        if kw.lower() in tl:
            return zh
    return ""


def ptype_from_list(types):
    tset = set(x for x in (types or []) if isinstance(x, str))
    for kw, zh in PTYPE_PRIORITY:
        if kw in tset:
            return zh
    return ""


def europepmc(query, retmax):
    """Europe PMC REST(免金鑰):涵蓋 PubMed 之外的全球文獻/全文/預印本。"""
    url = EUROPEPMC + "?" + urllib.parse.urlencode({
        "query": query, "format": "json", "pageSize": str(min(retmax, 100)),
        "resultType": "core", "sort": "CITED desc",   # 高被引=全年代最具影響力(不限年份)
    })
    raw = _get(url)
    if not raw:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    out = []
    for r in ((data.get("resultList") or {}).get("result") or []):
        title = _striptxt(r.get("title", "")).rstrip(".")
        if not title:
            continue
        pmid = str(r.get("pmid", "") or "")
        journal = (((r.get("journalInfo") or {}).get("journal") or {}).get("title")
                   or r.get("journalTitle") or "")
        date = (r.get("firstPublicationDate") or r.get("pubYear") or "")
        full = _striptxt(r.get("abstractText", ""))
        summary = full
        if len(summary) > 340:
            cut = summary[:340]
            dot = cut.rfind(". ")
            summary = (cut[:dot + 1] if dot > 170 else cut) + " …"
        abstract = full[:900]
        ptl = (r.get("pubTypeList") or {}).get("pubType")
        if isinstance(ptl, str):
            ptl = [ptl]
        ptype = ptype_from_list(ptl)
        aff = ""
        try:
            a0 = ((r.get("authorList") or {}).get("author") or [])[0]
            det = (a0.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or []
            if det:
                aff = det[0].get("affiliation", "")
        except Exception:
            aff = ""
        if not aff:
            aff = r.get("affiliation", "") or ""
        out.append({"title": title, "journal": journal, "date": (date or "")[:10],
                    "pmid": pmid, "summary": summary, "abstract": abstract,
                    "country": country_from_text(aff), "ptype": ptype})
    return out


def merge_dedup(*lists, cap=None):
    """依傳入順序(相關性→最新→高被引)去重保留,不依日期截斷,才能保住舊經典。"""
    seen, merged = set(), []
    for lst in lists:
        for it in (lst or []):
            k = (it.get("pmid") or "").strip() or re.sub(r"\W+", "", (it.get("title") or "").lower())[:80]
            if not k or k in seen:
                continue
            seen.add(k)
            merged.append(it)
    return merged[:cap] if cap else merged


def main():
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "PubMed(NCBI)+ Europe PMC;不限年份(相關性/高被引跨年代);中文為免費自動翻譯",
        "items": {},
    }
    flat = []
    for key, query in QUERIES.items():
        sys.stderr.write(f"[{key}] searching…\n")
        # 強制跨年代:分三個發表年代區間各抓一批(舊經典不會被最新擠掉)
        ids_new = esearch(query, sort="date", retmax=45)                                  # 最新
        time.sleep(0.34 if API_KEY else 0.5)
        ids_mid = esearch(query + " AND 2012:2020[dp]", sort="relevance", retmax=35)      # 2010年代
        time.sleep(0.34 if API_KEY else 0.5)
        ids_old = esearch(query + " AND 1995:2012[dp]", sort="relevance", retmax=30)      # 更早經典
        time.sleep(0.34 if API_KEY else 0.5)
        pmids = list(dict.fromkeys(ids_new + ids_mid + ids_old))[:130]
        arts = efetch(pmids)
        time.sleep(0.4 if API_KEY else 0.6)
        epmc = europepmc(query, 50)                                                      # 全年代高被引
        time.sleep(0.3)
        merged = merge_dedup(arts, epmc, cap=RETMAX)
        result["items"][key] = merged
        flat.extend(merged)
        yrs = sorted({(a.get("date") or "")[:4] for a in merged if a.get("date")})
        sys.stderr.write(f"[{key}] PubMed {len(arts)} + EuropePMC {len(epmc)} -> {len(merged)} 篇,年份 {yrs[:1]}..{yrs[-1:]} \n")

    # 免費中文翻譯:標題一批、重點一批;各設時間預算避免卡住
    if flat:
        t_titles = translate_batch([a.get("title", "") for a in flat], time.time() + 300)
        for i, a in enumerate(flat):
            a["zh"] = t_titles.get(i, "")
        t_sums = translate_batch([a.get("summary", "") for a in flat], time.time() + 300)
        for i, a in enumerate(flat):
            a["zh_sum"] = t_sums.get(i, "")

    total = sum(len(v) for v in result["items"].values())
    if total == 0 and os.path.exists("data.json"):
        sys.stderr.write("No results — keeping existing data.json\n")
        return
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote data.json ({total} articles)\n")


if __name__ == "__main__":
    main()
