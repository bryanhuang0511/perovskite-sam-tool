import sys
import os
import re
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\yexia\Documents\黃士緯\大學\趙宇強\GitHub\擷取工具\2026 Review  pin  1-s2.0-S0927024826000553-main [Solar Energy Materials and Solar Cells 299 (2026) 114214 ].pdf"

from pypdf import PdfReader
reader = PdfReader(pdf_path)
print(f"Reading PDF: {pdf_path} ({len(reader.pages)} pages)...")

full_text = ""
for i, page in enumerate(reader.pages):
    full_text += f"\n## Page {i+1}\n" + (page.extract_text() or "")

print(f"Full Text Length: {len(full_text)} characters.")

# Test finding all reference citations
ref_entries = re.findall(r'(?:\n\[\d{1,3}\]|\n\(\d{1,3}\)|\n\d{1,3}\.)\s+([^\n]+(?:\n(?!\n?\[\d+|\n?\(\d+|\n?\d+\.)[^\n]+)*)', full_text)
print(f"Regex found {len(ref_entries)} reference entries!")

direct_dois = re.findall(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+', full_text, re.IGNORECASE)
print(f"Regex found {len(set(direct_dois))} direct DOIs!")
