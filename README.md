# 🔬 鈣鈦礦 SAM 論文數據與 DOI 擷取工具 (Perovskite SAM Extractor)

本工具為鈣鈦礦太陽能電池（Perovskite Solar Cells）論文數據擷取專用網頁工具。上傳 PDF 論文後，自動調用 `markitdown` 轉換為 Markdown，精準擷取 35 欄位 SAM p-i-n 結構特徵數據（支援可信度儲存格著色與 Excel 導出），並一併提取論文中提及的所有參考文獻 DOI 列表。

## 🌟 主要功能
1. **PDF 轉 Markdown**：調用微軟 MarkItDown 轉換 PDF 為純文字。
2. **SAM p-i-n 數據點擷取**：符合 `sam-dataset-builder` 35 欄位規範，自動賦予白/紅/黑可信度色標與 Notes 註記。
3. **Reference DOI 提取**：精準掃描 10.xxxx/xxx 格式 DOI，附帶行數與上下文。
4. **互動式 Web UI**：支援即時預覽、TSV 一鍵複製（直貼 Excel）、匯出標準 Excel (.xlsx) 與全選 DOI 複製。

## 🚀 本地開發與運行

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 啟動 FastAPI 服務
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

開啟瀏覽器前往：`http://127.0.0.1:8000`

## ☁️ 雲端部署 (Deploy to Cloud)

本專案已包含 `Dockerfile`，可免費一鍵部署至：
- **Render.com** (Web Service -> Docker)
- **Hugging Face Spaces** (Docker SDK)
- **Railway** / **Fly.io**
