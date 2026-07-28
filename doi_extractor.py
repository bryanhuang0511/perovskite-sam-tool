import re
from typing import List, Dict, Any

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize an extracted DOI string."""
    doi = raw_doi.strip()
    
    # Strip leading URL prefixes if present
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*|doi/abs/|doi/full/|doi/pdf/)', '', doi, flags=re.IGNORECASE)
    
    # Strip trailing punctuation, markdown characters, brackets, and concatenated words
    doi = re.sub(r'[.,;:\)\>\]\'"\s\\]+$', '', doi)
    
    # If trailing parenthesis exists without matching opening, trim it
    if doi.count(')') > doi.count('('):
        doi = doi.rstrip(')')

    # Strip any trailing concatenated extensions
    doi = re.sub(r'(\.html|\.pdf|\.txt|\.zip|\.xml)$', '', doi, flags=re.IGNORECASE)
    
    return doi.strip()

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract reference DOIs from full text or markdown content with line-wrap resilience.
    Returns a list of dicts with 'doi', 'url', 'context', and 'in_reference_section'.
    """
    results = []
    seen_dois = set()

    # Pre-process text to join DOIs split across line breaks
    # e.g., "10.1002/\nadma.202520220" or "10.1016/j.nano-\nen.2023.108210"
    unwrapped_text = re.sub(r'(10\.\d{4,9}/[^\s]+?)-\s*\n\s*([^\s]+)', r'\1\2', text)
    unwrapped_text = re.sub(r'(10\.\d{4,9}/[^\s]*?)\s*\n\s*([a-zA-Z0-9.\-_/;()]+)', r'\1\2', unwrapped_text)

    lines = unwrapped_text.split('\n')
    
    ref_section_start = False
    ref_keywords = [
        r'^#*\s*References\b', r'^#*\s*REFERENCE\b', r'^#*\s*References and Notes\b',
        r'^#*\s*Literature Cited\b', r'^#*\s*Bibliography\b', r'^#*\s*文獻\b', r'^#*\s*參考文獻\b'
    ]
    
    # Primary regex: captures 10.xxxx/xxxx with optional doi.org or doi: prefixes
    pattern = r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+'

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

    # Global fallback regex across entire text if line-by-line missed DOIs
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

    return results

if __name__ == "__main__":
    sample_text = """
    Perovskite solar cells (doi:\n 10.1038/s41586-\n021-03285-w).
    
    # References
    1. 10.1016/\nj.nanoen.2023.108210.
    2. https://doi.org/10.1021/acsenergylett.2c01123
    """
    extracted = extract_dois_from_text(sample_text)
    print(f"Extracted {len(extracted)} DOIs:")
    for d in extracted:
        print(d['doi'])
