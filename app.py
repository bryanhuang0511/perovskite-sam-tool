import os
import tempfile
import json
import io
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from doi_extractor import extract_dois_from_text
from sam_extractor import process_paper_markdown
from excel_exporter import generate_sam_excel

app = FastAPI(title="鈣鈦礦 SAM 論文數據與 DOI 擷取工具", version="1.0.0")

# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/extract-text-sam")
async def extract_text_sam(payload: dict):
    """Extract SAM dataset and DOI references directly from text/markdown payload (Bypasses Vercel 4.5MB binary PDF upload limit)."""
    markdown_text = payload.get("markdown", "")
    filename = payload.get("filename", "paper.pdf")
    api_key = payload.get("api_key", None)
    
    if not markdown_text.strip():
        raise HTTPException(status_code=400, detail="未收到論文文字內容。")

    # Extract Reference DOIs
    dois = extract_dois_from_text(markdown_text)
    
    # Extract SAM p-i-n perovskite dataset features
    sam_data = process_paper_markdown(markdown_text, api_key=api_key)
    
    return JSONResponse(content={
        "filename": filename,
        "markdown": markdown_text,
        "sam_data": sam_data,
        "dois": dois,
        "doi_count": len(dois),
        "sam_count": len(sam_data)
    })

@app.post("/api/convert-and-extract")
async def convert_and_extract(
    file: UploadFile = File(...),
    api_key: str = Form(None)
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

        dois = extract_dois_from_text(markdown_text)
        sam_data = process_paper_markdown(markdown_text, api_key=api_key)
        
        return JSONResponse(content={
            "filename": file.filename,
            "markdown": markdown_text,
            "sam_data": sam_data,
            "dois": dois,
            "doi_count": len(dois),
            "sam_count": len(sam_data)
        })

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
        'Content-Disposition': f'attachment; filename="{clean_filename}"'
    }
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
