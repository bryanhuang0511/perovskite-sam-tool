import re
from typing import List, Dict, Any

# DOI regex pattern matching standard 10.xxxx/xxxx structure
DOI_PATTERN = r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b'

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize a extracted DOI string."""
    doi = raw_doi.strip()
    # Remove trailing punctuation often captured by regex
    doi = re.sub(r'[.,;:\)\>\]]+$', '', doi)
    # Remove leading prefixes if present
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.IGNORECASE)
    return doi

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract reference DOIs from full text or markdown content.
    Returns a list of dicts with 'doi', 'url', 'context', and 'is_reference_section'.
    """
    results = []
    seen_dois = set()

    lines = text.split('\n')
    
    # Try to identify where the References section starts
    ref_section_start = False
    ref_keywords = [
        r'^#*\s*References\b', r'^#*\s*REFERENCE\b', r'^#*\s*References and Notes\b',
        r'^#*\s*Literature Cited\b', r'^#*\s*Bibliography\b', r'^#*\s*文獻\b', r'^#*\s*參考文獻\b'
    ]
    
    for idx, line in enumerate(lines):
        # Check if entering reference section
        for kw in ref_keywords:
            if re.search(kw, line, re.IGNORECASE):
                ref_section_start = True
                break

        # Search for DOIs in line
        matches = re.findall(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+', line, re.IGNORECASE)
        if not matches:
            # Also fallback to standard 10.xxx
            matches = re.findall(DOI_PATTERN, line)

        for match in matches:
            doi = clean_doi(match)
            # Basic validation of DOI format
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

    return results

if __name__ == "__main__":
    sample_text = """
    Perovskite solar cells have achieved efficiencies exceeding 25% (doi: 10.1038/s41586-021-03285-w).
    
    # References
    1. Ullah et al., Development of HTLs. 10.1016/j.nanoen.2023.108210.
    2. Wang et al., ACS Energy Lett. 2022. https://doi.org/10.1021/acsenergylett.2c01123
    """
    extracted = extract_dois_from_text(sample_text)
    print(f"Extracted {len(extracted)} DOIs:")
    for d in extracted:
        print(d)
