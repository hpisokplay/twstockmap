# 台股產業地圖

台股產業鏈地圖網站：題材總覽、上中下游供應鏈結構、個股盤後資料（行情／估值／法人買賣超／月營收），每個交易日收盤後自動更新，手機、電腦瀏覽器都能開，支援「加入主畫面」當 App 用。

資料全部來自臺灣證券交易所（TWSE）與證券櫃檯買賣中心（TPEx）的官方公開 API，免費、免金鑰、合法。

## 專案結構

```
index.html              網站本體（單一檔案，含全部樣式與程式）
manifest.webmanifest    PWA 設定（加入主畫面）
sw.js                   離線快取
icon-*.png / icon.svg   圖示
data/
  industries.json       產業鏈分類（題材、上中下游、公司歸類）← 你可以自己編輯
  market.json           個股行情資料（自動產生）
  companies.json        公司基本資料（自動產生）
scripts/
  fetch_data.py         盤後資料抓取腳本（GitHub Actions 每天自動跑）
  make_demo_data.py     產生示範資料（本機預覽用）
github/workflows/update.yml    每日自動更新排程
```

> **注意**：上傳到 GitHub 時，`github` 資料夾必須改名為 **`.github`**（前面加一個點），
> 也就是讓檔案位於 `.github/workflows/update.yml`，排程才會生效。
> 用網頁上傳的話，可以直接在 GitHub 點「Add file → Create new file」，
> 檔名輸入 `.github/workflows/update.yml`，再把 update.yml 的內容貼進去。

## 部署教學（一次設定，之後全自動）

### 1. 建立 GitHub 帳號與儲存庫
1. 到 https://github.com 註冊帳號（免費）。
2. 右上角「+」→「New repository」，名稱例如 `twstockmap`，選 **Public**，按 Create。

### 2. 上傳這個專案
最簡單的方式（網頁上傳）：
1. 在新儲存庫頁面點「uploading an existing file」。
2. 把這個資料夾裡的**所有檔案與資料夾**拖進去（包含 `.github` 資料夾——若拖曳漏掉它，改用下面的指令方式）。
3. 按 Commit changes。

或用指令（電腦有裝 git 的話）：
```bash
cd twstockmap
git init && git add -A && git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的帳號/twstockmap.git
git push -u origin main
```

### 3. 開啟 GitHub Pages（拿到網址）
1. 儲存庫頁面 → Settings → Pages。
2. 「Source」選 **Deploy from a branch**，Branch 選 `main`、資料夾選 `/ (root)`，按 Save。
3. 等 1–2 分鐘，網址就是 `https://你的帳號.github.io/twstockmap/`。

### 4. 啟用自動更新
1. 儲存庫 → Settings → Actions → General → Workflow permissions → 勾選 **Read and write permissions** → Save。
2. 儲存庫 → Actions 分頁 → 若有提示按「I understand… enable them」。
3. 左側點「每日盤後資料更新」→ 右側「Run workflow」手動跑第一次。
4. 跑完後 `data/` 會變成真實盤後資料，網站自動顯示最新數據。之後每個交易日 17:30 與 21:00（台北時間）自動更新，不用再管它。

### 5.（選用）加入主畫面
手機瀏覽器開啟網址 → 瀏覽器選單 →「加入主畫面」，即可像 App 一樣使用。

### 6.（選用）綁自己的網域
Settings → Pages → Custom domain 填你買的網域，再到網域商設 CNAME 指向 `你的帳號.github.io`。

## 維護產業鏈內容

打開 `data/industries.json`，照現有格式增改題材與公司：

```json
{
  "id": "唯一英文代號",
  "name": "題材名稱",
  "category": "半導體",
  "icon": "🏭",
  "desc": "題材說明…",
  "chain": {
    "上游": [ { "group": "族群名", "companies": [ {"code":"2330","name":"台積電","note":"備註"} ] } ],
    "中游": [ ... ],
    "下游": [ ... ]
  }
}
```

改完 commit，網站幾分鐘內自動生效。新加入的股票代碼只要是上市/上櫃普通股，行情會自動帶入。

## 免責聲明

本網站資料來自公開資訊，僅供個人研究參考，不構成任何投資建議。產業鏈分類由 AI 整理，可能存在錯誤，請自行查證。
