import os
from typing import Any, Dict, List

from google import genai
from google.genai import types

_MODEL = "gemini-2.0-flash"

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
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not found in environment variables.")
        
        # Using the modern google-genai client
        self.client = genai.Client(api_key=api_key)

    def explain(self, decision: str, top_features: List[Dict[str, Any]], proxy_flags: List[str], counterfactuals: List[str], audience: str) -> str:
        system = _system_prompt(audience)
        features = _format_features(top_features)
        
        prompt = (
            f"{system}\n\n"
            f"CONTEXT: This is an AI model decision auditing tool.\n"
            f"Decision: {decision}\n"
            f"Top Features (SHAP values):\n{features}\n"
            f"Potential Proxies Detected: {', '.join(proxy_flags) if proxy_flags else 'None'}\n"
            f"Counterfactual Scenarios: {'; '.join(counterfactuals) if counterfactuals else 'N/A'}\n\n"
            f"Please explain this decision for the {audience} audience:"
        )

        try:
            # Modern SDK call
            response = self.client.models.generate_content(
                model=_MODEL,
                contents=prompt
            )
            return response.text.strip() if response.text else "No explanation generated."
        except Exception as e:
            print(f"[ExplainService] Gemini API error: {e}")
            
            # Smart Fallback: Generate a rule-based explanation if API is down
            primary_feature = top_features[0]['feature'] if top_features else "Unknown"
            direction = "positive" if top_features and top_features[0].get("shap_value", 0) >= 0 else "negative"
            
            fallback_text = (
                f"The model predicted '{decision}'. This was primarily driven by {primary_feature}, "
                f"which had a {direction} impact on the outcome. "
            )
            
            if proxy_flags:
                fallback_text += f"Note: Potential bias detected via proxy features: {', '.join(proxy_flags)}."
            
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                return f"{fallback_text} (Note: Detailed AI explanation is currently unavailable due to API quota limits.)"
            
            return f"{fallback_text} (AI Service error: {err_msg[:30]}...)"
