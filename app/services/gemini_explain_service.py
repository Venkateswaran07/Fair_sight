"""
GeminiExplainService — LLM-powered plain-language fairness explanations.

Audience routing
----------------
hr_manager  : 2-3 sentences, zero jargon, proxy concerns called out clearly
developer   : technical tone, feature names, SHAP values, fairness metric context
executive   : exactly two sentences — risk summary + recommended action

Environment variable
--------------------
GEMINI_API_KEY  (required)  — your Google Gemini API key
GEMINI_MODEL    (optional)  — overrides the default model
"""

import os
from typing import Any, Dict, List

import google.generativeai as genai

_DEFAULT_MODEL = "gemini-2.5-flash"


# ── Prompt builders ────────────────────────────────────────────────────────

def _format_features(top_features: List[Dict[str, Any]]) -> str:
    lines = []
    for f in top_features:
        direction = "↑ toward approval" if f.get("shap_value", 0) >= 0 else "↓ toward rejection"
        lines.append(
            f"  • {f['feature']}: SHAP={f.get('shap_value', 'N/A'):+.4f}, "
            f"impact={f.get('contribution_percent', 'N/A'):.1f}% ({direction})"
        )
    return "\n".join(lines) if lines else "  (no features provided)"


def _format_proxies(proxy_flags: List[str]) -> str:
    if not proxy_flags:
        return "None detected"
    return ", ".join(proxy_flags)


def _format_counterfactuals(counterfactuals: List[str]) -> str:
    if not counterfactuals:
        return "  (none available)"
    return "\n".join(f"  {i+1}. {cf}" for i, cf in enumerate(counterfactuals))


def _system_prompt(audience: str) -> str:
    if audience == "hr_manager":
        return (
            "You are a fair hiring advisor who explains AI-assisted decisions to HR professionals. "
            "Write in plain, empathetic language. Never use technical jargon. "
            "If there are proxy bias concerns, state them simply and clearly so the HR manager "
            "can take appropriate action."
        )
    if audience == "developer":
        return (
            "You are a senior ML engineer reviewing an AI model's decision for fairness and "
            "correctness. Use technical language. Be precise about feature names, SHAP values, "
            "and what the fairness signals mean in terms of model behaviour."
        )
    if audience == "executive":
        return (
            "You are a concise risk advisor briefing a C-suite executive. "
            "Write exactly two sentences: sentence 1 is a risk summary, sentence 2 is a "
            "recommended action. No bullet points, no headings, no extra text."
        )
    return "You are a helpful AI assistant explaining a decision."


def _user_prompt(
    decision: str,
    top_features: List[Dict[str, Any]],
    proxy_flags: List[str],
    counterfactuals: List[str],
    audience: str,
) -> str:
    features_text = _format_features(top_features)
    proxies_text = _format_proxies(proxy_flags)
    cfs_text = _format_counterfactuals(counterfactuals)

    context = f"""
DECISION: {decision}

TOP FEATURES DRIVING THIS DECISION (by absolute SHAP value):
{features_text}

PROXY BIAS FLAGS (non-protected features correlated with protected attributes):
{proxies_text}

COUNTERFACTUAL SCENARIOS (what would change the outcome to APPROVED):
{cfs_text}
""".strip()

    if audience == "hr_manager":
        instruction = (
            "Explain this decision in a brief, friendly paragraph for an HR manager. "
            "Focus on being clear and helpful. Avoid all technical jargon. "
            "If proxy concerns are present, mention them simply. "
            "Crucially: Ensure the explanation is a complete thought and never ends mid-sentence."
        )
    elif audience == "developer":
        instruction = (
            "Provide a thorough technical explanation. Include feature names, SHAP values, "
            "and implications of any proxy flags. Ensure all technical points are fully concluded."
        )
    elif audience == "executive":
        instruction = (
            "Write a concise 2-sentence summary. Sentence 1: Risk level/status. "
            "Sentence 2: Recommended action. Ensure both sentences are complete."
        )
    else:
        instruction = "Explain this decision in plain language. Ensure you finish your sentences."

    return f"{context}\n\n---\n{instruction}"

def _fallback_explanation(decision: str, top_features: list, proxy_flags: list) -> str:
    """Plain-English summary built from SHAP data — used when Gemini quota is exceeded."""
    verdict = "approved" if "APPROV" in decision.upper() else "not selected"
    lines = [f"This candidate was {verdict} by the model."]
    if top_features:
        top = top_features[0]
        direction = "positively" if top.get("shap_value", 0) >= 0 else "negatively"
        lines.append(
            f"The most influential factor was '{top['feature']}', "
            f"which {direction} impacted the decision "
            f"({top.get('contribution_percent', 0):.1f}% of total influence)."
        )
    if proxy_flags:
        lines.append(
            f"Note: the following features may act as proxies for protected attributes "
            f"and should be reviewed: {', '.join(proxy_flags)}."
        )
    return " ".join(lines)


# ── Service ────────────────────────────────────────────────────────────────

class GeminiExplainService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set."
            )
        
        genai.configure(api_key=api_key)
        # Reverting to the user's preferred model that worked before
        self._model_name = "gemini-2.5-flash"

    def explain(
        self,
        decision: str,
        top_features: List[Dict[str, Any]],
        proxy_flags: List[str],
        counterfactuals: List[str],
        audience: str,
    ) -> str:
        system_instruction = _system_prompt(audience)
        user = _user_prompt(decision, top_features, proxy_flags, counterfactuals, audience)

        combined_prompt = f"{system_instruction}\n\nTask:\n{user}"

        model = genai.GenerativeModel(self._model_name)
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=2048,  # Increased so explanations never truncate
        )
        try:
            response = model.generate_content(
                combined_prompt,
                generation_config=generation_config
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            print(f"GEMINI ERROR: {e}")
            # Graceful fallback: build a plain summary from the data directly
            return _fallback_explanation(decision, top_features, proxy_flags)
        return _fallback_explanation(decision, top_features, proxy_flags)
