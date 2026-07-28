import re
from typing import List, Dict, Any

# Standard DOI pattern
DOI_PATTERN = r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b'

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize an extracted DOI string."""
    doi = raw_doi.strip()
    
    # Strip leading URL prefixes if present
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.IGNORECASE)
    
    # Strip trailing punctuation, markdown characters, and concatenated words
    doi = re.sub(r'[.,;:\)\>\]\'"\s\\]+$', '', doi)
    
    # If trailing parenthesis exists without matching opening, trim it
    if doi.count(')') > doi.count('('):
        doi = doi.rstrip(')')

    # Strip any trailing concatenated extensions or HTML tags
    doi = re.sub(r'(\.html|\.pdf|\.txt|\.zip|\.xml)$', '', doi, flags=re.IGNORECASE)
    
    return doi.strip()

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract reference DOIs from full text or markdown content.
    Returns a list of dicts with 'doi', 'url', 'context', and 'in_reference_section'.
    """
    results = []
    seen_dois = set()

    lines = text.split('\n')
    
    ref_section_start = False
    ref_keywords = [
        r'^#*\s*References\b', r'^#*\s*REFERENCE\b', r'^#*\s*References and Notes\b',
        r'^#*\s*Literature Cited\b', r'^#*\s*Bibliography\b', r'^#*\s*文獻\b', r'^#*\s*參考文獻\b'
    ]
    
    for idx, line in enumerate(lines):
        for kw in ref_keywords:
            if re.search(kw, line, re.IGNORECASE):
                ref_section_start = True
                break

        # Search for DOIs in line
        matches = re.findall(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+', line, re.IGNORECASE)
        if not matches:
            matches = re.findall(DOI_PATTERN, line)

        for match in matches:
            doi = clean_doi(match)
            # Basic validation: must start with 10.xxxx/
            if doi.startswith('10.') and '/' in doi and len(doi) > 8:
                # Discard obviously invalid DOIs (e.g. ending with non-alphanumeric trailing garbage)
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
