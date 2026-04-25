import os
from typing import Any, Dict, List

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.oauth2 import service_account

_MODEL = "gemini-2.0-flash-001"
_PROJECT_ID = "fairsight-494322"
_LOCATION = "us-central1"

def _format_features(top_features: List[Dict[str, Any]]) -> str:
    lines = []
    for f in top_features:
        direction = "↑ toward approval" if f.get("shap_value", 0) >= 0 else "↓ toward rejection"
        lines.append(f"  • {f['feature']}: SHAP={f.get('shap_value', 'N/A'):+.4f} ({direction})")
    return "\n".join(lines) if lines else "  (no features)"

def _system_prompt(audience: str) -> str:
    prompts = {
        "hr_manager": "You are a fair hiring advisor. Explain decisions simply without jargon. Highlight proxy bias if present.",
        "developer": "You are a senior ML engineer. Be technical about SHAP values and fairness metrics.",
        "executive": "You are a risk advisor. Write exactly two sentences: risk summary and recommended action."
    }
    return prompts.get(audience, "Explain this decision in plain language.")

class GeminiExplainService:
    def __init__(self):
        key_path = "service-account.json"
        if os.path.exists(key_path):
            credentials = service_account.Credentials.from_service_account_file(key_path)
            vertexai.init(project=_PROJECT_ID, location=_LOCATION, credentials=credentials)
        else:
            vertexai.init(project=_PROJECT_ID, location=_LOCATION)
        
        self.model = GenerativeModel(_MODEL)

    def explain(self, decision: str, top_features: List[Dict[str, Any]], proxy_flags: List[str], counterfactuals: List[str], audience: str) -> str:
        system = _system_prompt(audience)
        features = _format_features(top_features)
        
        prompt = f"{system}\n\nDecision: {decision}\nTop Features:\n{features}\nProxies: {', '.join(proxy_flags)}\n\nExplain for {audience}:"

        try:
            config = GenerationConfig(temperature=0.7, max_output_tokens=1024)
            response = self.model.generate_content(prompt, generation_config=config)
            return response.text.strip() if response.text else "No explanation generated."
        except Exception as e:
            print(f"[ExplainService] Vertex AI error: {e}")
            return f"Decision was {decision}. Key factors: {', '.join([f['feature'] for f in top_features[:2]])}"
