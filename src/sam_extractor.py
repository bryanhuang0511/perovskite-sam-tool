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
你是鈣鈦礦太陽能電池 SAM（自組裝單分子層）全量數據與 Reference DOI 擷取專家。

【⚠️ 最高權限獨立記憶清除指令】：
你必須【100% 僅根據當前輸入的這篇論文全文內容】進行數據提取。
每一篇論文都是完全獨立且無狀態的。嚴禁引用、回憶或混入任何過去處理過的論文、已知記憶或歷史 context。如果當前論文內沒有提及某項數據，必須填寫 0 或留空，絕不能拿歷史記憶來填補！

請閱讀整篇論文（包含正文敘述、實驗章節 Experimental Methods、補充資訊 SI、表格、腳註與文末 References 參考文獻章節）。

請回傳一個包含 `sam_dataset` 陣列與 `reference_dois` 陣列的 JSON 物件：

{
  "sam_dataset": [
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
  ],
  "reference_dois": [
    {
      "doi": "10.1016/j.nanoen.2023.108210",
      "context": "(1) Ullah et al., Nano Energy 2023"
    }
  ]
}

核心原則：
1. 擷取【當前論文】內文與表格中【所有】符合 p-i-n (inverted) 結構單接面電池的 SAM 數據點。
2. 跨段落整合正文、實驗方法與表格，為每一個數據點完整補齊 35 個欄位。
3. 在 `reference_dois` 陣列中，請列出【當前論文】文末 References 參考文獻章節中【所有】引用文獻的 DOI 號碼（純文字 10.xxxx/xxxx 格式）。
"""

def extract_sam_data_with_gemini(markdown_text: str, api_key: str, model_name: str = "gemini-3.6-flash", images_base64: List[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract SAM dataset & Reference DOIs using Google Gemini API with stateless guarantee."""
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    prompt = SYSTEM_PROMPT + f"\n\n【當前獨立論文 100% 全文內容】：\n{markdown_text}"
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
                    temperature=0.0,  # 0.0 temperature for deterministic & 0-memory response!
                ),
            )
            parsed = json.loads(response.text)

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

            if isinstance(parsed, dict):
                return parsed, usage_info
            elif isinstance(parsed, list):
                return {"sam_dataset": parsed, "reference_dois": []}, usage_info
        except Exception as e:
            print(f"[Gemini API] Model {target_m} failed: {e}")
            last_error = e

    raise RuntimeError(f"Gemini API 呼叫失敗: {last_error}")

def extract_sam_data_with_openai_compatible(
    markdown_text: str,
    api_key: str,
    model_name: str = "gpt-4o-mini",
    api_base: str = "https://api.openai.com/v1"
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract SAM dataset & Reference DOIs using OpenAI-compatible API with stateless guarantee."""
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    user_content = f"{SYSTEM_PROMPT}\n\n【當前獨立論文 100% 全文內容】：\n{markdown_text}"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
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
        if isinstance(parsed, dict):
            return parsed, usage_info
        elif isinstance(parsed, list):
            return {"sam_dataset": parsed, "reference_dois": []}, usage_info
    else:
        raise RuntimeError(f"OpenAI 相容 API 錯誤 ({resp.status_code}): {resp.text[:200]}")

    raise RuntimeError("無法解析模型 JSON 回傳。")

def process_paper_markdown(
    markdown_text: str,
    api_key: Optional[str] = None,
    images_base64: List[str] = None,
    provider: str = "gemini",
    model_name: str = "gemini-3.6-flash",
    api_base: str = "https://api.openai.com/v1",
    return_usage: bool = False
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Main extraction router returning sam_dataset and reference_dois."""
    if api_key and api_key.strip():
        if provider == "openai" or provider == "deepseek" or provider == "custom":
            base_url = api_base if api_base and api_base.strip() else ("https://api.deepseek.com/v1" if provider == "deepseek" else "https://api.openai.com/v1")
            target_model = model_name if model_name and model_name.strip() else ("deepseek-chat" if provider == "deepseek" else "gpt-4o-mini")
            res_dict, usage_info = extract_sam_data_with_openai_compatible(markdown_text, api_key.strip(), target_model, base_url)
        else:
            target_model = model_name.strip() if model_name and model_name.strip() else "gemini-3.6-flash"
            res_dict, usage_info = extract_sam_data_with_gemini(markdown_text, api_key.strip(), target_model, images_base64)
    else:
        res_dict = {"sam_dataset": [], "reference_dois": []}
        usage_info = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "model_used": "local", "provider": "rule-based"}

    if return_usage:
        return res_dict, usage_info
    return res_dict
