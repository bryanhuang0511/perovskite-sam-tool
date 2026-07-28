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
    """Resolve a reference citation string (Authors, Journal, Year, Volume) to exact DOI via Crossref API."""
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

    lines = unwrapped_text.split('\n')
    
    ref_section_start = False
    ref_keywords = [
        r'^#*\s*References\b', r'^#*\s*REFERENCE\b', r'^#*\s*References and Notes\b',
        r'^#*\s*Literature Cited\b', r'^#*\s*Bibliography\b', r'^#*\s*文獻\b', r'^#*\s*參考文獻\b'
    ]
    
    pattern = r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+'

    # 1. Direct Regex Match (Line-by-line)
    for idx, line in enumerate(lines):
        for kw in ref_keywords:
            if re.search(kw, line, re.IGNORECASE):
                ref_section_start = True
                break

        matches = re.findall(pattern, line, re.IGNORECASE)
        for match in matches:
            doi = clean_doi(match)
            if doi.startswith('10.') and '/' in doi and len(doi) > 7:
                if doi.lower() not in seen_dois:
                    seen_dois.add(doi.lower())
                    results.append({
                        "doi": doi,
                        "url": f"https://doi.org/{doi}",
                        "line_number": idx + 1,
                        "context": line.strip()[:200],
                        "in_reference_section": ref_section_start
                    })

    # 2. Global Regex Match across entire text
    global_matches = re.findall(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b', unwrapped_text)
    for match in global_matches:
        doi = clean_doi(match)
        if doi.startswith('10.') and '/' in doi and len(doi) > 7:
            if doi.lower() not in seen_dois:
                seen_dois.add(doi.lower())
                results.append({
                    "doi": doi,
                    "url": f"https://doi.org/{doi}",
                    "line_number": 1,
                    "context": "Full text extract",
                    "in_reference_section": True
                })

    # 3. Reference Citation Parsing & Crossref Resolution (If fewer than 5 explicit DOIs found)
    if len(results) < 10:
        ref_entries = re.findall(r'(?:^|\n)(?:\(\d+\)|\[\d+\]|\d+\.)\s+([^\n]+(?:\n[^\(\[\d\n]+)*)', unwrapped_text)
        for idx, ref_text in enumerate(ref_entries[:45], start=1):
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
                    "context": clean_ref[:200],
                    "in_reference_section": True
                })

    return results
