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
            "Explain this decision in 2-3 plain sentences for an HR manager. "
            "Do not use technical terms like SHAP, correlation, or machine learning. "
            "If proxy concerns are present, mention them simply (e.g. 'ZIP code may be "
            "a stand-in for race'). Keep it empathetic and actionable."
        )
    elif audience == "developer":
        instruction = (
            "Provide a technical explanation of this decision. Include the specific feature "
            "names and their SHAP values, explain what proxy flags imply about model risk, "
            "and describe what the counterfactuals reveal about the decision boundary. "
            "Use precise ML terminology."
        )
    elif audience == "executive":
        instruction = (
            "Write exactly two sentences only. "
            "Sentence 1: a risk summary stating whether this decision carries fairness risk and why. "
            "Sentence 2: a single recommended action the organisation should take. "
            "Do not add any extra text, headings, or bullet points."
        )
    else:
        instruction = "Explain this decision in plain language."

    return f"{context}\n\n---\n{instruction}"


# ── Service ────────────────────────────────────────────────────────────────

class GeminiExplainService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Set it before starting the server: "
                "  Windows: set GEMINI_API_KEY=your_key_here\n"
                "  Linux/Mac: export GEMINI_API_KEY=your_key_here"
            )
        
        genai.configure(api_key=api_key)
        self._model_name = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)

    def explain(
        self,
        decision: str,
        top_features: List[Dict[str, Any]],
        proxy_flags: List[str],
        counterfactuals: List[str],
        audience: str,
    ) -> str:
        """
        Call the Google Gemini LLM and return the explanation text.

        Parameters
        ----------
        decision        : "APPROVED" or "REJECTED"
        top_features    : list of {feature, shap_value, contribution_percent}
        proxy_flags     : list of feature names flagged as proxies
        counterfactuals : list of plain counterfactual strings
        audience        : "hr_manager" | "developer" | "executive"

        Returns
        -------
        str  — the model's explanation text
        """
        system_instruction = _system_prompt(audience)
        user = _user_prompt(decision, top_features, proxy_flags, counterfactuals, audience)

        combined_prompt = f"{system_instruction}\n\nTask:\n{user}"

        # Use the modern Gemini 2.5 Flash model explicitly as shown in your AI Studio dashboard limits
        model_name = "gemini-2.5-flash"
        model = genai.GenerativeModel(model_name)
        
        # Generation config
        generation_config = genai.types.GenerationConfig(
            temperature=0.4,
            max_output_tokens=1024,
        )

        response = model.generate_content(
            combined_prompt,
            generation_config=generation_config
        )

        if response.text:
            return response.text.strip()
        return "Explanation could not be generated."
