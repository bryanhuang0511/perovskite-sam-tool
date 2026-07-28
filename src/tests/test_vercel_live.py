import requests
import json
import os

pdf_path = r"c:\Users\yexia\Documents\黃士緯\大學\趙宇強\GitHub\擷取工具\2023 99筆 machine-learning-accelerated-design-of-self-assembled-monolayers-for-high-performance-perovskite-solar-cells.pdf"

from pypdf import PdfReader
reader = PdfReader(pdf_path)
full_text = ""
for i, page in enumerate(reader.pages):
    full_text += f"\n## Page {i+1}\n" + (page.extract_text() or "")

print(f"Testing live Vercel endpoint: https://perovskite-sam-tool.vercel.app/api/extract-text-sam")
print(f"Sending payload with text length: {len(full_text)} chars...")

try:
    res = requests.post(
        "https://perovskite-sam-tool.vercel.app/api/extract-text-sam",
        json={
            "markdown": full_text,
            "filename": "2023_paper.pdf",
            "api_key": os.environ.get("GEMINI_API_KEY", ""),
            "provider": "gemini",
            "model_name": "gemini-3.6-flash"
        },
        timeout=30
    )
    print("Status code:", res.status_code)
    print("Response snippet:", res.text[:300])
    if res.status_code == 200:
        data = res.json()
        print("doi_count:", data.get("doi_count"))
        print("sam_count:", data.get("sam_count"))
except Exception as e:
    print("Vercel Request Error:", e)
