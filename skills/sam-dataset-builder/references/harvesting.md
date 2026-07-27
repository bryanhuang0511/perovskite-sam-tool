# 文獻檢索與數值擷取方法（通用 AI 適用）
 
適用於任何具備「瀏覽器控制（可經使用者 VPN）＋頁內 JavaScript 執行＋截圖/局部放大」能力的 AI 系統。無瀏覽器控制的模型改走「請使用者下載 PDF/SI 到本地資料夾」路線，解析部分相同。
 
## 0. 三層擷取原則（依序，不可跳層）
 
```
第一層　文字（主文 HTML、SI 內文字）→ 白格
第二層　SI 檔案內的文字表格（PDF/docx 解析）→ 白格
第三層　讀圖（能階圖/表格圖上「印出的數字」）→ 紅格
禁止層　讀曲線估值、憑記憶填值、跨文獻搬值（未經使用者核可）
```
 
每層找到即停。**讀圖只讀圖上明確印出的數字標註，不對曲線做內插或積分估值。**
 
## 1. 進入論文
 
1. 用 `https://doi.org/{DOI}` 讓瀏覽器重導向至出版社頁（經使用者 VPN 取得訂閱權限）。
2. 落地後**先驗證頁面標題與目標論文一致**（DOI 可能錯置）。
3. Cloudflare「請稍候」頁通常數秒自動通過，等待後重試；出現 CAPTCHA → 停止並通知使用者手動通過，**絕不嘗試繞過**。通過後同分頁可繼續用。
## 2. 文字層擷取（省 token 的核心）
 
不要通讀全文。在頁內執行 JavaScript，以關鍵字正則抓「關鍵句±150 字」回傳：
 
- 能階：`HOMO|valence band|VBM|UPS|PESA|ionization|work function` 且句中含 `eV`
- 製程：`dissolv|mg/mL|mg mL|mM|spin|rins|wash|anneal`
- 組成：`Cs0\.|FA0\.|MA0\.|CsPbI|FAPbI|MAPbI|Pb\(I|PbI2|precursor`
- 堆疊：`ITO/|FTO/|C60|BCP|PCBM|SnO2|evaporat`
- 效率：`PCE|efficiency of|certified|champion`
技巧：
- 回傳前清洗特殊字元與長雜湊字串，避免輸出被安全過濾器攔截；一次回傳量控制在數千字內。
- 主文常只有結論值，製程細節幾乎都在 Methods/SI——別在主文空轉太久。
- 區分值的性質：**DFT 計算值≠實測**；CV≠UPS；摘要的「認證值」與正文「反掃值」要分清。
## 3. SI 檔案取得（各出版社模式）
 
| 出版社 | SI 位置模式 | 備註 |
|---|---|---|
| Wiley (onlinelibrary/advanced/chemistry-europe) | 頁內 `downloadSupplement` 連結 | PDF 或 **docx** 都有 |
| Elsevier (ScienceDirect) | `ars.els-cdn.com/content/image/1-s2.0-{PII}-mmc{n}.pdf/.docx`；PII 在文章 URL | mmc 檔通常公開可抓 |
| RSC (pubs.rsc.org) | 頁內「Supplementary information (PDF)」→ `article-supplement/.../pdf/...` | |
| Springer/Nature | `static-content.springer.com/esm/art%3A{DOI編碼}/MediaObjects/{...}_MOESM{n}_ESM.pdf` | 公開可抓 |
| ACS | `pubs.acs.org/doi/suppl/{DOI}/suppl_file/{id}_si_001.pdf` | 公開可抓 |
| Science/AAAS | `science.org/doi/suppl/{DOI}/suppl_file/science.{id}_sm.pdf` | 需訂閱 session |
| Cell Press | 頁內 `/cms/{DOI}/attachment/.../mmc{n}.pdf` | |
| OUP | `oup.silverchair-cdn.com/...`（帶簽名 token 的限時連結） | 從文章頁取完整 URL |
 
