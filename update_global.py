#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全球近視控制新訊 — 每日更新腳本(全免費)
抓 Google News(英文/全球)RSS,依主題彙整國際新聞;
「重點」用 Google 翻譯免費介面把英文標題翻成繁體中文顯示(不需任何金鑰)。
(選填:若設定 ANTHROPIC_API_KEY,會改用 Claude 產生更精煉的繁中重點。)
由 GitHub Actions 每日執行。
"""
import json, time, sys, os, datetime, re, html
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BASE = "https://news.google.com/rss/search"
TAPI = "https://translate.googleapis.com/translate_a/single"
UA = "Mozilla/5.0 (myopia-hub global news bot)"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

QUERIES = {
    "myopia":      'myopia control OR myopia management when:6y',
    "contactlens": 'contact lens (industry OR launch OR myopia) when:6y',
    "lens":        'spectacle lens OR ophthalmic lens OR optometry when:6y',
    "device":      'ophthalmic device OR ophthalmology equipment when:6y',
    "pharma":      'ophthalmology drug OR dry eye OR cataract treatment when:6y',
    "health":      'eye health OR vision care awareness when:6y',
    "industry":    'eyecare industry OR vision care market OR optical retail when:6y',
    "business":    '(eyecare OR ophthalmic OR "contact lens" OR "vision care") (earnings OR revenue OR sales OR profit OR guidance OR stock OR quarterly) when:6y',
    "deal":        '(eyecare OR ophthalmic OR "vision care" OR optical) (acquisition OR merger OR acquires OR investment OR IPO OR partnership OR "private equity") when:6y',
    "eyewear":     'site:ewintelligence.com OR "eyewear industry" OR "eyewear market" OR "optical retail" OR "spectacle market" when:6y',
}
RETMAX = 30  # 每分類則數(近6年;全球逐則翻譯,取適中值)


def _get(url, timeout=40, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write(f"  retry {i+1}: {e}\n")
            time.sleep(1 + i)
    return None


def fetch(query):
    q = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return _get(f"{BASE}?{q}")


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def translate_zh(text):
    """免費 Google 翻譯介面:英文 -> 繁體中文(zh-TW)。失敗回傳空字串。"""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        q = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "zh-TW",
                                    "dt": "t", "q": text})
        raw = _get(f"{TAPI}?{q}", timeout=20, retries=3)
        if not raw:
            return ""
        data = json.loads(raw)
        return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
    except Exception as e:
        sys.stderr.write(f"  translate skip: {e}\n")
        return ""


def translate_batch(texts, budget_until, chunk=20):
    """批次翻譯:一次送多則(以換行分隔),大幅減少請求數;超過時間預算即停。"""
    out = {}
    for start in range(0, len(texts), chunk):
        if time.time() > budget_until:
            sys.stderr.write("translate budget reached — stop translating\n")
            break
        part = [(texts[start + k] or "").replace("\n", " ").strip() for k in range(min(chunk, len(texts) - start))]
        zh = translate_zh("\n".join(part))
        lines = [x for x in zh.split("\n")] if zh else []
        if len(lines) == len(part):
            for k, ln in enumerate(lines):
                if ln.strip():
                    out[start + k] = ln.strip()
        time.sleep(0.6)
    return out


CLUSTER_RE = re.compile(r'(相關報導|相關新聞|最新消息|懶人包|Google News)\s*$', re.I)

def parse(raw, limit):
    out = []
    if not raw:
        return out
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("{*}source") or it.find("source")
        source = (src_el.text.strip() if src_el is not None and src_el.text else "")
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)].strip()
        # 丟棄 Google News 主題叢集/彙整(日期非文章真實日期)
        if CLUSTER_RE.search(title):
            continue
        date = ""
        pd = it.findtext("pubDate")
        if pd:
            try:
                date = parsedate_to_datetime(pd).astimezone().strftime("%Y-%m-%d")
            except Exception:
                date = ""
        # 無真實日期一律丟棄(避免舊聞被當成新聞)
        if not date:
            continue
        summary = strip_html(it.findtext("description"))
        if len(summary) > 180:
            summary = summary[:180] + "…"
        if title and link:
            out.append({"title": title, "link": link, "source": source,
                        "date": date, "summary": summary})
        if len(out) >= limit:
            break
    out.sort(key=lambda x: x.get("date", ""), reverse=True)  # 新到舊
    return out


def claude_keypoints(all_items):
    if not API_KEY or not all_items:
        return {}
    listing = [{"i": i, "title": it["title"], "source": it.get("source", "")}
               for i, it in enumerate(all_items)]
    system = ("你是近視控制產業分析助理。針對每則英文新聞標題,用繁體中文寫一句話重點"
              "(20~40字,精準不誇大)。只回傳 JSON 陣列 [{\"i\":0,\"zh\":\"...\"}]。")
    payload = {"model": MODEL, "max_tokens": 2000, "system": system,
               "messages": [{"role": "user", "content": json.dumps(listing, ensure_ascii=False)}]}
    try:
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "x-api-key": API_KEY,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        text = re.sub(r"^json", "", text.strip().strip("`")).strip()
        return {int(o["i"]): str(o["zh"]).strip() for o in json.loads(text) if "i" in o and "zh" in o}
    except Exception as e:
        sys.stderr.write(f"claude skip: {e}\n")
        return {}


def main():
    mode = "Claude" if API_KEY else "Google 翻譯(免費)"
    result = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": f"Google News (Global/EN) · 重點:{mode}",
        "items": {},
    }
    flat = []
    for key, q in QUERIES.items():
        sys.stderr.write(f"[{key}] fetching…\n")
        arts = parse(fetch(q), RETMAX)
        result["items"][key] = arts
        flat.extend(arts)
        sys.stderr.write(f"[{key}] {len(arts)} items\n")
        time.sleep(1.0)

    # 重點:預設用免費 Google 翻譯把標題翻成繁中
    if not API_KEY and flat:
        budget = time.time() + 300  # 翻譯階段最多 5 分鐘(放慢避免被限流,提高中文覆蓋)
        zhmap = translate_batch([a["title"] for a in flat], budget)
        for i, a in enumerate(flat):
            if zhmap.get(i):
                a["keypoint"] = zhmap[i]
    else:
        pts = claude_keypoints(flat)
        for i, a in enumerate(flat):
            if pts.get(i):
                a["keypoint"] = pts[i]

    total = len(flat)
    if total == 0 and os.path.exists("global_news.json"):
        sys.stderr.write("No results — keeping existing global_news.json\n")
        return
    with open("global_news.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Wrote global_news.json ({total} items, mode={mode})\n")


if __name__ == "__main__":
    main()
