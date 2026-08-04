import os
import sys
import tempfile
import json
import io
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query

from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Also load .env from ROOT_DIR
env_file = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except Exception:
        pass

try:
    from doi_extractor import extract_dois_from_text, clean_doi
    from sam_extractor import process_paper_markdown
    from excel_exporter import generate_sam_excel
    from database import save_job_and_records, get_all_jobs, get_job_detail, search_records, init_db
except ImportError:
    try:
        from .doi_extractor import extract_dois_from_text, clean_doi
        from .sam_extractor import process_paper_markdown
        from .excel_exporter import generate_sam_excel
        from .database import save_job_and_records, get_all_jobs, get_job_detail, search_records, init_db
    except ImportError:
        from backend.doi_extractor import extract_dois_from_text, clean_doi
        from backend.sam_extractor import process_paper_markdown
        from backend.excel_exporter import generate_sam_excel
        from backend.database import save_job_and_records, get_all_jobs, get_job_detail, search_records, init_db


# Initialize SQLite database on app startup
init_db()

app = FastAPI(
    title="鈣鈦礦 SAM 論文數據與 DOI 擷取工具 (Backend API)",
    version="2.0.0",
    description="Clean Decoupled FastAPI Backend with SQLite & CSV Persistence"
)

# Enable CORS for decoupled frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "static")

try:
    if os.path.isdir(FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
except Exception:
    pass

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}


def safe_truncate_paper_text(text: str, max_chars: int = 55000) -> str:
    """Intelligently compress ultra-long paper text to fit within serverless/memory limits."""
    if len(text) <= max_chars:
        return text
    
    search_start = int(len(text) * 0.6)
    tail_text = text[search_start:]
    pos_in_tail = max(
        tail_text.find("\nReferences"),
        tail_text.find("References\n"),
        tail_text.find("\nREFERENCES"),
        tail_text.find("REFERENCES\n")
    )
    if pos_in_tail != -1:
        ref_start_pos = search_start + pos_in_tail
        head_part = text[:30000]
        tail_part = text[ref_start_pos:]
        return head_part + "\n\n...[已壓縮中間正文以優化雲端效能]...\n\n" + tail_part
    
    return text[:35000] + "\n\n...[已壓縮超長內文]...\n\n" + text[-20000:]


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index():
    """Serve frontend index.html."""
    candidates = [
        os.path.join(FRONTEND_DIR, "index.html"),
        os.path.join(ROOT_DIR, "frontend", "index.html"),
        os.path.join(BASE_DIR, "static", "index.html"),
    ]
    for html_path in candidates:
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), headers=NO_CACHE_HEADERS)
    return HTMLResponse(content="<h1>鈣鈦礦 SAM 擷取工具 API 後端</h1><p>Frontend index.html not found</p>", headers=NO_CACHE_HEADERS)


@app.get("/api/health")
def health_check():
    """Health status and backend key status check."""
    gemini_key_set = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    openai_key_set = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "ok",
        "gemini_key_configured": gemini_key_set,
        "openai_key_configured": openai_key_set,
        "database_storage": "SQLite + CSV Dual Persistence Active",
        "security_mode": "Backend Secure API Key Proxy Active"
    }


@app.post("/api/extract-text-sam")
async def extract_text_sam(payload: dict):
    """
    Extract SAM dataset and DOI references directly from text/markdown payload.
    Automatically persists results to SQLite database and CSV file.
    """
    try:
        raw_markdown = payload.get("markdown", "")
        si_markdown = payload.get("si_markdown", "")
        filename = payload.get("filename", "paper.pdf")
        api_key = payload.get("api_key", None)
        images_base64 = payload.get("images", [])
        
        provider = payload.get("provider", "gemini")
        model_name = payload.get("model_name", "gemini-3.6-flash")
        api_base = payload.get("api_base", "https://api.openai.com/v1")
        
        # Secure API Key Fallback from server environment
        if not api_key or not str(api_key).strip():
            if provider == "gemini":
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            else:
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")

        if not raw_markdown.strip():
            raise HTTPException(status_code=400, detail="未收到論文文字內容。")

        markdown_text = safe_truncate_paper_text(raw_markdown)
        si_text = safe_truncate_paper_text(si_markdown) if si_markdown and si_markdown.strip() else None

        dois = extract_dois_from_text(markdown_text)

        res_dict, usage_info = process_paper_markdown(
            markdown_text,
            api_key=api_key,
            images_base64=images_base64,
            provider=provider,
            model_name=model_name,
            api_base=api_base,
            return_usage=True,
            si_markdown_text=si_text
        )

        sam_data = res_dict.get("sam_dataset", [])

        # Auto-save job to SQLite & CSV persistence
        job_id = save_job_and_records(
            filename=filename,
            sam_dataset=sam_data,
            doi_list=dois
        )

        return JSONResponse(content={
            "job_id": job_id,
            "filename": filename,
            "markdown": markdown_text,
            "sam_data": sam_data,
            "dois": dois,
            "doi_count": len(dois),
            "sam_count": len(sam_data),
            "usage_info": usage_info
        }, headers=NO_CACHE_HEADERS)
    except Exception as e:
        print(f"[API Error in extract-text-sam]: {e}")
        return JSONResponse(status_code=500, content={"detail": f"處理論文時發生錯誤: {str(e)}"}, headers=NO_CACHE_HEADERS)


@app.get("/api/jobs")
def list_jobs(date: Optional[str] = Query(None, description="Filter by date string YYYY-MM-DD")):
    """List historical extraction jobs from SQLite database."""
    try:
        jobs = get_all_jobs(date_str=date)
        return {"count": len(jobs), "jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Retrieve details and 35-column records of a specific job."""
    try:
        job = get_job_detail(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return job
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
def search_db(q: str = Query(..., description="Search keyword across SAM name, SMILES, DOI, filename")):
    """Search records across all jobs in SQLite database."""
    try:
        results = search_records(q)
        return {"query": q, "count": len(results), "records": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export-job-excel/{job_id}")
def export_job_excel(job_id: str):
    """Generate and download Excel file for a specific job."""
    try:
        job = get_job_detail(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        excel_bytes = generate_sam_excel(job.get("sam_dataset", []))
        filename = f"SAM_Extraction_{job_id}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                **NO_CACHE_HEADERS
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
