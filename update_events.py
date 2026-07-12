#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取中華民國眼科醫學會(oph.org.tw)學術活動行事曆 → events.json
於 GitHub Actions 執行(容器內無法連該站)。視光全聯會為 JS 動態平台,無法簡單爬取,故僅附連結。
"""
import json, re, sys, datetime
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.stderr.write("need requests + beautifulsoup4\n"); raise

BASE = "https://www.oph.org.tw"
HEAD = {"User-Agent": "Mozilla/5.0 (EyeVisionHub-Calendar/1.0)"}
DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})")

SOURCES = [
    ("domestic", "/events/events.php?type=3"),   # 國內活動
    ("intl",     "/events/events.php?type=4"),   # 國際活動
    ("annual",   "/events/meeting.php?type=1"),  # 年會
    ("midyear",  "/events/meeting.php?type=2"),  # 年中會
    ("course",   "/events/course.php"),          # 驗光/護理課程
]

def to_iso(y, m, d):
    return "%s-%s-%s" % (y, m, d)

def normalize_link(href):
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return BASE + href
    return BASE + "/events/" + href

def scrape(cat, path):
    out = []
    try:
        r = requests.get(BASE + path, headers=HEAD, timeout=25)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        sys.stderr.write("[%s] fetch fail: %s\n" % (cat, e))
        return out
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ("content.php?id=" not in href) and ("meeting_info.php?id=" not in href):
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 4:
            continue
        cont = a.find_parent(["li", "div", "article", "td", "tr"]) or a.parent
        txt = cont.get_text("\n", strip=True) if cont else ""
        dates = DATE_RE.findall(txt)
        if not dates:
            continue
        date = to_iso(*dates[0])
        date_end = to_iso(*dates[1]) if len(dates) >= 2 else ""
        # 地點:日期之後、非積分/報名的那一行
        venue = ""
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        for i, l in enumerate(lines):
            if DATE_RE.search(l):
                for nxt in lines[i + 1:]:
                    if DATE_RE.search(nxt):
                        continue
                    if any(k in nxt for k in ("積分", "報名", "認定", "主辦", "人數")):
                        continue
                    if nxt == title:
                        continue
                    venue = nxt
                    break
                break
        out.append({
            "title": title, "date": date, "date_end": date_end,
            "venue": venue, "cat": cat, "org": "眼科醫學會",
            "link": normalize_link(href),
        })
    # 去重(依連結)
    seen, ded = set(), []
    for e in out:
        if e["link"] in seen:
            continue
        seen.add(e["link"]); ded.append(e)
    return ded

def main():
    all_events = []
    for cat, path in SOURCES:
        evs = scrape(cat, path)
        sys.stderr.write("[%s] %d events\n" % (cat, len(evs)))
        all_events += evs
    all_events = [e for e in all_events if e["date"]]
    # 只留近 90 天以後(含未來),控制檔案大小
    cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    all_events = [e for e in all_events if e["date"] >= cutoff]
    # 去重(跨來源,依 title+date)
    seen, ded = set(), []
    for e in sorted(all_events, key=lambda x: x["date"]):
        k = e["title"] + "|" + e["date"]
        if k in seen:
            continue
        seen.add(k); ded.append(e)
    # 保留/設定 first_seen(首次抓到日期),供前端標示新活動
    prev = {}
    try:
        with open("events.json", encoding="utf-8") as f:
            for e in json.load(f).get("events", []):
                if e.get("link"):
                    prev[e["link"]] = e.get("first_seen")
    except Exception:
        pass
    today = datetime.date.today().isoformat()
    for e in ded:
        e["first_seen"] = prev.get(e["link"]) or today

    data = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "links": [
            {"name": "中華民國眼科醫學會 官方行事曆", "url": "https://www.oph.org.tw/events/"},
            {"name": "中華民國驗光師公會全國聯合會 官網", "url": "https://www.optometrist.tw/"},
            {"name": "視光全聯會 Facebook", "url": "https://www.facebook.com/TaiwanOptometristsAssociation/"},
        ],
        "events": ded,
    }
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    sys.stderr.write("total %d events written\n" % len(ded))

if __name__ == "__main__":
    main()
