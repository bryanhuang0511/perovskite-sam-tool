import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from src.app import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    err_tb = traceback.format_exc()
    @app.get("/{full_path:path}")
    @app.post("/{full_path:path}")
    async def catch_all_error(full_path: str):
        return JSONResponse(status_code=500, content={"error": "Fatal App Import Error", "traceback": err_tb})
