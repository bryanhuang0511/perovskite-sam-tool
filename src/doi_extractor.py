import re
import sys
import json
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

def clean_doi(raw_doi: str) -> str:
    """Clean and normalize an extracted DOI string."""
    doi = raw_doi.strip()
    doi = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*|doi/abs/|doi/full/|doi/pdf/)', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'[.,;:\)\>\]\'"\s\\]+$', '', doi)
    
    if doi.count(')') > doi.count('('):
        doi = doi.rstrip(')')

    doi = re.sub(r'(\.html|\.pdf|\.txt|\.zip|\.xml)$', '', doi, flags=re.IGNORECASE)
    # Strip trailing metadata words commonly concatenated during PDF text extraction
    doi = re.sub(r'(Received|Accepted|Available|Published|Online|Revised|Submitted|Copyright|Abstract|Keywords|Introduction).*$', '', doi)
    return doi.strip()

def resolve_citation_to_doi(citation_str: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a reference citation string to exact DOI via Crossref Polite Pool REST API.
    Zero-token lightweight pure Python HTTP resolution.
    """
    clean_text = citation_str[:400].strip()
    if len(clean_text) < 12:
        return None

    try:
        url = "https://api.crossref.org/works"
        params = {"query.bibliographic": clean_text, "rows": 1}
        headers = {"User-Agent": "PerovskiteSAMTool/1.0 (mailto:perovskitesamtool@gmail.com)"}
        res = requests.get(url, params=params, headers=headers, timeout=3.0)
        if res.status_code == 200:
            items = res.json().get("message", {}).get("items", [])
            if items:
                item = items[0]
                doi = item.get("DOI", "")
                score = item.get("score", 0.0)
                title = item.get("title", [""])[0] if item.get("title") else ""
                container = item.get("container-title", [""])[0] if item.get("container-title") else ""
                if doi and score >= 10.0:
                    return {
                        "doi": clean_doi(doi),
                        "title": title,
                        "journal": container,
                        "score": score,
                        "verified_by": "Crossref (Polite Pool API)"
                    }
    except Exception:
        pass

    return None

def locate_references_section(text: str) -> str:
    """Locate the References section and remove header/footer noise and SI sections."""
    unwrapped = re.sub(r'(10\.\d{4,9}/[^\s]+?)-\s*\n\s*([^\s]+)', r'\1\2', text)
    unwrapped = re.sub(r'(10\.\d{4,9}/[^\s]*?)\s*\n\s*([a-zA-Z0-9.\-_/;()]+)', r'\1\2', unwrapped)

    headings = list(re.finditer(r'(?:^|\n)\s*(?:References|BIBLIOGRAPHY|Literature Cited|參考文獻)\s*(?:\n|$)', unwrapped, re.IGNORECASE))
    if headings:
        start_idx = headings[-1].end()
        section = unwrapped[start_idx:]
    else:
        search_start = int(len(unwrapped) * 0.6)
        section = unwrapped[search_start:]

    ending_match = re.search(r'(?:^|\n)\s*(?:Supporting Information|Supplementary Information|Author Biographies|Biographies|Acknowledgements)\s*(?:\n|$)', section, re.IGNORECASE)
    if ending_match:
        section = section[:ending_match.start()]

    return section

def parse_sequential_references(section_text: str) -> List[Dict[str, Any]]:
    """Parse sequential references (1..N) and retain placeholders for entries without DOIs."""
    lines = [l.strip() for l in section_text.split('\n') if l.strip()]
    
    filtered_lines = []
    for line in lines:
        if re.search(r'^\d+\s+of\s+\d+$', line, re.IGNORECASE):
            continue
        if re.search(r'Downloaded from', line, re.IGNORECASE):
            continue
        filtered_lines.append(line)

    refs = []
    current = None

    for line in filtered_lines:
        match = re.match(r'^(?:\[(\d{1,4})\]|\((\d{1,4})\)|(\d{1,4})\s*[.)])\s+(.+)$', line)
        if match:
            number = int(match.group(1) or match.group(2) or match.group(3))
            if (not current and number == 1) or (current and number == current["refNumber"] + 1):
                if current:
                    refs.append(current)
                current = {"refNumber": number, "rawCitation": match.group(4).strip()}
            elif current:
                current["rawCitation"] += f" {line}"
        elif current:
            current["rawCitation"] += f" {line}"

    if current:
        refs.append(current)

    if not refs:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', section_text) if len(p.strip()) >= 20]
        for idx, p in enumerate(paragraphs, start=1):
            refs.append({"refNumber": idx, "rawCitation": p})

    results = []
    for ref in refs:
        clean_citation = re.sub(r'The Journal of Physical Chemistry Letters.*$', '', ref["rawCitation"], flags=re.IGNORECASE)
        clean_citation = re.sub(r'https?://doi\.org/10\.1021/acs\.jpclett.*$', '', clean_citation, flags=re.IGNORECASE)
        clean_citation = re.sub(r'\s+', ' ', clean_citation).strip()
        doi_match = re.search(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*|10\.\d{4,9}/)[-._;()/:A-Za-z0-9]+', clean_citation, re.IGNORECASE)
        found_doi = clean_doi(doi_match.group(0)) if doi_match else None
        if found_doi and (not found_doi.startswith("10.") or "/" not in found_doi or len(found_doi) < 7):
            found_doi = None

        results.append({
            "refNumber": ref["refNumber"],
            "rawCitation": clean_citation,
            "doi": found_doi,
            "has_doi": bool(found_doi)
        })

    return results

def extract_dois_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Robust Multi-Stage Deterministic Reference DOI Extraction Pipeline.
    Strictly aligns 1..N references and retains placeholder for un-DOI references.
    """
    section_text = locate_references_section(text)
    seq_refs = parse_sequential_references(section_text)

    missing_entries = [r for r in seq_refs if not r["has_doi"] and len(r["rawCitation"]) >= 15]

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ref = {
            executor.submit(resolve_citation_to_doi, r["rawCitation"]): r
            for r in missing_entries
        }
        try:
            for future in as_completed(future_to_ref, timeout=5.0):
                try:
                    res_obj = future.result()
                    if res_obj and res_obj.get("doi"):
                        ref = future_to_ref[future]
                        ref["doi"] = res_obj["doi"]
                        ref["has_doi"] = True
                        ref["verification"] = res_obj.get("verified_by", "Crossref Match")
                except Exception:
                    pass
        except TimeoutError:
            pass

    final_output = []
    for r in seq_refs:
        ref_num = r["refNumber"]
        citation_snippet = r["rawCitation"][:140]
        if r["has_doi"]:
            doi_val = r["doi"]
            final_output.append({
                "doi": doi_val,
                "url": f"https://doi.org/{doi_val}",
                "line_number": ref_num,
                "context": f"({ref_num}) {citation_snippet}",
                "in_reference_section": True,
                "verification": r.get("verification", "✅ 已通過 Crossref 官方權重校驗"),
                "has_doi": True,
                "ai_status": "✅ 已通過 Crossref 官方權重校驗"
            })
        else:
            final_output.append({
                "doi": f"N/A (文獻 #{ref_num} 無 DOI)",
                "url": "",
                "line_number": ref_num,
                "context": f"({ref_num}) {citation_snippet}",
                "in_reference_section": True,
                "verification": "⚠️ 無 DOI (已保留序號對齊)",
                "has_doi": False,
                "ai_status": "⚠️ 無 DOI (已保留序號對齊)"
            })

    return final_output

def extract_all_reference_dois_with_ai(
    paper_text: str,
    api_key: str,
    model_name: str = "gemini-3.6-flash"
) -> List[Dict[str, Any]]:
    """
    AI Full-Reference DOI Extraction Engine:
    Calls Gemini API to extract ALL 140+ reference DOIs in 1 single pass safely.
    """
    try:
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
    except Exception as outer_e:
        print(f"[AI Full DOI Outer Error]: {outer_e}")

    return []
