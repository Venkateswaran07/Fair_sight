import os
import json
import re
import pandas as pd
from typing import Dict

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.oauth2 import service_account

# ── Simple in-memory cache ──────────────────────────────────────────────────
_mapping_cache: Dict[str, Dict[str, str]] = {}

_MODEL = "gemini-1.5-flash"
_PROJECT_ID = "fairsight-494322"
_LOCATION = "us-central1"

_SYSTEM_PROMPT = """
You are a data schema expert. Your job is to analyze CSV column headers and sample data,
then map them to these standard FairSight column names:

- ground_truth : The actual/real outcome (e.g. was the person actually hired, selected, approved)
- prediction   : The AI/model's predicted outcome or decision (e.g. model score, hired-by-expert)
- gender       : Gender or sex of the person
- age          : Age of the person
- race         : Race or ethnicity of the person

Format:
Return a JSON object where the KEY is the original CSV header and the VALUE is the standard FairSight name.
Example: {"Hired": "ground_truth", "Sex": "gender"}

Rules:
1. Only map columns you are CONFIDENT about.
2. Do NOT map the same column twice.
3. Return ONLY a valid JSON object. No explanation, no markdown, no code blocks.
4. If you cannot identify a column for a standard name, leave it out of the JSON.
"""

def _get_model():
    key_path = "service-account.json"
    if os.path.exists(key_path):
        credentials = service_account.Credentials.from_service_account_file(key_path)
        vertexai.init(project=_PROJECT_ID, location=_LOCATION, credentials=credentials)
    else:
        vertexai.init(project=_PROJECT_ID, location=_LOCATION)
        
    return GenerativeModel(_MODEL)

def ai_discover_column_mapping(df: pd.DataFrame) -> Dict[str, str]:
    global _mapping_cache
    headers = df.columns.tolist()

    # Cache check
    cache_key = "|".join(sorted(headers))
    if cache_key in _mapping_cache:
        return _mapping_cache[cache_key]

    sample_rows = df.head(5).to_dict(orient="records")
    prompt = f"""{_SYSTEM_PROMPT}

Headers: {headers}
Sample Rows: {json.dumps(sample_rows, indent=2, default=str)}

Return the JSON mapping in the format {{ "original_header": "standard_name" }}:"""

    try:
        model = _get_model()
        config = GenerationConfig(temperature=0.1, max_output_tokens=512)
        
        response = model.generate_content(
            prompt,
            generation_config=config
        )
        
        raw_text = response.text.strip()
        clean = re.sub(r"```(?:json)?", "", raw_text).strip().strip("`").strip()
        mapping = json.loads(clean)
        
        allowed = {"ground_truth", "prediction", "gender", "age", "race"}
        validated = {k: v for k, v in mapping.items() if v in allowed and k in headers}
        
        _mapping_cache[cache_key] = validated
        return validated
    except Exception as e:
        print(f"[DiscoveryService] Vertex AI mapping failed: {e}")
        return {}
