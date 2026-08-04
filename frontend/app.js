// Perovskite SAM Extractor - Decoupled Frontend JS Logic

const API_BASE = "https://sam-extractor-backend.onrender.com";  // Live Render Backend API URL

let activeJobId = "";
let currentSamData = [];
let currentDoiData = [];

const HEADER_SCHEMA = [
    { label: "Ref ID (PDF-SAM名)", key: "ref_id", color: "hdr-gray" },
    { label: "SAM material", key: "sam_material", color: "hdr-orange" },
    { label: "SMILES", key: "smiles", color: "hdr-green" },
    { label: "NiO2", key: "nio2", color: "hdr-blue" },
    { label: "Ethanol", key: "ethanol", color: "hdr-blue" },
    { label: "Toluene", key: "toluene", color: "hdr-blue" },
    { label: "IPA", key: "ipa", color: "hdr-blue" },
    { label: "THF", key: "thf", color: "hdr-blue" },
    { label: "chlorobenzene", key: "chlorobenzene", color: "hdr-blue" },
    { label: "2-Methoxyethanol", key: "methoxyethanol_2", color: "hdr-blue" },
    { label: "CH2CL2", key: "ch2cl2", color: "hdr-blue" },
    { label: "concentration(mg/ml)", key: "concentration", color: "hdr-bluegray" },
    { label: "wash", key: "wash", color: "hdr-bluegray" },
    { label: "E", key: "energy_e", color: "hdr-yellow" },
    { label: "Cs", key: "cs", color: "hdr-purple" },
    { label: "FA", key: "fa", color: "hdr-purple" },
    { label: "MA", key: "ma", color: "hdr-purple" },
    { label: "Pb", key: "pb", color: "hdr-purple" },
    { label: "Sn", key: "sn", color: "hdr-purple" },
    { label: "I", key: "i", color: "hdr-purple" },
    { label: "Br", key: "br", color: "hdr-purple" },
    { label: "CL", key: "cl", color: "hdr-purple" },
    { label: "C60", key: "c60", color: "hdr-blue" },
    { label: "BCP", key: "bcp", color: "hdr-blue" },
    { label: "PC60BM", key: "pc60bm", color: "hdr-blue" },
    { label: "PCBM", key: "pcbm", color: "hdr-blue" },
    { label: "PC61BM", key: "pc61bm", color: "hdr-blue" },
    { label: "PEAI", key: "peai", color: "hdr-blue" },
    { label: "ALD-SnO2", key: "ald_sno2", color: "hdr-blue" },
    { label: "PCE", key: "pce", color: "hdr-yellow" },
    { label: "Reference_DOI", key: "reference_doi", color: "hdr-gray" },
    { label: "Ref_author", key: "ref_author", color: "hdr-gray" },
    { label: "Ref_journal", key: "ref_journal", color: "hdr-gray" },
    { label: "Notes", key: "notes", color: "hdr-white" }
];

let mainPdfFile = null;
let siPdfFile = null;

// Tab Switcher
function switchTab(tabName) {
    document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    if (tabName === 'live') {
        document.getElementById('tabLiveBtn').classList.add('active');
        document.getElementById('tabLiveContent').classList.add('active');
    } else {
        document.getElementById('tabHistoryBtn').classList.add('active');
        document.getElementById('tabHistoryContent').classList.add('active');
        loadHistoryJobs();
    }
}

// File Drag & Drop Setup
document.addEventListener('DOMContentLoaded', () => {
    setupUploadZone('dropZoneMain', 'fileInputMain', (file) => {
        mainPdfFile = file;
        document.getElementById('mainFileSubtitle').innerText = `✅ 已選擇: ${file.name}`;
        checkStartBtn();
    });

    setupUploadZone('dropZoneSi', 'fileInputSi', (file) => {
        siPdfFile = file;
        document.getElementById('siFileSubtitle').innerText = `✅ 已選擇: ${file.name}`;
    });

    document.getElementById('startExtractBtn').addEventListener('click', startExtraction);
});

function setupUploadZone(zoneId, inputId, onFileSelect) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);

    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) onFileSelect(e.target.files[0]);
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.style.borderColor = '#6366f1';
    });

    zone.addEventListener('dragleave', () => {
        zone.style.borderColor = '#475569';
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.style.borderColor = '#475569';
        if (e.dataTransfer.files.length > 0) onFileSelect(e.dataTransfer.files[0]);
    });
}

function checkStartBtn() {
    const startBtn = document.getElementById('startExtractBtn');
    startBtn.style.display = mainPdfFile ? 'inline-block' : 'none';
}

// Read PDF text using pdf.js
async function extractPdfText(file) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let fullText = "";
    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items.map(item => item.str).join(' ');
        fullText += `\n\n## Page ${i}\n` + pageText;
    }
    return fullText;
}

