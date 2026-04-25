import re
from typing import Dict, Any
import pandas as pd

def normalize_string(s: str) -> str:
    """Clean up a single string to a standard, predictable format."""
    # 1. Lowercase and remove all content inside parentheses
    clean = s.lower().strip()
    clean = re.sub(r'\(.*?\)', '', clean)
    # 2. Remove any leftover parentheses or quotes
    clean = re.sub(r'[()\'"]', '', clean)
    # 3. Standardize whitespace and separators
    clean = clean.replace(' ', '_').replace('-', '_')
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean

def normalize_column_list(cols: list) -> list:
    """Normalize a list of column names for matching."""
    return [normalize_string(c) for c in cols]

def normalize_dataframe_headers(df: pd.DataFrame, fast_mode: bool = False) -> pd.DataFrame:
    """
    Universally map varied column names to standard FairSight names.
    Step 1: Fast regex/fuzzy matching.
    Step 2: If critical columns are still missing and not in fast_mode, call Gemini AI.
    """
    new_columns = {}
    
    # Mapping patterns
    mappings = {
        "ground_truth": [
            r"^ground[_ ]?truth$", r"^actual$", r"^label$", r"^target$",
            r"^suitability$", r"^should[-_]hire$", r"^outcome$", r"^y$", r"^loan[_ ]?status$"
        ],
        "prediction": [
            r"^prediction$", r"^pred$", r"^predicted$", r"^hired[-_]by[-_]expert$",
            r"^decision$", r"^selection$", r"^output$", r"^prediction_output$"
        ],
        "gender": [r"gender", r"sex", r"m[_ ]?f"],
        "age": [r"age", r"dob", r"year[_ ]?of[_ ]?birth", r"age[_ ]?group"],
        "race": [r"race", r"ethnicity"],
    }

    current_cols = df.columns.tolist()

    for col in current_cols:
        clean_col = normalize_string(col)
        found_mapped = False
        for standard_name, patterns in mappings.items():
            for pattern in patterns:
                if re.search(pattern, clean_col) or re.search(pattern, col.lower()):
                    if standard_name not in new_columns.values():
                        new_columns[col] = standard_name
                        found_mapped = True
                        break
            if found_mapped:
                break
        if not found_mapped:
            new_columns[col] = clean_col

    # ── Ensure Unique Column Names ──────────────────────────────────────────
    final_columns = []
    seen = {}
    for col in current_cols:
        candidate = new_columns.get(col, normalize_string(col))
        if candidate in seen:
            seen[candidate] += 1
            final_columns.append(f"{candidate}_{seen[candidate]}")
        else:
            seen[candidate] = 0
            final_columns.append(candidate)
    
    df.columns = final_columns

    if fast_mode:
        return df

    # ── AI Fallback ─────────────────────────────────────────────────────────
    critical = {"ground_truth", "prediction"}
    if not critical.issubset(set(df.columns)):
        try:
            from app.services.discovery_service import ai_discover_column_mapping
            original_df = df.rename(columns={v: k for k, v in new_columns.items()})
            ai_mapping = ai_discover_column_mapping(original_df)
            if ai_mapping:
                df = df.rename(columns={
                    new_columns.get(orig, normalize_string(orig)): std
                    for orig, std in ai_mapping.items()
                })
        except Exception as e:
            print(f"[SmartMapper] AI fallback error: {e}")

    # ── Last-Resort Auto-Detection ───────────────────────────────────────────
    cols = set(df.columns)
    if "ground_truth" not in cols or "prediction" not in cols:
        _auto_detect_outcome(df)

    if "ground_truth" in set(df.columns) and "prediction" not in set(df.columns):
        df["prediction"] = df["ground_truth"]

    # ── Drop Useless Identifiers ─────────────────────────────────────────────
    df = _drop_identifier_columns(df)

    return df


def _drop_identifier_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove columns that are purely unique string identifiers (Names, Addresses, IDs).
    A column is dropped if it's a string type and >90% of its values are unique.
    Exception: If it's the target 'ground_truth' or 'prediction', keep it.
    """
    cols_to_drop = []
    n_rows = len(df)
    if n_rows == 0:
        return df

    for col in df.columns:
        if col in ("ground_truth", "prediction"):
            continue
            
        # Only drop string/object columns (numeric IDs are mostly harmless, but strings break OHE)
        if df[col].dtype == 'object' or pd.api.types.is_string_dtype(df[col]):
            unique_count = df[col].nunique()
            if unique_count / n_rows > 0.90:  # > 90% unique
                cols_to_drop.append(col)

    if cols_to_drop:
        print(f"[SmartMapper] Dropping highly-unique string columns (likely IDs/Addresses): {cols_to_drop}")
        df = df.drop(columns=cols_to_drop)
        
    return df



def _auto_detect_outcome(df: pd.DataFrame) -> None:
    """
    Scan DataFrame columns for binary-valued columns (Yes/No, 0/1, True/False).
    Promote the best candidate to 'ground_truth' and 'prediction' in-place.
    Prefers columns whose name sounds like an outcome (hired, selected, approved, etc.).
    """
    binary_candidates = []
    outcome_keywords = ["attrition", "hired", "selected", "approved", "rejected",
                        "outcome", "result", "target", "label", "status", "decision",
                        "churn", "default", "fraud", "leave", "left"]

    for col in df.columns:
        if col in ("ground_truth", "prediction"):
            continue
        series = df[col].dropna()
        unique = series.unique()
        if len(unique) == 2:
            # Score by how "outcome-like" the name is
            name_lower = col.lower()
            score = sum(1 for kw in outcome_keywords if kw in name_lower)
            binary_candidates.append((score, col))

    if not binary_candidates:
        print("[SmartMapper] Could not auto-detect any binary outcome column.")
        return

    # Pick the highest-scoring candidate (most outcome-like name)
    binary_candidates.sort(key=lambda x: -x[0])
    best_col = binary_candidates[0][1]

    if "ground_truth" not in df.columns:
        df["ground_truth"] = df[best_col]
        print(f"[SmartMapper] Auto-detected '{best_col}' as ground_truth.")

    if "prediction" not in df.columns:
        df["prediction"] = df["ground_truth"]
        print(f"[SmartMapper] Using '{best_col}' as prediction (no separate prediction column found).")


def normalize_dictionary_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys in a dictionary to match standard naming conventions."""
    return {normalize_string(k): v for k, v in d.items()}

def translate_value_to_numeric(val: Any, target_series: pd.Series) -> Any:
    """
    Attempt to translate a string value (like 'male' or 'yes') 
    to match the numeric type or encoding of the target series.
    Also scrubs messy quotes and whitespace.
    """
    if not isinstance(val, str):
        return val
        
    # Scrub messy quotes and whitespace (handles strings like '" 10"' -> '10')
    clean_val = val.strip().strip('"').strip("'").strip()
    
    if not pd.api.types.is_numeric_dtype(target_series):
        return clean_val
    
    lookup_val = clean_val.lower()
    
    # Common boolean/binary mappings
    boolean_map = {
        "male": 1, "m": 1, "man": 1,
        "female": 0, "f": 0, "woman": 0,
        "yes": 1, "y": 1, "true": 1, "approved": 1,
        "no": 0, "n": 0, "false": 0, "rejected": 0
    }
    
    if lookup_val in boolean_map:
        return boolean_map[lookup_val]
        
    try:
        # Final attempt to force it to a number
        return float(clean_val)
    except (ValueError, TypeError):
        return clean_val
