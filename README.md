# 🔬 鈣鈦礦 SAM 論文數據與 DOI 擷取工具 (Perovskite SAM Extractor)

本專案為鈣鈦礦太陽能電池（Perovskite Solar Cells, PSCs）論文數據擷取的專用系統。採用**前後端徹底分離架構**，結合 Gemini/OpenAI 大語言模型、**Agent 自校驗工具箱 (RDKit / PubChem / Fable 規則引擎)**、以及 **SQLite + CSV 雙軌持久化資料庫與歷史數據檢索系統**。

---

## 🌟 核心特色 (Core Features)

1. **🛡️ 前後端徹底分離與 API Key 安全代理**：
   - 前端靜態網頁（不含任何 Python 程式或 API Key），可免費安全部署於 Vercel / GitHub Pages。
   - 後端 REST API 統一處理金鑰與模型請求，**同學或外部使用者完全不需要輸入 API Key**，金鑰 100% 隱藏在後端 `.env` 中。
2. **🧰 Agentic Tool-Calling 自自我校驗與數據修復**：
   - **RDKit SMILES 校驗**：自動檢驗化學結構合法性並轉為標準 Canonical SMILES。
   - **PubChem & 字典反查**：若文獻遺漏 SMILES，自動依 SAM 縮寫名稱（如 `MeO-2PACz`）跨庫補全。
   - **Fable 5 配比歸一化引擎**：自動將 A-site 鈣鈦礦前驅物配比（如 $\text{Cs}_{0.05}\text{FA}_{0.85}\text{MA}_{0.15}$ 總和 $1.05$）歸一化至 $1.00$。
   - **Wash & 能階推論**：依據 Methods 描述推論 `wash=1`（標紅推論鏈）並自動標註白/紅/黑可信度色標。
3. **💾 雙軌資料庫持久化 (SQLite + CSV)**：
   - 每完成一次論文擷取，自動分配唯一任務編號（如 `JOB_20260804_084022_0C63`）與時間戳記。
   - 同步寫入 **SQLite 資料庫 (`data/sam_database.db`)** 與 **CSV 備份檔 (`data/sam_database.csv`)**。
4. **🔍 前端多維度數據查詢與 Excel 導出**：
   - **日期選單 (Date Picker)**：選擇 `2026-08-04` 一鍵列出當天所有處理過的論文任務。
   - **任務卡片瀏覽**：點擊卡片即時載入該次 35 欄位 SAM 明細表格。
   - **跨庫關鍵字搜尋**：輸入 SAM 名稱、SMILES 或 DOI 關鍵字即時搜尋全量歷史資料庫。
   - **Excel / CSV 一鍵導出**：隨時串流下載含有儲存格色標的 `.xlsx` 表格。

---

## 📂 專案目錄結構 (Project Structure)

```text
擷取工具/
├── backend/                       # 後端純 Python FastAPI 服務 (REST API)
│   ├── app.py                     # API 路由主程式 (含 CORS 與安全 Key 代理)
│   ├── database.py                # SQLite + CSV 雙軌持久化與查詢引擎
│   ├── sam_extractor.py           # AI 文章數據擷取與 Agent 工具鏈
│   ├── doi_extractor.py           # Crossref 與 1..N DOI 檢索模組
│   ├── excel_exporter.py          # Excel (.xlsx) 帶色標生成器
│   ├── extraction_tools.py        # RDKit / PubChem / Fable 規則引擎
│   └── test_decoupled_db_suite.py # 後端自動化單元測試套件
├── frontend/                      # 獨立前端靜態網頁 (無 Python / 無 Key)
│   ├── index.html                 # 主介面 (即時擷取 Tab + 歷史查詢 Tab)
│   ├── app.js                     # 前端 REST API 請求與 UI 動態渲染
│   └── style.css                  # 精美現代 Dark Mode 樣式表
├── data/                          # 雙軌持久化資料庫自動存放區
│   ├── sam_database.db            # SQLite 資料庫 (索引任務與 35 欄位明細)
│   └── sam_database.csv           # 全量 CSV 備份檔
├── .env.example                    # 後端 API Key 環境變數範本
├── vercel.json                    # Vercel 部署設定檔
└── requirements.txt               # 後端 Python 依賴套件
```

---

## 🚀 方案 1 教學：Vercel 前端 + 本地/雲端 SQLite 後端部署指南

> **方案 1 理念**：將無 API Key 的純靜態 `frontend/` 託管在 **Vercel** 上，產生一個好記的網址給同學；後端 `backend/` 跑在**你的實體電腦**或免費雲端（如 Render.com）。
> **好處**：SQLite 資料庫與 CSV 會永久保存在你的實體電腦上，絕不丟失；同學用 Vercel 網址就能直接操作你的後端並查詢歷史資料庫！

### 步驟 1：配置後端 API Key (`.env`)

在專案根目錄下建立 `.env` 檔案（可複製 `.env.example`）：

```bash
cp .env.example .env
```

編輯 `.env` 並填入你的 Gemini API Key：
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 步驟 2：啟動後端 FastAPI 服務

在電腦終端機中執行：

```powershell
# 啟用 Python 虛擬環境並啟動後端
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
> 當終端機顯示 `Uvicorn running on http://0.0.0.0:8000` 即代表後端啟動成功！

---

### 步驟 3：將前端部署至 Vercel

1. **上傳程式碼至 GitHub**：
   將專案 Push 到你的 GitHub 倉庫。
2. **前往 Vercel 開啟新專案**：
   - 登入 [Vercel.com](https://vercel.com) 點擊 **"Add New" $\rightarrow$ "Project"**。
   - 選擇並匯入你的 GitHub 倉庫。
3. **設定 Root Directory**：
   - 在 Vercel 設定頁面中，將 **Root Directory** 設定為 `frontend`。
   - Framework Preset 選擇 `Other`（純靜態網頁）。
4. **點擊 Deploy！**
   - 部署完成後，Vercel 會產生一個專屬網址（例 `https://your-sam-tool.vercel.app`）。

---

### 步驟 4：將前端與後端連線

若同學在外部網路要連接你的電腦後端：
- 在 [frontend/app.js](file:///c:/Users/yexia/Documents/黃士緯/大學/趙宇強/GitHub/擷取工具/frontend/app.js) 第一行修改：
  ```javascript
  const API_BASE = "https://your-backend-domain.com"; // 例如你的 ngrok 網址或固定 IP
  ```
- 如果只是在本機測試，直接開啟瀏覽器造訪 `http://127.0.0.1:8000` 即可！

---

## 📡 REST API 介面說明

| HTTP 方法 | API 路徑 | 功能說明 |
| :--- | :--- | :--- |
| `GET` | `/api/health` | 檢查伺服器狀態與後端 API Key 配置狀態 |
| `POST` | `/api/extract-text-sam` | 上傳 Markdown/PDF 進行數據擷取，並自動寫入 SQLite & CSV |
| `GET` | `/api/jobs` | 取得歷史任務清單（支援 `?date=2026-08-04` 日期篩選） |
| `GET` | `/api/jobs/{job_id}` | 取得指定任務編號的 35 欄位 SAM 表格明細 |
| `GET` | `/api/search?q={keyword}` | 跨任務搜尋 SAM 名稱、SMILES、DOI 或檔名 |
| `GET` | `/api/export-job-excel/{job_id}` | 串流導出指定任務的標準 Excel (.xlsx) 表格 |

---

## 🧪 自動化測試

執行全套後端與 SQLite 資料庫單元測試：

```powershell
.venv\Scripts\python.exe -m unittest backend/test_decoupled_db_suite.py
```
