"""
CFExplainerService — self-contained counterfactual generation.

Workflow
--------
1. Read CSV → training DataFrame
2. Label-encode categorical columns; store encode/decode maps
3. Train a RandomForestClassifier on the encoded data
4. Encode the user-supplied instance with the *same* maps
5. Run DiCE-ML (random sampler) to generate N counterfactuals
   targeting desired_class (default 1 = "approved")
6. Decode CF values back to original space
7. For each CF build:
   - changed_features  : {col: {original, new}}
   - full_instance     : complete feature dict with CF values
   - explanation       : human-readable sentence, e.g.
       "If employment_gap_months were 2 instead of 8
        and credit_score were 650 instead of 580: APPROVED"
"""

import io
import json
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

NUM_CFS = 3
_RF_PARAMS = dict(n_estimators=100, random_state=42, n_jobs=None)
_DESIRED_CLASS_LABEL = "APPROVED"
_REJECTED_CLASS_LABEL = "REJECTED"


# ── Encoding helpers ───────────────────────────────────────────────────────

def _build_maps(series: pd.Series) -> Tuple[Dict, Dict]:
    """Return (encode_map, decode_map) for a categorical series."""
    cats = series.dropna().astype(str).unique().tolist()
    cats.sort()
    enc = {v: i for i, v in enumerate(cats)}
    dec = {i: v for i, v in enumerate(cats)}
    return enc, dec


def _encode_df(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, Dict], Dict[str, Dict]]:
    """
    Label-encode all non-numeric columns in *df*.

    Returns
    -------
    encoded_df   : DataFrame with all-numeric values
    encode_maps  : {col: {original_val -> int}}
    decode_maps  : {col: {int -> original_val}}
    """
    df = df.copy()
    encode_maps: Dict[str, Dict] = {}
    decode_maps: Dict[str, Dict] = {}

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            enc, dec = _build_maps(df[col])
            df[col] = df[col].astype(str).map(enc).fillna(-1).astype(int)
            encode_maps[col] = enc
            decode_maps[col] = dec

    return df.fillna(0), encode_maps, decode_maps


def _encode_instance(
    instance: Dict[str, Any],
    feature_cols: List[str],
    encode_maps: Dict[str, Dict],
    df_train: pd.DataFrame,
) -> Dict[str, Any]:
    """Encode a single instance dict using pre-fitted maps. Missing keys → 0."""
    from app.utils.data_utils import translate_value_to_numeric
    row: Dict[str, Any] = {}
    for col in feature_cols:
        val = instance.get(col, 0)
        
        # Try to translate string inputs (like 'male') to numeric if needed
        if col in df_train.columns:
            val = translate_value_to_numeric(val, df_train[col])
            
        if col in encode_maps:
            row[col] = encode_maps[col].get(str(val), -1)
        else:
            row[col] = val
    return row


def _decode_value(col: str, val, decode_maps: Dict[str, Dict]) -> Any:
    """Reverse-encode a single value; leaves numeric columns unchanged."""
    if col not in decode_maps:
        # Numeric — round floats that should be ints
        try:
            if float(val) == int(float(val)):
                return int(float(val))
        except (TypeError, ValueError):
            pass
        return val
    key = int(round(float(val)))
    return decode_maps[col].get(key, val)


# ── Explanation sentence builder ───────────────────────────────────────────

def _build_explanation(
    changes: Dict[str, Dict[str, Any]],
    desired_label: str,
) -> str:
    """
    Build a plain-English sentence from a changes dict.

    Examples
    --------
    1 change  → "If income were 60000 instead of 45000: APPROVED"
    2 changes → "If income were 60000 instead of 45000
                  and credit_score were 700 instead of 580: APPROVED"
    3+ changes → "If income were 60000 instead of 45000,
                   credit_score were 700 instead of 580,
                   and employment_gap_months were 2 instead of 8: APPROVED"
    """
    items = list(changes.items())
    if not items:
        return f"No feature changes required: {desired_label}"

    clauses = [
        f"{col} were {v['new']} instead of {v['original']}"
        for col, v in items
    ]

    if len(clauses) == 1:
        joined = clauses[0]
    elif len(clauses) == 2:
        joined = f"{clauses[0]} and {clauses[1]}"
    else:
        joined = ", ".join(clauses[:-1]) + f", and {clauses[-1]}"

    return f"If {joined}: {desired_label}"


# ── Service ────────────────────────────────────────────────────────────────

