import re
import json
import os
import base64
import requests
from typing import List, Dict, Any, Optional, Tuple, Union

COLUMN_KEYS = [
    "ref_id", "sam_material", "smiles", "nio2",
    "ethanol", "toluene", "ipa", "thf", "chlorobenzene", "methoxyethanol_2", "ch2cl2",
    "concentration", "wash", "energy_e",
    "cs", "fa", "ma", "pb", "sn", "i", "br", "cl",
    "c60", "bcp", "pc60bm", "pcbm", "pc61bm", "peai", "ald_sno2",
    "pce", "reference_doi", "ref_author", "ref_journal", "data_status", "notes"
]

KNOWN_SAM_SMILES = {
    "2PACz": "c1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "MeO-2PACz": "COc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "Me-2PACz": "Cc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "MeO-4PACz": "COc1ccc2c(c1)c3ccccc3n2CCCCP(=O)(O)O",
    "Me-4PACz": "Cc1ccc2c(c1)c3ccccc3n2CCCCP(=O)(O)O",
    "2PAC": "c1ccc2c(c1)c3ccccc3n2CCP(=O)(O)O",
    "3PACz": "c1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "4PACz": "c1ccc2c(c1)c3ccccc3n2CCCCP(=O)(O)O",
    "Br-2PACz": "Brc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "Cl-2PACz": "Clc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "E-2PACz": "C=CC(=O)Oc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "MPACz": "Cc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "Ph-2PACz": "c1ccc(cc1)c2ccc3c(c2)c4ccccc4n3CCCP(=O)(O)O",
    "tBu-2PACz": "CC(C)(C)c1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "V1036": "COc1ccc(cc1)N(c2ccc(OC)cc2)c3ccc(cc3)P(=O)(O)O",
}

SYSTEM_PROMPT = """
你是鈣鈦礦太陽能電池 SAM（自組裝單分子層）全量數據擷取專家。
請閱讀整篇論文（包含正文敘述、實驗章節 Experimental Methods、補充資訊 SI、表格與腳註），擷取內文與表格中【所有】符合 p-i-n (inverted) 結構單接面電池的 SAM 數據點。

核心原則（跨段落跨章節資訊整合）：
1. 論文的 Summary Table 通常只寫了分子名稱與 PCE，但該分子的【化學 SMILES 結構式】、【沖洗步驟 wash】、【使用溶劑 (ethanol/toluene/IPA...)】、【調配濃度 (concentration)】、【能階 E】與【鈣鈦礦 A/B/X-site 組成 (Cs/FA/MA/Pb/Sn/I/Br/Cl)】通常散落在正文敘述、實驗方法與腳註中！
2. 請務必閱讀整篇論文的正文與實驗描述，將散落於正文的製程與元件條件與數據點結合，為【每一個數據點】完整補齊 35 個欄位！切勿單純抄錄表格而留下大量空白。
3. 只有當論文正文、實驗方法與表格確實皆未載明時，該欄位才填空字串 ""，並在 Data_status 標明 "缺:欄位名"。
4. 標色規則：正文/表格文字抄錄為白（""）；讀圖或邏輯推論為紅（"red"）；無法讀取缺失為黑（"black"）。

請回傳純 JSON 陣列（JSON Array）：
[
  {
    "ref_id": "1-MeO-2PACz(champion)",
    "sam_material": "MeO-2PACz",
    "smiles": "COc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
    "nio2": 0,
    "ethanol": 1,
    "toluene": 0,
    "ipa": 0,
    "thf": 0,
    "chlorobenzene": 0,
    "methoxyethanol_2": 0,
    "ch2cl2": 0,
    "concentration": 0.5,
    "wash": 1,
    "energy_e": 0.25,
    "cs": 0.05,
    "fa": 0.90,
    "ma": 0.05,
    "pb": 1.0,
    "sn": 0.0,
    "i": 0.95,
    "br": 0.05,
    "cl": 0.0,
    "c60": 1,
    "bcp": 1,
    "pc60bm": 0,
    "pcbm": 0,
    "pc61bm": 0,
    "peai": 0,
    "ald_sno2": 0,
    "pce": 22.8,
    "reference_doi": "10.1016/j.nanoen.2023.108210",
    "ref_author": "Ullah et al.",
    "ref_journal": "Nano Energy",
    "data_status": "完整(全文)",
    "notes": "",
    "confidence_colors": {
      "energy_e": "red"
    }
  }
]
"""

