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

# 每個分類的搜尋關鍵字(Google News;when:6y = 近六年,惟 Google News RSS 多僅回溯約1年)
QUERIES = {
    "myopia":      '近視控制 OR 近視防控 OR 角膜塑型 when:6y',
    "contactlens": '隱形眼鏡 when:6y',
    "lens":        '(鏡片 OR 驗光 OR 眼鏡) 光學 when:6y',
    "device":      '眼科 (醫材 OR 器材 OR 儀器) when:6y',
    "pharma":      '(眼藥 OR 乾眼 OR 白內障 OR 青光眼) when:6y',
    "health":      '視力保健 OR 護眼 OR 眼睛健康 when:6y',
    "industry":    '(眼科 OR 光學 OR 隱形眼鏡) (產業 OR 營收 OR 上市 OR 公司) when:6y',
    "events":      '(眼科 OR 視光 OR 驗光 OR 近視 OR 隱形眼鏡 OR 角膜塑型) (講座 OR 研討會 OR 年會 OR 學會 OR 繼續教育 OR 工作坊 OR 論壇 OR 衛教 OR 體驗會 OR 發表會 OR 記者會 OR 義診 OR 展) when:6y',
    "business":    '(晶碩 OR 視陽 OR 精華光學 OR 大學光 OR 亨泰 OR 明基材 OR 隱形眼鏡 OR 眼科) (營收 OR 財報 OR 法說 OR 股價 OR 獲利 OR 財測 OR 上市 OR 掛牌) when:6y',
    "deal":        '(眼科 OR 光學 OR 隱形眼鏡 OR 視光 OR 眼鏡 OR 晶碩 OR 視陽 OR 亨泰 OR 蔡司) (併購 OR 收購 OR 入股 OR 投資 OR 募資 OR IPO OR 擴廠 OR 建廠 OR 策略聯盟 OR 代理權) when:6y',
}
RETMAX = 80  # 每分類最多幾則(近6年取最新)
MAXAGE_DAYS = 2200  # 近6年上限:丟棄早於此天數者(無日期仍保留)


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


def _cutoff():
    d = datetime.datetime.now() - datetime.timedelta(days=MAXAGE_DAYS)
    return d.strftime('%Y-%m-%d')


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
        # 近6年上限:有日期且早於 6 年則丟棄;無日期仍保留
        if date and date < _cutoff():
            continue
        summary = strip_html(it.findtext("description"))
        if len(summary) > 180:
            summary = summary[:180] + "…"
        out.append({
            "title": title, "link": link, "source": source,
            "date": date, "summary": summary,
        })
        if len(out) >= limit:
            break
    # 依日期新到舊排序
    out.sort(key=lambda x: x.get("date",""), reverse=True)
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
