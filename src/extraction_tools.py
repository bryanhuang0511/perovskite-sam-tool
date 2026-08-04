"""Agentic Tools Module for Perovskite SAM Extractor.

Provides tool-calling & post-processing verification capabilities:
1. SMILES validation & canonicalization (via RDKit or fallback).
2. SAM name to SMILES resolution (via Known SAM dict & PubChem PUG REST API).
3. Perovskite stoichiometry normalization (Fable 5 rule engine: Cs + FA + MA = 1.0).
4. Confidence color grading & notes generator (white / red / black).
"""
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("extraction_tools")

# Optional RDKit import
try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

# Known SAM dictionary for instant resolution
KNOWN_SAM_SMILES: Dict[str, str] = {
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


def validate_and_fix_smiles(smiles: str) -> Dict[str, Any]:
    """Validate SMILES string using RDKit if available, returning canonical form or error details."""
    if not smiles or not isinstance(smiles, str) or not smiles.strip():
        return {"valid": False, "canonical_smiles": "", "error": "Empty SMILES"}
    
    clean_smiles = smiles.strip()
    
    if HAS_RDKIT:
        try:
            mol = Chem.MolFromSmiles(clean_smiles)
            if mol is not None:
                canonical = Chem.MolToSmiles(mol, canonical=True)
                return {
                    "valid": True,
                    "canonical_smiles": canonical,
                    "error": "",
                    "rdkit_verified": True
                }
            else:
                return {
                    "valid": False,
                    "canonical_smiles": clean_smiles,
                    "error": "RDKit MolFromSmiles parsing failed",
                    "rdkit_verified": True
                }
        except Exception as e:
            return {
                "valid": False,
                "canonical_smiles": clean_smiles,
                "error": f"RDKit exception: {str(e)}",
                "rdkit_verified": True
            }
    else:
        # Robust heuristic fallback check when RDKit package is absent
        has_elements = bool(re.search(r'[CcnNoOpPsS]', clean_smiles))
        has_invalid_chars = bool(re.search(r'[^A-Za-z0-9@+\-\[\]\(\)\\/\=#%:.]', clean_smiles))
        has_words = bool(re.search(r'[A-Za-z]{6,}', clean_smiles))  # SMILES strings rarely have 6+ consecutive letters
        is_basic_valid = has_elements and not has_invalid_chars and not has_words
        return {
            "valid": is_basic_valid,
            "canonical_smiles": clean_smiles,
            "error": "" if is_basic_valid else "Basic SMILES syntax check failed",
            "rdkit_verified": False
        }



def lookup_sam_smiles_by_name(sam_name: str) -> Optional[str]:
    """Look up SMILES by SAM abbreviation using local dictionary and PubChem API fallback."""
    if not sam_name or not isinstance(sam_name, str):
        return None
    
    name_clean = sam_name.strip()
    
    # 1. Check Known SAM dictionary (exact match or case-insensitive)
    for known_name, known_smiles in KNOWN_SAM_SMILES.items():
        if known_name.lower() == name_clean.lower():
            return known_smiles
            
    # 2. Try PubChem PUG REST API query if network is available
    try:
        import requests
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name_clean}/property/CanonicalSMILES/JSON"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            properties = data.get("PropertyTable", {}).get("Properties", [])
            if properties and "CanonicalSMILES" in properties[0]:
                return properties[0]["CanonicalSMILES"]
    except Exception as e:
        logger.debug(f"PubChem lookup failed for {sam_name}: {e}")
        
    return None


def normalize_perovskite_composition(record: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
    """Apply Fable 5 stoichiometry normalization rules for A-site cations (Cs + FA + MA = 1.0)."""
    notes_added = []
    
    try:
        cs = float(record.get("cs", 0) or 0)
        fa = float(record.get("fa", 0) or 0)
        ma = float(record.get("ma", 0) or 0)
    except (ValueError, TypeError):
        return record, notes_added
        
    total_a = cs + fa + ma
    
    # If A-site cations exist and sum is not 1.0 (e.g. 1.05 or 0.95), normalize to 1.0
    if total_a > 0 and abs(total_a - 1.0) > 0.001:
        norm_cs = round(cs / total_a, 4)
        norm_fa = round(fa / total_a, 4)
        norm_ma = round(ma / total_a, 4)
        
        record["cs"] = norm_cs
        record["fa"] = norm_fa
        record["ma"] = norm_ma
        
        notes_added.append(f"A-site 配比歸一化 (原總和 {total_a:.3f} -> 歸一化為 1.0)")
        
    return record, notes_added


def apply_fable_confidence_rules(record: Dict[str, Any], paper_text: str = "") -> Dict[str, Any]:
    """Evaluate record parameters against Fable 5 rules and assign confidence colors & notes."""
    confidence_colors = record.get("confidence_colors", {})
    if not isinstance(confidence_colors, dict):
        confidence_colors = {}
        
    existing_notes = str(record.get("notes", "") or "").strip()
    notes_list = [existing_notes] if existing_notes else []
    
    # 1. SMILES Validation & Auto-fixing
    raw_smiles = str(record.get("smiles", "") or "").strip()
    sam_name = str(record.get("sam_material", "") or "").strip()
    
    val_res = validate_and_fix_smiles(raw_smiles)
    if val_res["valid"]:
        record["smiles"] = val_res["canonical_smiles"]
    else:
        # Try lookup by SAM name if SMILES was invalid or empty
        lookup_smiles = lookup_sam_smiles_by_name(sam_name)
        if lookup_smiles:
            record["smiles"] = lookup_smiles
            confidence_colors["smiles"] = "red"
            notes_list.append(f"SMILES 由 SAM 名稱 ({sam_name}) 自動補全")
        else:
            confidence_colors["smiles"] = "black"
            notes_list.append("SMILES 無法驗證或未提供")
            
    # 2. Perovskite Stoichiometry Normalization
    record, norm_notes = normalize_perovskite_composition(record)
    notes_list.extend(norm_notes)
    
    # 3. Wash parameter check
    wash_val = record.get("wash", None)
    if wash_val is None or wash_val == 0:
        if paper_text and ("dipping" in paper_text.lower() or "immers" in paper_text.lower()):
            record["wash"] = 1
            confidence_colors["wash"] = "red"
            notes_list.append("wash=1 (依浸泡 dipping 方法推論註記)")
            
    # 4. Energy E check
    energy_e = record.get("energy_e", None)
    if energy_e is not None and energy_e != 0:
        if "energy_e" not in confidence_colors:
            confidence_colors["energy_e"] = "red"  # Energy reading from band diagram flagged red by default
            
    record["confidence_colors"] = confidence_colors
    record["notes"] = "; ".join([n for n in notes_list if n])
    
    return record