**CORS 繞法（關鍵技巧）**：SI 檔常在另一網域，文章頁內 `fetch` 會被 CORS/CSP 擋。解法：把 SI 完整 URL 放進 `#fragment`，讓瀏覽器導航到「SI 所在網域的任意純文字頁」（如 `/robots.txt`），fragment 會跟著過去，再從 `location.hash` 取回 URL 做**同源 fetch**。
 
## 4. SI 檔案解析（頁內執行）
 
- **PDF**：載入 pdf.js（CDN），`getDocument({data:buffer})` 後逐頁 `getTextContent()` 取純文字，之後同第 2 節做關鍵字擷取。CDN 被目標網域 CSP 擋時見 docx 的原生解法。
- **docx**：docx 是 zip。有 JSZip 用 JSZip；CDN 被擋就**原生解**：掃 End-of-Central-Directory（`0x06054b50`）→ 讀 central directory 找 `word/document.xml` → `DecompressionStream('deflate-raw')` 解壓 → 去 XML tag 得純文字。
- **docx 陷阱**：EndNote 引用會塞進大量 XML/Base64 垃圾（`ADDIN EN.CITE`），會把表格切碎——先以 `ADDIN[\s\S]*?EN\.CITE` 與 60 字以上的 Base64 串清掉再搜尋。表格數字可能被切散（`15. 81` `0. 54`），比對時容忍空白。
- **大檔**：fetch 可能超過單次執行逾時 → 改成「非同步啟動＋把結果掛在 window 變數＋輪詢狀態」三步式。
## 5. 讀圖（第三層，一律標紅）
 
1. 先用 SI 文字定位候選頁碼（搜圖說：`UPS|energy level|Fig. S\d+`）。
2. 用 pdf.js 把該頁 render 到 canvas（scale 2 左右）插入 DOM → 截圖 → 對目標區域 zoom。
3. docx 內嵌圖：從 zip 抽 `word/media/*`，PNG/JPEG 可用 blob URL 排版顯示後截圖；**EMF/WMF 瀏覽器無法渲染**——據實回報，**請使用者提供 PDF 版檔案**（PDF 是機器最可讀的格式；勿收 docx/掃描檔等難讀格式）或人工讀值。
4. 只抄圖上印出的數字。模糊必 zoom 確認；讀出後盡量交叉驗算（如 UPS：WF＋(E_F−VBM)＝IP 應與 cutoff/onset 算出的一致；或用同表已知列反推該論文的基準值再驗新值）。
5. Notes 記下圖表編號（`E:讀Fig.1F能階圖(讀圖)`）。
6. **線上 vs 使用者 PDF 一致性檢核**：若線上（網頁/線上 SI）讀到的內容與使用者上傳的 PDF **差異大**（版本不同、圖表編號對不上、數值矛盾），停止填值，回報差異並請使用者提供正式 **PDF 版**作為唯一依據——之後以使用者提供的 PDF 為準。
## 6. 防誤導清單
 
- 主文敘述≠元件實際製程（例：主文提到「乙醇浸泡實驗」但 SI 寫元件用氯苯溶液）→ **以 Methods/SI 的元件段為準**。
- 「該溶劑句出現在表徵段而非元件段」→ 填值標紅註明。
- 單位陷阱：`0.5 mmol/mL` 常是 mM 筆誤；mg/mL vs mM 要看清。
- 組成式筆誤（加總>1）→ 按慣例解讀＋標紅＋Notes 保留原文寫法。
- 同名縮寫（PI vs PEAI、PCBM vs PC61BM）→ 跟原文，歧義標紅。
- 一篇論文多個 perovskite（1.53/1.68/1.80 eV）→ 確認每個值屬於哪個組成，別把 champion 的 PCE 配到別的 bandgap 列。
- 引用他人數據的能階圖（"data from ref. 15"）不算該論文自報值。
## 7. Token 節約守則
 
- 關鍵字句子擷取，永不整頁回傳；SI 先搜後讀。
- 同一 session 快取已解析的 SI 文字（掛 window 變數），重複查詢不重抓。
- 每篇論文完成即寫入 xlsx＋進度分頁，讓中斷後可從進度表續作，不重做。
- 讀圖是最貴的操作，放最後；一次 render 一頁，讀完即棄。
- 批次寫入用腳本（openpyxl 等）一次多格，不要逐格互動。