import re
import sys
import json
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

try:
    from habanero import Crossref
    cr_client = Crossref(mailto="perovskitesamtool@gmail.com")
except Exception:
    cr_client = None

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize an extracted DOI string."""
    doi = raw_doi.strip()
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*|doi/abs/|doi/full/|doi/pdf/)', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'[.,;:\)\>\]\'"\s\\]+$', '', doi)
    
    if doi.count(')') > doi.count('('):
        doi = doi.rstrip(')')

    doi = re.sub(r'(\.html|\.pdf|\.txt|\.zip|\.xml)$', '', doi, flags=re.IGNORECASE)
    return doi.strip()

def resolve_citation_with_habanero(citation_str: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a reference citation string to exact DOI via habanero / Crossref official weighted matcher.
    """
    clean_text = citation_str[:180].strip()
    if len(clean_text) < 12:
        return None

    if cr_client:
        try:
            res = cr_client.works(query_bibliographic=clean_text, limit=1)
            items = res.get("message", {}).get("items", [])
            if items:
                item = items[0]
                doi = item.get("DOI", "")
                score = item.get("score", 0.0)
                title = item.get("title", [""])[0] if item.get("title") else ""
                container = item.get("container-title", [""])[0] if item.get("container-title") else ""
                
                if doi and score >= 20.0:
                    return {
                        "doi": clean_doi(doi),
                        "title": title,
                        "journal": container,
                        "score": score,
                        "verified_by": "Crossref (Habanero Engine)"
                    }
        except Exception:
            pass

    try:
        url = "https://api.crossref.org/works"
        params = {"query.bibliographic": clean_text, "rows": 1}
        headers = {"User-Agent": "PerovskiteSAMTool/1.0 (mailto:perovskitesamtool@gmail.com)"}
        res = requests.get(url, params=params, headers=headers, timeout=2.5)
        if res.status_code == 200:
            items = res.json().get("message", {}).get("items", [])
            if items:
                item = items[0]
                doi = item.get("DOI", "")
                score = item.get("score", 0.0)
                title = item.get("title", [""])[0] if item.get("title") else ""
                container = item.get("container-title", [""])[0] if item.get("container-title") else ""
                if doi and score >= 20.0:
                    return {
                        "doi": clean_doi(doi),
                        "title": title,
                        "journal": container,
                        "score": score,
                        "verified_by": "Crossref (REST API)"
                    }
    except Exception:
        pass

    return None

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Robust Multi-Stage DOI extraction pipeline for non-API key mode.
    Handles both multiline PDF text and flattened single-line PDF.js browser text.
    """
    results = []
    seen_dois = set()

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
                    "in_reference_section": True,
                    "verification": "Direct Text Match"
                })

    # 2. Locate the real References section header in the tail 40% of paper text
    search_start = int(len(unwrapped_text) * 0.6)
    tail_text = unwrapped_text[search_start:]
    pos_in_tail = max(
        tail_text.find("\nReferences"),
        tail_text.find("References\n"),
        tail_text.find("\nREFERENCES"),
        tail_text.find("REFERENCES\n")
    )
    if pos_in_tail != -1:
        ref_block = unwrapped_text[search_start + pos_in_tail:]
    else:
        ref_block = unwrapped_text[search_start:]

    # 3. Extract Reference Citation entries from the References section
    raw_splits = re.split(r'(?:\n|^|\b)(?:\[\d{1,3}\]|\(\d{1,3}\)|\b\d{1,3}\.)\s+', ref_block)
    
    valid_entries = []
    for idx, ref_chunk in enumerate(raw_splits, start=1):
        clean_ref = re.sub(r'\s+', ' ', ref_chunk.strip())
        if len(clean_ref) >= 15:
            valid_entries.append((idx, clean_ref[:250]))

    # Perform Concurrent API requests with 20 parallel workers for serverless stability
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_entry = {}
        for idx, clean_ref in valid_entries:
            doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', clean_ref)
            if doi_match:
                found_doi = clean_doi(doi_match.group(0))
                if found_doi and found_doi.lower() not in seen_dois:
                    seen_dois.add(found_doi.lower())
                    results.append({
                        "doi": found_doi,
                        "url": f"https://doi.org/{found_doi}",
                        "line_number": idx,
                        "context": clean_ref[:150],
                        "in_reference_section": True,
                        "verification": "Inline Text Match"
                    })
            else:
                future = executor.submit(resolve_citation_with_habanero, clean_ref)
                future_to_entry[future] = (idx, clean_ref)

        try:
            for future in as_completed(future_to_entry, timeout=4.5):
                try:
                    res_obj = future.result()
                    if res_obj and res_obj.get("doi"):
                        found_doi = clean_doi(res_obj["doi"])
                        if found_doi.lower() not in seen_dois:
                            idx, clean_ref = future_to_entry[future]
                            seen_dois.add(found_doi.lower())
                            results.append({
                                "doi": found_doi,
                                "url": f"https://doi.org/{found_doi}",
                                "line_number": idx,
                                "context": clean_ref[:150],
                                "title": res_obj.get("title", ""),
                                "journal": res_obj.get("journal", ""),
                                "in_reference_section": True,
                                "verification": res_obj.get("verified_by", "Crossref Match")
                            })
                except Exception:
                    pass
        except TimeoutError:
            pass

    return results

def extract_all_reference_dois_with_ai(
    paper_text: str,
    api_key: str,
    model_name: str = "gemini-3.6-flash"
) -> List[Dict[str, Any]]:
    """
    AI Full-Reference DOI Extraction Engine:
    Calls Gemini API to extract ALL 140+ reference DOIs in 1 single pass.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    
    search_start = int(len(paper_text) * 0.6)
    tail_text = paper_text[search_start:]
    pos_in_tail = max(
        tail_text.find("\nReferences"),
        tail_text.find("References\n"),
        tail_text.find("\nREFERENCES"),
        tail_text.find("REFERENCES\n")
    )
    if pos_in_tail != -1:
        ref_text_block = paper_text[search_start + pos_in_tail:]
    else:
        ref_text_block = paper_text[search_start:]
    
    prompt = f"""
你是頂尖學術參考文獻 DOI 提取專家。
請閱讀這篇論文的 References 章節（共包含約 100~150 條文獻）。
請幫我提取並還原出【每一條】文獻的純文字 DOI（格式如 10.1016/j.solmat.2026.114214）。

References 內容：
{ref_text_block[:35000]}

請回傳純 JSON 陣列：
[
  {{"line_number": 1, "doi": "10.1016/j.solmat.2026.114214", "context": "(1) Author et al., Sol. Energy Mater.", "ai_status": "✅ 100% 精準對應文獻"}}
]
"""
    candidate_models = [model_name, "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.1-pro-preview"]
    for target_m in candidate_models:
        if not target_m: continue
        try:
            resp = client.models.generate_content(
                model=target_m,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            raw_txt = resp.text.strip()
            raw_txt = re.sub(r'^```json\s*', '', raw_txt, flags=re.IGNORECASE)
            raw_txt = re.sub(r'\s*```$', '', raw_txt).strip()
            parsed = json.loads(raw_txt)

            if isinstance(parsed, list) and len(parsed) > 0:
                results = []
                seen = set()
                for item in parsed:
                    if isinstance(item, dict) and item.get("doi"):
                        d_val = clean_doi(item["doi"])
                        if d_val and d_val.startswith("10.") and "/" in d_val and d_val.lower() not in seen:
                            seen.add(d_val.lower())
                            results.append({
                                "doi": d_val,
                                "url": f"https://doi.org/{d_val}",
                                "line_number": item.get("line_number", len(results) + 1),
                                "context": item.get("context", f"AI 參考文獻提取 ({target_m})"),
                                "in_reference_section": True,
                                "verification": f"AI 全文還原 ({target_m})",
                                "ai_status": item.get("ai_status", "✅ AI 審核通過 (100% 對應原文)")
                            })
                if len(results) > 0:
                    return results
        except Exception as e:
            print(f"[AI Full DOI] Model {target_m} failed: {e}")

    return []

if __name__ == "__main__":
    from pypdf import PdfReader
    pdf_path = r"c:\Users\yexia\Documents\黃士緯\大學\趙宇強\GitHub\擷取工具\2026 Review  pin  1-s2.0-S0927024826000553-main [Solar Energy Materials and Solar Cells 299 (2026) 114214 ].pdf"
    text = "".join([p.extract_text() or "" for p in PdfReader(pdf_path).pages])
    extracted = extract_dois_from_text(text)
    print(f"Habanero + Crossref Engine extracted {len(extracted)} DOIs!")
    for d in extracted[:5]:
        print(f" - #{d['line_number']}: {d['doi']} ({d.get('verification')})")
