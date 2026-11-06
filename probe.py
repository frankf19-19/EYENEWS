#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""資料源探針:在 Actions 上查 data.gov.tw 資料集 metadata 與 CSV 前幾列(除錯用)"""
import sys, json, io, csv, requests, re, os
HEAD={"User-Agent":"Mozilla/5.0 EyeVisionHub-probe/1.0"}
ids=(os.environ.get("DATASETS") or "9576,151955,9123").split(",")
for ds in ids:
    ds=ds.strip(); print("=== dataset",ds,"===")
    try:
        j=requests.get("https://data.gov.tw/api/v2/rest/dataset/"+ds,headers=HEAD,timeout=40).json()
        r=j.get("result",{}); print("title:",r.get("title")); print("freq:",r.get("updateFrequency") or r.get("frequency")); print("desc:",(r.get("description") or "")[:200])
        print("fields:",(r.get("fieldDescription") or r.get("fieldsDescription") or "")[:600])
        for d in r.get("distribution",[]): print("  dist:",d.get("resourceFormat"),d.get("resourceDownloadUrl"))
        csvs=[d.get("resourceDownloadUrl") for d in r.get("distribution",[]) if (d.get("resourceFormat") or "").upper()=="CSV"]
        if csvs:
            rr=requests.get(csvs[0],headers=HEAD,timeout=180); raw=rr.content
            print("csv bytes:",len(raw),"ctype:",rr.headers.get("Content-Type"))
            if raw[:2]==b"PK":
                import zipfile
                z=zipfile.ZipFile(io.BytesIO(raw)); names=z.namelist(); print("zip members:",names)
                raw=z.read(names[0])
            txt=None
            for enc in ("utf-8-sig","utf-8","big5","cp950"):
                try: txt=raw.decode(enc); print("enc:",enc); break
                except Exception: pass
            if txt:
                rows=list(csv.DictReader(io.StringIO(txt)))
                print("rows:",len(rows)); print("headers:",list(rows[0].keys()) if rows else [])
                for row in rows[:2]: print("sample:",json.dumps(row,ensure_ascii=False)[:500])
                # 眼科相關筆數概估
                eye=[row for row in rows if re.search(r"眼|隱形眼鏡|角膜|水晶體|視",json.dumps(row,ensure_ascii=False))]
                print("眼科相關列數:",len(eye))
                for row in eye[:3]: print("eye-sample:",json.dumps(row,ensure_ascii=False)[:500])
    except Exception as e:
        print("ERR",e)
