# 眼視光資訊中心 OPTO-HUB

近視控制六大工具的臨床決策單頁,臨床文獻由 GitHub Actions 每日自動抓取 PubMed 更新。

## 檔案結構
```
index.html               主頁(靜態,GitHub Pages 直接托管)
data.json                文獻資料(由 Actions 自動改寫)
update_data.py           每日抓 PubMed 的腳本
.github/workflows/update.yml   排程工作流
```

## 部署(GitHub Pages)
1. 建一個新 repo,把這四個檔案(含 `.github/workflows/update.yml`)上傳。
2. Settings → Pages → Source 選 `main` 分支、`/ (root)`,存檔。
3. 幾分鐘後即可用 `https://<帳號>.github.io/<repo>/` 開啟。

## 每日自動更新
- 工作流排程為每日 21:00 UTC(台灣約隔日 05:00),也可到 **Actions → Update PubMed literature → Run workflow** 手動觸發。
- 腳本查詢 NCBI E-utilities(免金鑰),依六大工具分類抓取近 3 年最新文獻,寫回 `data.json` 並自動 commit。
- 前端每次載入會讀取 `data.json`,標題與重點直接顯示。

## 可選:提高 PubMed 速率上限
到 repo → Settings → Secrets and variables → Actions 新增:
- `NCBI_EMAIL`:你的 email(NCBI 禮貌性識別)
- `NCBI_API_KEY`:NCBI 帳號申請的 API key(可將速率從 3/秒提升到 10/秒)

未設定也能正常運作。

## 台灣市場新訊(每 6 小時更新)
- `update_news.py` 抓 Google News(台灣/繁中)RSS,依主題彙整近視控制新聞/活動,寫入 `news.json`。
- 工作流 `.github/workflows/update_news.yml` 每 6 小時執行一次,也可手動觸發。
- 前端「市場新訊」分頁讀 `news.json`,可依分類篩選、依日期排序。
- 要改搜尋主題:編輯 `update_news.py` 的 `QUERIES`。

## 全球新訊(每日更新 · 重點免費繁中翻譯)
- `update_global.py` 抓 Google News(全球/英文)RSS,依主題彙整國際新聞,寫入 `global_news.json`。
- **重點**:預設用 **Google 翻譯免費介面**把英文標題翻成繁體中文顯示,**不需任何金鑰、零成本**。
- (選填:若設定 `ANTHROPIC_API_KEY`,改用 Claude 產生更精煉的繁中重點。)
- 工作流 `.github/workflows/update_global.yml` 每日執行(也可手動觸發)。

## 調整文獻查詢
編輯 `update_data.py` 中的 `QUERIES` 字典即可增修各工具的 PubMed 搜尋條件;
`RELDATE_DAYS`(回溯天數)與 `RETMAX`(每工具篇數)可調整抓取範圍。

## 更新工作流
之後若要改版,沿用你的「更新」流程:提供完整替換檔即可,build 版號會標在頁尾。

---
資料僅供臨床與衛教參考,不構成醫療建議。對外行銷用途請先經法規/法務審閱(醫療器材/醫療廣告相關規範)。
build r16


## 眼視光升級(r13)
- 主題由「近視控制」擴大為「眼視光」;近視控制為其中一環。
- 新聞分為『台灣訊息』與『全球訊息』,涵蓋近視控制/隱形眼鏡/鏡片驗光/眼科醫材/眼藥/視力保健/產業公司,可分類篩選。
- 新增『產業公司』分類目錄(可編輯 index.html 的 COMPANIES 陣列)。
- 兩個新聞腳本的 QUERIES 已擴充為眼視光分類。
