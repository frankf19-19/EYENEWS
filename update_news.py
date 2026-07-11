#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灣近視控制市場新訊 — 每日更新腳本
抓 Google News(台灣/繁中)RSS,依主題彙整近期新聞/活動/市場動態,寫入 news.json。
免金鑰、免費。由 GitHub Actions 定期執行。
"""
import json, time, sys, datetime, re, html
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BASE = "https://news.google.com/rss/search"
UA = "Mozilla/5.0 (myopia-hub news bot)"

# 每個分類的搜尋關鍵字(Google News 查詢語法;when:1y = 近一年)
QUERIES = {
    "myopia":      '近視控制 OR 近視防控 OR 角膜塑型 when:1y',
    "contactlens": '隱形眼鏡 when:1y',
    "lens":        '(鏡片 OR 驗光 OR 眼鏡) 光學 when:1y',
    "device":      '眼科 (醫材 OR 器材 OR 儀器) when:1y',
    "pharma":      '(眼藥 OR 乾眼 OR 白內障 OR 青光眼) when:1y',
    "health":      '視力保健 OR 護眼 OR 眼睛健康 when:1y',
    "industry":    '(眼科 OR 光學 OR 隱形眼鏡) (產業 OR 營收 OR 上市 OR 公司) when:1y',
    "events":      '(眼科 OR 視光 OR 近視 OR 隱形眼鏡 OR 角膜塑型) (講座 OR 衛教 OR 活動 OR 體驗會 OR 發表會 OR 記者會 OR 義診) when:1y',
}
RETMAX = 40  # 每分類最多幾則(取最新;一年份用較大值)


def fetch(query):
    q = urllib.parse.urlencode({
        "q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"
    })
    url = f"{BASE}?{q}"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write(f"  retry {i+1}: {e}\n")
            time.sleep(2 + 2 * i)
    return None


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse(raw, limit):
    out = []
    seen = set()
    if not raw:
        return out
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        # source
        src_el = it.find("{*}source") or it.find("source")
        source = (src_el.text.strip() if src_el is not None and src_el.text else "")
        # Google News 標題常是 "標題 - 來源",去掉尾巴來源
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)].strip()
        key = re.sub(r"\s+", "", title)
        if not title or not link or key in seen:
            continue
        seen.add(key)
        # date
        date = ""
        pd = it.findtext("pubDate")
        if pd:
            try:
                date = parsedate_to_datetime(pd).astimezone().strftime("%Y-%m-%d")
            except Exception:
                date = ""
        summary = strip_html(it.findtext("description"))
        if len(summary) > 160:
            summary = summary[:160] + "…"
        out.append({
            "title": title, "link": link, "source": source,
            "date": date, "summary": summary,
        })
        if len(out) >= limit:
            break
    return out


def main():
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "Google News (台灣/繁中)",
        "items": {},
    }
    for key, q in QUERIES.items():
        sys.stderr.write(f"[{key}] fetching…\n")
        arts = parse(fetch(q), RETMAX)
        result["items"][key] = arts
        sys.stderr.write(f"[{key}] {len(arts)} items\n")
        time.sleep(1.0)

    total = sum(len(v) for v in result["items"].values())
    if total == 0 and __import__("os").path.exists("news.json"):
        sys.stderr.write("No results — keeping existing news.json\n")
        return
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote news.json ({total} items)\n")


if __name__ == "__main__":
    main()