def extract_sam_data_with_gemini(markdown_text: str, api_key: str, model_name: str = "gemini-3.6-flash", images_base64: List[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Extract SAM data using Google Gemini API and collect token usage metadata."""
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    prompt = SYSTEM_PROMPT + f"\n\n論文 100% 全文內容：\n{markdown_text}"
    contents = [prompt]
    
    if images_base64:
        for img_b64 in images_base64[:3]:
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
            img_data = base64.b64decode(img_b64)
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))

    candidate_models = [model_name, "gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite", "gemini-2.0-flash", "gemini-flash-latest"]
    
    last_error = None
    for target_m in candidate_models:
        if not target_m:
            continue
        try:
            print(f"[Gemini API] Calling model: {target_m} with 100% full paper text ({len(markdown_text)} chars)...")
            response = client.models.generate_content(
                model=target_m,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            parsed = json.loads(response.text)

            # Collect token usage
            usage_info = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "model_used": target_m,
                "provider": "google-gemini"
            }
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_info["input_tokens"] = getattr(response.usage_metadata, 'prompt_token_count', 0)
                usage_info["output_tokens"] = getattr(response.usage_metadata, 'candidates_token_count', 0)
                usage_info["total_tokens"] = getattr(response.usage_metadata, 'total_token_count', 0)

            if isinstance(parsed, list):
                print(f"[Gemini API] Success with model {target_m}! Extracted {len(parsed)} items. Tokens: {usage_info}")
                return parsed, usage_info
            elif isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        return v, usage_info
        except Exception as e:
            print(f"[Gemini API] Model {target_m} failed: {e}")
            last_error = e

    raise RuntimeError(f"Gemini API 呼叫失敗: {last_error}")

def extract_sam_data_with_openai_compatible(
    markdown_text: str,
    api_key: str,
    model_name: str = "gpt-4o-mini",
    api_base: str = "https://api.openai.com/v1"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Extract SAM data using OpenAI-compatible API and collect token usage metadata."""
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    user_content = f"{SYSTEM_PROMPT}\n\n論文 100% 全文內容：\n{markdown_text}"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"} if "gpt-4" in model_name or "deepseek" in model_name else None
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    if resp.status_code == 200:
        res_json = resp.json()
        content = res_json['choices'][0]['message']['content']
        content_clean = re.sub(r'^```json\s*', '', content.strip(), flags=re.IGNORECASE)
        content_clean = re.sub(r'\s*```$', '', content_clean).strip()
        
        usage = res_json.get('usage', {})
        usage_info = {
            "input_tokens": usage.get('prompt_tokens', 0),
            "output_tokens": usage.get('completion_tokens', 0),
            "total_tokens": usage.get('total_tokens', 0),
            "model_used": model_name,
            "provider": "openai-compatible"
        }

        parsed = json.loads(content_clean)
        if isinstance(parsed, list):
            return parsed, usage_info
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v, usage_info
    else:
        raise RuntimeError(f"OpenAI 相容 API 錯誤 ({resp.status_code}): {resp.text[:200]}")

    raise RuntimeError("無法解析模型 JSON 回傳。")

def parse_markdown_tables(markdown_text: str) -> List[Dict[str, Any]]:
    extracted_rows = []
    lines = markdown_text.split('\n')
    
    in_table = False
    table_lines = []
    
    for line in lines:
        line_str = line.strip()
        if line_str.startswith('|') and line_str.endswith('|'):
            if not in_table:
                in_table = True
                table_lines = [line_str]
            else:
                table_lines.append(line_str)
        else:
            if in_table:
                in_table = False
                if len(table_lines) >= 3:
                    rows = process_single_markdown_table(table_lines)
                    extracted_rows.extend(rows)
                table_lines = []

    if in_table and len(table_lines) >= 3:
        rows = process_single_markdown_table(table_lines)
        extracted_rows.extend(rows)

    return extracted_rows

def process_single_markdown_table(table_lines: List[str]) -> List[Dict[str, Any]]:
    results = []
    raw_headers = [c.strip() for c in table_lines[0].strip('|').split('|')]
    
    sam_col_idx = -1
    pce_col_idx = -1
    doi_col_idx = -1
    stack_col_idx = -1
    
    for idx, h in enumerate(raw_headers):
        h_lower = h.lower()
        if any(k in h_lower for k in ['sam', 'htl', 'molecule', 'material', '層']):
            sam_col_idx = idx
        elif any(k in h_lower for k in ['pce', 'efficiency', '效能', '%']):
            pce_col_idx = idx
        elif any(k in h_lower for k in ['ref', 'doi', 'reference']):
            doi_col_idx = idx
        elif any(k in h_lower for k in ['stack', 'structure', '基板', '層結構']):
            stack_col_idx = idx

    for r_idx, row_line in enumerate(table_lines[2:], start=1):
        cols = [c.strip() for c in row_line.strip('|').split('|')]
        if len(cols) < len(raw_headers):
            continue

        sam_name = cols[sam_col_idx] if sam_col_idx != -1 and sam_col_idx < len(cols) else ""
        pce_str = cols[pce_col_idx] if pce_col_idx != -1 and pce_col_idx < len(cols) else ""
        doi_str = cols[doi_col_idx] if doi_col_idx != -1 and doi_col_idx < len(cols) else ""
        stack_str = cols[stack_col_idx] if stack_col_idx != -1 and stack_col_idx < len(cols) else ""

        sam_name = re.sub(r'\[\d+\]', '', sam_name).strip()
        if not sam_name or len(sam_name) < 2 or sam_name.lower() in ['material', 'sam', 'htl', 'none', 'molecule']:
            continue

        pce_match = re.search(r'([12]?\d\.\d{1,2})', pce_str)
        pce_val = float(pce_match.group(1)) if pce_match else ""

        doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', doi_str + ' ' + row_line)
        doi_val = ""
        if doi_match:
            raw_doi = doi_match.group(0)
            doi_val = re.sub(r'[.,;:\)\>\]\'"\s]+$', '', raw_doi).strip()

        smiles_val = KNOWN_SAM_SMILES.get(sam_name, "")

        missing_fields = []
        if not pce_val: missing_fields.append("PCE")
        if not doi_val: missing_fields.append("Reference_DOI")

        status_str = "完整(表格)" if not missing_fields else f"表格部分；缺:{','.join(missing_fields)}"

        row = {
            "ref_id": f"Table-{r_idx}-{sam_name}",
            "sam_material": sam_name,
            "smiles": smiles_val,
            "nio2": 1 if 'niox' in (stack_str + sam_name).lower() else 0,
            "ethanol": 0, "toluene": 0, "ipa": 0, "thf": 0, "chlorobenzene": 0, "methoxyethanol_2": 0, "ch2cl2": 0,
            "concentration": "",
            "wash": "",
            "energy_e": "",
            "cs": "", "fa": "", "ma": "", "pb": "", "sn": "", "i": "", "br": "", "cl": "",
            "c60": 1 if 'c60' in stack_str.lower() else 0,
            "bcp": 1 if 'bcp' in stack_str.lower() else 0,
            "pc60bm": 0, "pcbm": 0, "pc61bm": 0, "peai": 0, "ald_sno2": 0,
            "pce": pce_val,
            "reference_doi": doi_val,
            "ref_author": "",
            "ref_journal": "",
            "data_status": status_str,
            "notes": f"抄錄自表格 (第{r_idx}列)" if doi_val else f"抄錄自表格 (第{r_idx}列)；無明示對應 DOI",
            "confidence_colors": {}
        }
        results.append(row)

    return results

def extract_sam_data_rule_based(markdown_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Strict rule-based parser without fake default numbers or duplicated main DOIs."""
    results = []
    
    table_results = parse_markdown_tables(markdown_text)
    if table_results:
        results.extend(table_results)

    if not results:
        sam_candidates = []
        for mol in KNOWN_SAM_SMILES.keys():
            if re.search(r'\b' + re.escape(mol) + r'\b', markdown_text, re.IGNORECASE):
                sam_candidates.append(mol)

        for idx, sam_name in enumerate(sam_candidates, start=1):
            smiles_val = KNOWN_SAM_SMILES.get(sam_name, "")
            
            pce_val = ""
            pce_match = re.search(re.escape(sam_name) + r'[\s\S]{0,100}?(?:PCE|efficiency)\s*(?:of|=|~|:)?\s*([12]?\d\.\d{1,2})\s*%', markdown_text, re.IGNORECASE)
            if pce_match:
                pce_val = float(pce_match.group(1))

            row = {
                "ref_id": f"Text-{idx}-{sam_name}",
                "sam_material": sam_name,
                "smiles": smiles_val,
                "nio2": 0, "ethanol": 0, "toluene": 0, "ipa": 0, "thf": 0, "chlorobenzene": 0, "methoxyethanol_2": 0, "ch2cl2": 0,
                "concentration": "",
                "wash": "",
                "energy_e": "",
                "cs": "", "fa": "", "ma": "", "pb": "", "sn": "", "i": "", "br": "", "cl": "",
                "c60": 0, "bcp": 0, "pc60bm": 0, "pcbm": 0, "pc61bm": 0, "peai": 0, "ald_sno2": 0,
                "pce": pce_val,
                "reference_doi": "",
                "ref_author": "",
                "ref_journal": "",
                "data_status": "內文擷取；缺:製程,E,DOI",
                "notes": "未填 API Key 走嚴格規則模式；未明示欄位均留空",
                "confidence_colors": {}
            }
            results.append(row)

    usage_info = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "model_used": "Rule-based Engine (No API Key)",
        "provider": "local"
    }

    return results, usage_info

def process_paper_markdown(
    markdown_text: str,
    api_key: Optional[str] = None,
    images_base64: List[str] = None,
    provider: str = "gemini",
    model_name: str = "gemini-3.6-flash",
    api_base: str = "https://api.openai.com/v1",
    return_usage: bool = False
) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    """Main extraction router supporting Gemini, OpenAI, DeepSeek, Ollama, OpenRouter, and Custom APIs."""
    if api_key and api_key.strip():
        if provider == "openai" or provider == "deepseek" or provider == "custom":
            base_url = api_base if api_base and api_base.strip() else ("https://api.deepseek.com/v1" if provider == "deepseek" else "https://api.openai.com/v1")
            target_model = model_name if model_name and model_name.strip() else ("deepseek-chat" if provider == "deepseek" else "gpt-4o-mini")
            data_rows, usage_info = extract_sam_data_with_openai_compatible(markdown_text, api_key.strip(), target_model, base_url)
        else:
            target_model = model_name.strip() if model_name and model_name.strip() else "gemini-3.6-flash"
            data_rows, usage_info = extract_sam_data_with_gemini(markdown_text, api_key.strip(), target_model, images_base64)
    else:
        data_rows, usage_info = extract_sam_data_rule_based(markdown_text)

    if return_usage:
        return data_rows, usage_info
    return data_rows
