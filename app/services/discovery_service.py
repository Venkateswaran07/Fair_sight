"""
DiscoveryService — AI-powered CSV column schema detection.

When standard regex mapping cannot identify required columns like
'ground_truth' and 'prediction', this service sends the CSV headers
and sample rows to Gemini and asks it to identify the correct mapping.

Caching: Results are cached by column fingerprint so Gemini is only
called ONCE per unique column structure, preventing rate limit errors.
"""

import os
import json
import re
import pandas as pd
from typing import Dict

import google.generativeai as genai

# ── Simple in-memory cache: column_fingerprint -> mapping dict ──────────────
_mapping_cache: Dict[str, Dict[str, str]] = {}

_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = """
You are a data schema expert. Your job is to analyze CSV column headers and sample data,
then map them to these standard FairSight column names:

- ground_truth : The actual/real outcome (e.g. was the person actually hired, selected, approved)
- prediction   : The AI/model's predicted outcome or decision (e.g. model score, hired-by-expert)
- gender       : Gender or sex of the person
- age          : Age of the person
- race         : Race or ethnicity of the person

Rules:
1. Only map columns you are CONFIDENT about.
2. Do NOT map the same column twice.
3. Return ONLY a valid JSON object. No explanation, no markdown, no code blocks.
4. If you cannot identify a column for a standard name, leave it out of the JSON.

Example output format:
{"original_col_name": "ground_truth", "another_col": "prediction", "sex_col": "gender"}
"""


def _call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(_MODEL)
    config = genai.types.GenerationConfig(temperature=0.1, max_output_tokens=512)
    response = model.generate_content(prompt, generation_config=config)
    return response.text.strip() if response.text else ""


def ai_discover_column_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """
    Ask Gemini to analyze the CSV headers and sample rows,
    returning a dict mapping original column names -> standard FairSight names.
    Results are cached by column fingerprint to avoid repeated API calls.
    Falls back to empty dict on any error.
    """
    global _mapping_cache
    headers = df.columns.tolist()

    # ── Cache check ──────────────────────────────────────────────────────────
    cache_key = "|".join(sorted(headers))
    if cache_key in _mapping_cache:
        print(f"[DiscoveryService] Cache hit — skipping Gemini call.")
        return _mapping_cache[cache_key]

    # Send first 5 rows as context so Gemini can see the actual data values
    sample_rows = df.head(5).to_dict(orient="records")

    prompt = f"""{_SYSTEM_PROMPT}

Here are the CSV column headers:
{headers}

Here are 5 sample rows from the data:
{json.dumps(sample_rows, indent=2, default=str)}

Now return the JSON mapping of original column names to FairSight standard names.
"""

    try:
        raw_response = _call_gemini(prompt)
        clean = re.sub(r"```(?:json)?", "", raw_response).strip().strip("`").strip()
        mapping = json.loads(clean)
        allowed = {"ground_truth", "prediction", "gender", "age", "race"}
        validated = {k: v for k, v in mapping.items() if v in allowed and k in headers}
        # Only cache successful results so quota errors trigger a retry next time
        _mapping_cache[cache_key] = validated
        return validated
    except Exception as e:
        print(f"[DiscoveryService] AI mapping failed (falling back to regex): {e}")
        return {}  # Do NOT cache failures — allow retry on next request

