import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

try:
    from src.app import app
except Exception as e:
    # If src.app fails to import, create a minimal FastAPI that reports the error
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    error_msg = traceback.format_exc()
    
    @app.get("/")
    @app.post("/api/extract-text-sam")
    @app.post("/api/convert-and-extract")
    async def error_handler():
        return JSONResponse(
            status_code=500,
            content={"error": "Import failed", "traceback": error_msg}
        )