// Start Extraction Execution
async function startExtraction() {
    if (!mainPdfFile) return;

    const startBtn = document.getElementById('startExtractBtn');
    startBtn.disabled = true;
    startBtn.innerText = "⏳ 正在使用 AI 與 Agent 工具庫處理論文中...";

    try {
        const mainText = await extractPdfText(mainPdfFile);
        let siText = "";
        if (siPdfFile) {
            siText = await extractPdfText(siPdfFile);
        }

        const apiKey = document.getElementById('apiKey').value.trim();
        const modelProvider = document.getElementById('modelProvider').value;

        const payload = {
            filename: mainPdfFile.name,
            markdown: mainText,
            si_markdown: siText,
            api_key: apiKey,
            provider: modelProvider.startsWith('gemini') ? 'gemini' : modelProvider,
            model_name: modelProvider
        };

        const resp = await fetch(`${API_BASE}/api/extract-text-sam`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '擷取失敗');
        }

        const data = await resp.json();
        currentSamData = data.sam_data || [];
        currentDoiData = data.dois || [];
        activeJobId = data.job_id || "";

        document.getElementById('resultArea').style.display = 'block';
        document.getElementById('resultTitle').innerText = `📊 擷取成果表格 (${data.sam_count} 筆記錄, Job ID: ${activeJobId})`;
        renderSamTable('tableHeaderRow', 'tableBody', currentSamData);

    } catch (err) {
        alert(`處理出錯: ${err.message}`);
    } finally {
        startBtn.disabled = false;
        startBtn.innerText = "🚀 開始 AI 數據擷取與自動校驗";
    }
}

// Render 35-column SAM table
function renderSamTable(headerRowId, bodyId, dataset) {
    const headerRow = document.getElementById(headerRowId);
    const body = document.getElementById(bodyId);

    headerRow.innerHTML = HEADER_SCHEMA.map(h => `<th class="${h.color}">${h.label}</th>`).join('');
    body.innerHTML = "";

    dataset.forEach(row => {
        const tr = document.createElement('tr');
        const colors = row.confidence_colors || {};

        HEADER_SCHEMA.forEach(h => {
            const td = document.createElement('td');
            const val = row[h.key] !== undefined && row[h.key] !== null ? row[h.key] : "";
            td.innerText = val;

            const colorName = (colors[h.key] || "white").toLowerCase();
            if (colorName === 'red') td.className = 'cell-red';
            else if (colorName === 'black') td.className = 'cell-black';
            else td.className = 'cell-white';

            tr.appendChild(td);
        });
        body.appendChild(tr);
    });
}

// History & SQLite Functions
async function loadHistoryJobs() {
    const dateInput = document.getElementById('filterDate').value;
    const url = dateInput ? `${API_BASE}/api/jobs?date=${dateInput}` : `${API_BASE}/api/jobs`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        const grid = document.getElementById('jobGrid');
        grid.innerHTML = "";

        if (!data.jobs || data.jobs.length === 0) {
            grid.innerHTML = `<p style="color: #94a3b8; grid-column: 1/-1;">查無歷史任務紀錄 (${dateInput || '全量'})</p>`;
            return;
        }

        data.jobs.forEach(job => {
            const card = document.createElement('div');
            card.className = 'job-card';
            card.onclick = () => loadJobDetail(job.job_id);

            card.innerHTML = `
                <div class="job-header">
                    <span class="job-id-tag">${job.job_id}</span>
                    <span class="job-date">${job.created_at}</span>
                </div>
                <div class="job-filename" title="${job.filename}">${job.filename}</div>
                <div style="font-size: 0.85rem; color: #94a3b8;">
                    包含 <strong style="color: #38bdf8;">${job.sam_count}</strong> 筆 SAM 資料, 
                    <strong style="color: #a855f7;">${job.doi_count}</strong> 筆 DOIs
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (e) {
        console.error("載入歷史失敗", e);
    }
}

async function loadJobDetail(jobId) {
    try {
        const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        const job = await resp.json();
        activeJobId = jobId;

        document.getElementById('jobDetailContainer').style.display = 'block';
        document.getElementById('jobDetailTitle').innerText = `📊 任務明細 (${job.job_id} - ${job.filename})`;

        renderSamTable('jobTableHeaderRow', 'jobTableBody', job.sam_dataset || []);
        document.getElementById('jobDetailContainer').scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
        alert("載入任務詳情失敗");
    }
}

function handleSearchKeyup(e) {
    if (e.key === 'Enter') executeSearch();
}

async function executeSearch() {
    const q = document.getElementById('searchKeyword').value.trim();
    if (!q) {
        loadHistoryJobs();
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
        const data = await resp.json();

        document.getElementById('jobDetailContainer').style.display = 'block';
        document.getElementById('jobDetailTitle').innerText = `🔍 SQLite 搜尋結果 (關鍵字: "${q}", 共 ${data.count} 筆)`;
        renderSamTable('jobTableHeaderRow', 'jobTableBody', data.records || []);
    } catch (e) {
        alert("搜尋 SQLite 失敗");
    }
}

function resetHistoryFilters() {
    document.getElementById('filterDate').value = "";
    document.getElementById('searchKeyword').value = "";
    document.getElementById('jobDetailContainer').style.display = 'none';
    loadHistoryJobs();
}

function exportCurrentExcel() {
    if (!activeJobId) {
        alert("請先完成一次擷取或選擇一個歷史任務");
        return;
    }
    window.location.href = `${API_BASE}/api/export-job-excel/${activeJobId}`;
}

function exportJobExcel(jobId) {
    if (!jobId) return;
    window.location.href = `${API_BASE}/api/export-job-excel/${jobId}`;
}
