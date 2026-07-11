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

RELDATE_DAYS = 1095   # 近 3 年
RETMAX = 8            # 每類最多 8 篇(取最新)


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


def esearch(query):
    url = f"{EUTILS}/esearch.fcgi?" + _params({
        "db": "pubmed", "term": query, "retmax": RETMAX,
        "sort": "date", "datetype": "pdat", "reldate": RELDATE_DAYS,
    })
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
        concl, last = "", ""
        for ab in art.findall(".//Abstract/AbstractText"):
            txt = "".join(ab.itertext()).strip()
            if not txt:
                continue
            last = txt
            label = (ab.get("Label") or "").upper()
            if "CONCLUSION" in label or "RESULT" in label:
                concl = txt
        summary = concl or last
        if len(summary) > 240:
            cut = summary[:240]
            dot = cut.rfind(". ")
            summary = (cut[:dot + 1] if dot > 120 else cut) + " …"
        if title:
            out.append({"title": title, "journal": journal, "date": year,
                        "pmid": pmid, "summary": summary})
    return out


# ---- 免費翻譯(translate.googleapis.com,無需金鑰) ----
def translate(text, retries=2):
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
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
        except Exception as e:
            sys.stderr.write(f"  translate retry {i+1}: {e}\n")
            time.sleep(1.5)
    return ""


def main():
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "PubMed / NCBI E-utilities;中文為免費自動翻譯",
        "items": {},
    }
    for key, query in QUERIES.items():
        sys.stderr.write(f"[{key}] searching…\n")
        pmids = esearch(query)
        time.sleep(0.4 if API_KEY else 0.6)
        arts = efetch(pmids)
        time.sleep(0.4 if API_KEY else 0.6)
        # 免費中文翻譯:標題 + 重點(合併一次呼叫,以節省請求)
        for a in arts:
            sep = " ||| "
            combo = translate((a["title"] or "") + sep + (a["summary"] or ""))
            if combo and sep.strip() in combo:
                zt, _, zs = combo.partition(sep.strip())
                a["zh"] = zt.strip(" |")
                a["zh_sum"] = zs.strip(" |")
            else:
                a["zh"] = combo
                a["zh_sum"] = ""
            time.sleep(0.4)
        result["items"][key] = arts
        sys.stderr.write(f"[{key}] {len(arts)} articles\n")

    total = sum(len(v) for v in result["items"].values())
    if total == 0 and os.path.exists("data.json"):
        sys.stderr.write("No results — keeping existing data.json\n")
        return
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote data.json ({total} articles)\n")


if __name__ == "__main__":
    main()
