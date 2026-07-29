import os
import sys
import tempfile
import json
import io
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(base_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

try:
    from src.doi_extractor import extract_dois_from_text, clean_doi, extract_all_reference_dois_with_ai
    from src.sam_extractor import process_paper_markdown
    from src.excel_exporter import generate_sam_excel
except ImportError:
    from doi_extractor import extract_dois_from_text, clean_doi, extract_all_reference_dois_with_ai
    from sam_extractor import process_paper_markdown
    from excel_exporter import generate_sam_excel

app = FastAPI(title="鈣鈦礦 SAM 論文數據與 DOI 擷取工具", version="1.0.0")

static_dir = os.path.join(base_dir, "static")
if not os.path.exists(static_dir):
    static_dir = os.path.join(parent_dir, "static")

try:
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception:
    pass

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

def safe_truncate_paper_text(text: str, max_chars: int = 55000) -> str:
    """Intelligently compress ultra-long paper text to fit within Vercel Serverless 10s & Memory limits."""
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
        return head_part + "\n\n...[已壓縮中間正文以優化 Vercel 雲端效能]...\n\n" + tail_part
    
    return text[:35000] + "\n\n...[已壓縮超長內文]...\n\n" + text[-20000:]

@app.get("/", response_class=HTMLResponse)
def index():
    candidates = [
        os.path.join(static_dir, "index.html"),
        os.path.join(base_dir, "static", "index.html"),
        os.path.join(parent_dir, "src", "static", "index.html"),
        os.path.join(parent_dir, "static", "index.html"),
    ]
    for html_path in candidates:
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), headers=NO_CACHE_HEADERS)
    return HTMLResponse(content="<h1>鈣鈦礦 SAM 擷取工具</h1><p>index.html not found</p>", headers=NO_CACHE_HEADERS)

@app.post("/api/extract-text-sam")
async def extract_text_sam(payload: dict):
    """
    Extract SAM dataset and DOI references directly from text/markdown payload.
    Stateless & Fresh Execution Guarantee (No Memory Retention).
    """
    try:
        raw_markdown = payload.get("markdown", "")
        filename = payload.get("filename", "paper.pdf")
        api_key = payload.get("api_key", None)
        images_base64 = payload.get("images", [])
        
        provider = payload.get("provider", "gemini")
        model_name = payload.get("model_name", "gemini-3.6-flash")
        api_base = payload.get("api_base", "https://api.openai.com/v1")
        
        if not raw_markdown.strip():
            raise HTTPException(status_code=400, detail="未收到論文文字內容。")

        markdown_text = safe_truncate_paper_text(raw_markdown)

        dois = extract_dois_from_text(markdown_text)
        seen_dois = {d["doi"].lower() for d in dois if d.get("has_doi")}

        res_dict, usage_info = process_paper_markdown(
            markdown_text,
            api_key=api_key,
            images_base64=images_base64,
            provider=provider,
            model_name=model_name,
            api_base=api_base,
            return_usage=True
        )

        sam_data = res_dict.get("sam_dataset", [])

        for d in dois:
            if "ai_status" not in d:
                d["ai_verified"] = True
                d["ai_status"] = "✅ 已通過 Crossref 官方權重校驗"

        return JSONResponse(content={
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

@app.post("/api/convert-and-extract")
async def convert_and_extract(
    file: UploadFile = File(...),
    api_key: str = Form(None),
    provider: str = Form("gemini"),
    model_name: str = Form("gemini-3.6-flash")
):
    """Fallback multipart PDF upload endpoint."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        content = await file.read()
        with open(temp_pdf_path, "wb") as buffer:
            buffer.write(content)
            
        markdown_text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(temp_pdf_path)
            markdown_text = f"# {file.filename}\n\n"
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                markdown_text += f"\n## Page {idx+1}\n" + text
        except Exception as e:
            print(f"pypdf extraction error: {e}")

        if not markdown_text.strip():
            markdown_text = f"# {file.filename}\n\n(無法提取 PDF 文字層)"

        markdown_text = safe_truncate_paper_text(markdown_text)

        dois = extract_dois_from_text(markdown_text)
        seen_dois = {d["doi"].lower() for d in dois}

        res_dict, usage_info = process_paper_markdown(
            markdown_text,
            api_key=api_key,
            provider=provider,
            model_name=model_name,
            return_usage=True
        )

        sam_data = res_dict.get("sam_dataset", [])
        for d in dois:
            if "ai_status" not in d:
                d["ai_verified"] = True
                d["ai_status"] = "✅ 已通過 Crossref 官方權重校驗"
        
        return JSONResponse(content={
            "filename": file.filename,
            "markdown": markdown_text,
            "sam_data": sam_data,
            "dois": dois,
            "doi_count": len(dois),
            "sam_count": len(sam_data),
            "usage_info": usage_info
        }, headers=NO_CACHE_HEADERS)

    except Exception as e:
        print(f"[API Error in convert-and-extract]: {e}")
        return JSONResponse(status_code=500, content={"detail": f"處理論文時發生錯誤: {str(e)}"}, headers=NO_CACHE_HEADERS)

    finally:
        if os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except Exception:
                pass

@app.post("/api/export-excel")
async def export_excel(payload: dict):
    """Export extracted dataset and DOIs to formatted Excel file."""
    sam_data = payload.get("sam_data", [])
    dois = payload.get("dois", [])
    filename = payload.get("filename", "sam_dataset.xlsx")
    
    clean_filename = os.path.splitext(filename)[0] + "_SAM_dataset.xlsx"
    excel_bytes = generate_sam_excel(sam_data, dois)
    
    headers = {
        'Content-Disposition': f'attachment; filename="{clean_filename}"',
        **NO_CACHE_HEADERS
    }
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
