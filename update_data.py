#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
近視控制臨床中心 — 每日文獻更新腳本
Fetches recent PubMed literature for each myopia-control tool and writes data.json.

資料來源: NCBI E-utilities (esearch + efetch). 免金鑰、免費。
由 GitHub Actions 每日排程執行。若要提高速率上限,可在 repo Secrets 設定 NCBI_API_KEY。
"""

import json
import time
import os
import sys
import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "myopia-control-hub"                 # NCBI 'tool' identifier
EMAIL = os.environ.get("NCBI_EMAIL", "example@example.com")
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()

# 每個工具的 PubMed 查詢字串 + 前端 key
QUERIES = {
    "ortho":     '(orthokeratology OR "ortho-k") AND (myopia) AND (control OR progression OR "axial length")',
    "atropine":  '(atropine) AND (myopia) AND (progression OR control OR "axial length") AND (low-dose OR "0.01%" OR "0.05%" OR concentration)',
    "spectacle": '((defocus spectacle) OR DIMS OR "highly aspherical lenslet" OR "myopia spectacle lens") AND (myopia) AND (control OR progression)',
    "softcl":    '(("dual focus" OR "dual-focus" OR MiSight OR "defocus soft contact") AND myopia) AND (control OR progression)',
    "redlight":  '("repeated low-level red light" OR "red light therapy" OR "low-level red-light") AND myopia',
    "outdoor":   '(outdoor OR "light exposure" OR "time outdoors") AND myopia AND (children OR onset OR prevention)',
}

# 每個工具抓最近幾年、最多幾篇
RELDATE_DAYS = 1095     # 近 3 年
RETMAX = 6              # 每個工具最多 6 篇(取最新)


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
    """回傳最新的 PMID 清單。"""
    url = f"{EUTILS}/esearch.fcgi?" + _params({
        "db": "pubmed",
        "term": query,
        "retmax": RETMAX,
        "sort": "date",           # 依日期,最新在前
        "datetype": "pdat",
        "reldate": RELDATE_DAYS,
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
    """抓取每篇文章的標題、期刊、年份、結論摘要。"""
    if not pmids:
        return []
    url = f"{EUTILS}/efetch.fcgi?" + _params({
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
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

        # 年份
        year = _text(art, ".//JournalIssue/PubDate/Year")
        if not year:
            md = _text(art, ".//JournalIssue/PubDate/MedlineDate")
            year = md[:4] if md else ""

        # 摘要:優先抓標為 CONCLUSION 的段落,否則取最後一段
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
        # 控制長度(僅顯示重點,避免整段複製)
        if len(summary) > 240:
            cut = summary[:240]
            dot = cut.rfind(". ")
            summary = (cut[:dot + 1] if dot > 120 else cut) + " …"

        if title:
            out.append({
                "title": title,
                "journal": journal,
                "date": year,
                "pmid": pmid,
                "summary": summary,
            })
    return out


def main():
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "PubMed / NCBI E-utilities",
        "items": {},
    }

    for key, query in QUERIES.items():
        sys.stderr.write(f"[{key}] searching…\n")
        pmids = esearch(query)
        time.sleep(0.4 if API_KEY else 0.5)
        arts = efetch(pmids)
        time.sleep(0.4 if API_KEY else 0.5)
        result["items"][key] = arts
        sys.stderr.write(f"[{key}] {len(arts)} articles\n")

    # 若全部為空(暫時性 API 問題),保留舊檔避免頁面空白
    total = sum(len(v) for v in result["items"].values())
    if total == 0 and os.path.exists("data.json"):
        sys.stderr.write("No results fetched — keeping existing data.json\n")
        return

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote data.json ({total} articles total)\n")


if __name__ == "__main__":
    main()