class CFExplainerService:
    def generate(
        self,
        raw_bytes: bytes,
        target_column: str,
        instance_raw: str,
        num_cfs: int = NUM_CFS,
        desired_class: int = 1,
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        raw_bytes
            Raw CSV bytes (training dataset).
        target_column
            Name of the label column.
        instance_raw
            JSON string of the instance whose prediction is to be flipped,
            e.g. '{"age": 45, "income": 30000, "gender": "Female"}'.
        num_cfs
            Number of counterfactuals to return (default 3).
        desired_class
            Target class to flip *to* (default 1 = "approved").

        Returns
        -------
        dict  — full structured result ready for JSON serialisation.

        Raises
        ------
        ValueError
            On missing target column or invalid instance JSON.
        """
        # ── Load & validate ─────────────────────────────────────────────
        from app.utils.data_utils import normalize_dataframe_headers, normalize_string, normalize_dictionary_keys
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)
        
        # Normalize target column name
        target_column = normalize_string(target_column)

        if target_column not in df.columns:
            raise ValueError(
                f"Target column '{target_column}' not found in CSV. "
                f"Available: {list(df.columns)}"
            )

        feature_cols = [c for c in df.columns if c != target_column]
        if not feature_cols:
            raise ValueError("No feature columns found after removing the target column.")

        # ── Parse instance ───────────────────────────────────────────────
        try:
            instance_dict: Dict[str, Any] = json.loads(instance_raw)
            if not isinstance(instance_dict, dict):
                raise ValueError
            # Clean up applicant column names
            instance_dict = normalize_dictionary_keys(instance_dict)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(
                "instance must be a valid JSON object, "
                'e.g. \'{"age": 45, "income": 30000}\''
            )

        y = df[target_column]
        X_raw = df[feature_cols]

        # ── Encode ──────────────────────────────────────────────────────
        X_enc, encode_maps, decode_maps = _encode_df(X_raw)
        y_enc = y.copy()

        # If target is continuous numeric (too many unique values), auto-bin it
        if pd.api.types.is_numeric_dtype(y_enc) and y_enc.nunique() > 5:
            median_val = y_enc.median()
            y_enc = (y_enc > median_val).astype(int)
            print(f"[CFExplainer] Auto-binned continuous target '{target_column}' at median {median_val}")
            
        # If target is non-numeric (e.g. 'Yes'/'No'), label-encode it to 0/1
        elif not pd.api.types.is_numeric_dtype(y_enc):
            unique_labels = sorted(y_enc.dropna().unique(), key=str)
            _target_label_map = {lbl: i for i, lbl in enumerate(unique_labels)}
            y_enc = y_enc.map(_target_label_map)
            print(f"[CFExplainer] Label-encoded target '{target_column}': {_target_label_map}")

        y_enc = y_enc.astype(int)

        # ── Train RF ────────────────────────────────────────────────────
        model = RandomForestClassifier(**_RF_PARAMS)
        model.fit(X_enc, y_enc)

        inst_enc = _encode_instance(instance_dict, feature_cols, encode_maps, df)
        inst_df = pd.DataFrame([inst_enc])
        # Coerce dtypes to match training data exactly to prevent DiCE crash
        for col in feature_cols:
            if col in X_enc.columns:
                inst_df[col] = inst_df[col].astype(X_enc[col].dtype)

        original_pred = int(model.predict(inst_df)[0])


        # ── DiCE setup ──────────────────────────────────────────────────
        import dice_ml
        from dice_ml import Dice

        # DiCE needs the encoded df + target
        dice_df = X_enc.copy()
        dice_df[target_column] = y_enc.values

        dice_data = dice_ml.Data(
            dataframe=dice_df,
            continuous_features=feature_cols,   # all numeric after encoding
            outcome_name=target_column,
        )
        dice_model = dice_ml.Model(model=model, backend="sklearn")
        exp = Dice(dice_data, dice_model, method="random")

        # ── Generate CFs ────────────────────────────────────────────────
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cf_result = exp.generate_counterfactuals(
                    inst_df,
                    total_CFs=num_cfs,
                    desired_class=desired_class,
                    features_to_vary="all",
                )
            cf_df: Optional[pd.DataFrame] = cf_result.cf_examples_list[0].final_cfs_df
        except Exception as exc:
            raise ValueError(f"DiCE counterfactual generation failed: {exc}")

        if cf_df is None or cf_df.empty:
            raise ValueError(
                "DiCE could not find any valid counterfactuals for this instance. "
                "Try a larger or more diverse training dataset."
            )

        # Drop target column from CF rows if present
        if target_column in cf_df.columns:
            cf_df = cf_df.drop(columns=[target_column])

        # ── Decode & build results ──────────────────────────────────────
        desired_label = _DESIRED_CLASS_LABEL if desired_class == 1 else str(desired_class)

        counterfactuals: List[Dict[str, Any]] = []

        for i, row in enumerate(cf_df.to_dict(orient="records"), start=1):
            # Decode CF values to original space
            cf_decoded: Dict[str, Any] = {
                col: _decode_value(col, row.get(col, inst_enc.get(col, 0)), decode_maps)
                for col in feature_cols
            }

            # Original instance decoded (for comparison)
            orig_decoded: Dict[str, Any] = {
                col: _decode_value(col, inst_enc.get(col, 0), decode_maps)
                for col in feature_cols
            }

            # Identify changed features
            changed: Dict[str, Dict[str, Any]] = {}
            for col in feature_cols:
                orig_val = orig_decoded[col]
                new_val = cf_decoded[col]
                # Compare as strings to handle float vs int noise
                if str(orig_val) != str(new_val):
                    changed[col] = {"original": orig_val, "new": new_val}

            explanation = _build_explanation(changed, desired_label)

            counterfactuals.append(
                {
                    "id": i,
                    "changed_features": changed,
                    "full_instance": cf_decoded,
                    "explanation": explanation,
                }
            )

        # ── Original instance decoded for response ───────────────────────
        original_decoded = {
            col: _decode_value(col, inst_enc[col], decode_maps) for col in feature_cols
        }

        return {
            "target_column": target_column,
            "original_instance": original_decoded,
            "original_prediction": original_pred,
            "original_prediction_label": (
                _DESIRED_CLASS_LABEL if original_pred == 1 else _REJECTED_CLASS_LABEL
            ),
            "desired_class": desired_class,
            "desired_class_label": desired_label,
            "num_cfs_requested": num_cfs,
            "num_cfs_generated": len(counterfactuals),
            "counterfactuals": counterfactuals,
        }
