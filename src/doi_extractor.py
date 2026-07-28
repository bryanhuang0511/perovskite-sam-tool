import re
import requests
from typing import List, Dict, Any

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize an extracted DOI string."""
    doi = raw_doi.strip()
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*|doi/abs/|doi/full/|doi/pdf/)', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'[.,;:\)\>\]\'"\s\\]+$', '', doi)
    
    if doi.count(')') > doi.count('('):
        doi = doi.rstrip(')')

    doi = re.sub(r'(\.html|\.pdf|\.txt|\.zip|\.xml)$', '', doi, flags=re.IGNORECASE)
    return doi.strip()

def resolve_citation_str_to_doi(citation_str: str) -> str:
    """Resolve a reference citation string to exact DOI via Crossref API."""
    try:
        url = "https://api.crossref.org/works"
        params = {"query.bibliographic": citation_str[:160], "rows": 1}
        headers = {"User-Agent": "PerovskiteSAMTool/1.0"}
        res = requests.get(url, params=params, headers=headers, timeout=3)
        if res.status_code == 200:
            items = res.json().get("message", {}).get("items", [])
            if items:
                return items[0].get("DOI", "")
    except Exception:
        pass
    return ""

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract reference DOIs from full text or markdown content.
    Combines direct 10.xxxx regex parsing and Crossref bibliographic resolution for citations without explicit DOIs.
    """
    results = []
    seen_dois = set()

    # Pre-process text to join line breaks in DOIs
    unwrapped_text = re.sub(r'(10\.\d{4,9}/[^\s]+?)-\s*\n\s*([^\s]+)', r'\1\2', text)
    unwrapped_text = re.sub(r'(10\.\d{4,9}/[^\s]*?)\s*\n\s*([a-zA-Z0-9.\-_/;()]+)', r'\1\2', unwrapped_text)

    # 1. Direct Regex Match for 10.xxxx/xxxx
    pattern = r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+'
    direct_matches = re.findall(pattern, unwrapped_text, re.IGNORECASE)
    for match in direct_matches:
        doi = clean_doi(match)
        if doi.startswith('10.') and '/' in doi and len(doi) > 7:
            if doi.lower() not in seen_dois:
                seen_dois.add(doi.lower())
                results.append({
                    "doi": doi,
                    "url": f"https://doi.org/{doi}",
                    "line_number": len(results) + 1,
                    "context": match[:150],
                    "in_reference_section": True
                })

    # 2. Extract Reference Citation entries (like (1) Author... Journal 2023, [2] Author..., 1. Author...)
    ref_entries = re.findall(r'(?:\(\d{1,3}\)|\[\d{1,3}\]|\b\d{1,3}\.)\s+([^\n]+(?:\n[^\(\[\d\n]+)*)', unwrapped_text)
    
    for idx, ref_text in enumerate(ref_entries[:50], start=1):
        clean_ref = re.sub(r'\s+', ' ', ref_text.strip())
        if len(clean_ref) < 15:
            continue
            
        doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', clean_ref)
        found_doi = clean_doi(doi_match.group(0)) if doi_match else resolve_citation_str_to_doi(clean_ref)
        
        if found_doi and found_doi.lower() not in seen_dois:
            seen_dois.add(found_doi.lower())
            results.append({
                "doi": found_doi,
                "url": f"https://doi.org/{found_doi}",
                "line_number": idx,
                "context": clean_ref[:150],
                "in_reference_section": True
            })

    return results

if __name__ == "__main__":
    from pypdf import PdfReader
    pdf_path = r"c:\Users\yexia\Documents\黃士緯\大學\趙宇強\GitHub\擷取工具\2023 99筆 machine-learning-accelerated-design-of-self-assembled-monolayers-for-high-performance-perovskite-solar-cells.pdf"
    text = "".join([p.extract_text() or "" for p in PdfReader(pdf_path).pages])
    extracted = extract_dois_from_text(text)
    print(f"Extracted {len(extracted)} DOIs from 2023 paper:")
    for d in extracted[:10]:
        print(f" - #{d['line_number']}: {d['doi']} ({d['context'][:60]}...)")
