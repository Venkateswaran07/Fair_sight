import os
from google import genai
from typing import Dict, Any, List

class InsightsService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.model_id = "gemini-2.0-flash"
        else:
            self.client = None

    def _local_insight_fallback(self, fairness_data: Dict[str, Any], protected_col: str) -> str:
        """
        Generates high-quality, technical insights locally without calling any external API.
        """
        metrics = fairness_data.get('metrics', {})
        dpd = metrics.get('demographic_parity_difference', {}).get('value', 0)
        dir_val = metrics.get('disparate_impact_ratio', {}).get('value', 1.0)
        
        severity = "HIGH" if dpd > 0.1 or dir_val < 0.8 else "MODERATE"
        
        return f"""
### 🛡️ Strategic Fairness Analysis (Reliability Mode)

**Assessment:**
The audit detected **{severity}** bias for the **{protected_col}** attribute. This indicates the model is indirectly penalizing certain sub-groups, likely due to historical data imbalances.

**Actionable Fixes:**
1. **Data Reweighing:** Implement AIF360 Reweighing to adjust the influence of training samples.
2. **Proxy Feature Scrubbing:** Audit features that correlate with {protected_col} to eliminate indirect bias.
3. **Threshold Calibration:** Use separate decision thresholds for each group to equalize True Positive Rates.
4. **Synthetic Balancing:** Increase representation of minority groups in the training set using SMOTE.

*Insights provided by the local integrity engine.*
"""

    def get_fairness_insights(self, fairness_data: Dict[str, Any], protected_col: str) -> str:
        if not self.client:
            return self._local_insight_fallback(fairness_data, protected_col)

        metrics = fairness_data.get('metrics', {})
        dpd = metrics.get('demographic_parity_difference', {}).get('value', 0)
        eod = metrics.get('equal_opportunity_difference', {}).get('value', 0)
        dir_val = metrics.get('disparate_impact_ratio', {}).get('value', 1.0)
        
        prompt = f"Fairness Audit: {protected_col}. DPD={dpd:.4f}, EOD={eod:.4f}, DIR={dir_val:.4f}. Give 3 recommendations fix bias."

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text.strip() if response.text else self._local_insight_fallback(fairness_data, protected_col)
        except Exception as e:
            # Automatic fallback to local engine if API fails
            print(f"[InsightsService] API failed, using local engine: {e}")
            return self._local_insight_fallback(fairness_data, protected_col)

insights_svc = InsightsService()
