import os
import sys
import json
sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory (src) and project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pypdf import PdfReader
from src.doi_extractor import extract_dois_from_text
from src.sam_extractor import process_paper_markdown
from src.excel_exporter import generate_sam_excel

pdf_path = r"c:\Users\yexia\Documents\黃士緯\大學\趙宇強\GitHub\擷取工具\2023 99筆 machine-learning-accelerated-design-of-self-assembled-monolayers-for-high-performance-perovskite-solar-cells.pdf"
api_key = os.environ.get("GEMINI_API_KEY", "")

print(f"Reading PDF file: {pdf_path}...")
reader = PdfReader(pdf_path)
full_text = ""
for i, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    full_text += f"\n## Page {i+1}\n" + text

print(f"Full PDF Text Length: {len(full_text)} characters.")

print("Step 1: Extracting DOIs with Crossref citation resolution...")
dois = extract_dois_from_text(full_text)
print(f"Extracted {len(dois)} reference DOIs!")

print("\nStep 2: Extracting SAM dataset with 100% full-paper Gemini 3.6 Flash...")
res_dict, usage_info = process_paper_markdown(
    markdown_text=full_text,
    api_key=api_key,
    provider="gemini",
    model_name="gemini-3.6-flash",
    return_usage=True
)

sam_data = res_dict.get("sam_dataset", [])
print(f"\nExtracted {len(sam_data)} SAM dataset rows!")
print("Token Usage Info:", usage_info)

excel_output = "benchmark_result_2023.xlsx"
generate_sam_excel(sam_data, dois, excel_output)
print(f"\nSaved Excel file to {excel_output}!")
