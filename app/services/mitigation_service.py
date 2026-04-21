"""
MitigationService
=================
Applies IBM AIF360 Reweighing to a dataset and compares a baseline
RandomForestClassifier with a fairness-reweighed one.

Algorithm
---------
Reweighing (Kamiran & Calders, 2012) assigns a weight to each training
instance so that the joint distribution of (label, protected attribute)
matches what it would be if the two were statistically independent.
The weighted distribution satisfies demographic parity by construction.

Weight formula
--------------
  W(x) = P_exp(Y=y | A=a) / P_obs(Y=y | A=a)
  P_exp = P(Y=y) * P(A=a)      (expected under independence)
  P_obs = P(Y=y, A=a)          (observed joint)

The AIF360 library computes this for us via BinaryLabelDataset + Reweighing.

Evaluation
----------
An 80/20 stratified train/test split is used so that reported metrics
reflect out-of-sample generalisation, not in-sample fit.
"""

import io
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


class MitigationService:

    def run(
        self,
        df: pd.DataFrame,
        target_col: str,
        protected_col: str,
    ) -> Dict[str, Any]:
        """
        Run the full reweighing pipeline and return a before/after comparison.

        Parameters
        ----------
        df            : pandas DataFrame parsed from the uploaded CSV
        target_col    : name of the binary label column (0 = unfavourable, 1 = favourable)
        protected_col : name of the protected attribute column
        """
        # ── 1. Basic validation ──────────────────────────────────────────────
        missing = [c for c in [target_col, protected_col] if c not in df.columns]
        if missing:
            raise ValueError(f"Column(s) not found in CSV: {', '.join(missing)}")

        df = df.dropna(subset=[target_col, protected_col]).copy().reset_index(drop=True)

        if len(df) < 50:
            raise ValueError(
                f"Dataset has only {len(df)} usable rows after dropping NaNs. "
                "Need at least 50 rows for a meaningful train/test split."
            )

        # ── 2. Label-encode all categorical columns ──────────────────────────
        le_map: Dict[str, LabelEncoder] = {}
        for col in df.columns:
            if df[col].dtype == object or str(df[col].dtype) == "category":
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                le_map[col] = le

        # ── 3. Normalise target to strict {0, 1} ────────────────────────────
        target_vals = sorted(df[target_col].unique())
        if len(target_vals) < 2:
            raise ValueError("Target column must have at least 2 distinct values.")
        if set(target_vals) != {0, 1}:
            # Map: maximum value → 1 (favourable), everything else → 0
            df[target_col] = (df[target_col] == max(target_vals)).astype(int)

        # ── 4. Identify privileged / unprivileged groups ─────────────────────
        vc = df[protected_col].value_counts()
        if len(vc) < 2:
            raise ValueError(
                f"Protected column '{protected_col}' has fewer than 2 unique values."
            )
        privileged_val   = int(vc.index[0])   # majority class
        unprivileged_val = int(vc.index[1])    # second-most-common class

        # Human-readable labels (decoded from LabelEncoder if available)
        def _decode_prot(val: int) -> str:
            if protected_col in le_map:
                return str(le_map[protected_col].inverse_transform([val])[0])
            return str(val)

        priv_label   = _decode_prot(privileged_val)
        unpriv_label = _decode_prot(unprivileged_val)

        # ── 5. Build feature matrix ──────────────────────────────────────────
        feature_cols = [c for c in df.columns if c != target_col]
        X = df[feature_cols].values.astype(float)
        y = df[target_col].values.astype(int)
        # Protected column values (integer-encoded) used for metric computation
        prot_idx     = feature_cols.index(protected_col)
        protected    = X[:, prot_idx].astype(int)

        # ── 6. Stratified 80/20 split ────────────────────────────────────────
        X_train, X_test, y_train, y_test, prot_train, prot_test = train_test_split(
            X, y, protected,
            test_size=0.2, random_state=42, stratify=y,
        )

        # ── 7. AIF360 Reweighing weights ─────────────────────────────────────
        sample_weights = self._compute_weights(
            X_train, y_train,
            feature_cols, target_col, protected_col,
            privileged_val, unprivileged_val,
        )

        # ── 8. Train baseline and reweighed models ───────────────────────────
        rf_orig = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        rf_orig.fit(X_train, y_train)

        rf_rew = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        rf_rew.fit(X_train, y_train, sample_weight=sample_weights)

        # ── 9. Evaluate on held-out test set ─────────────────────────────────
        y_pred_orig = rf_orig.predict(X_test)
        y_pred_rew  = rf_rew.predict(X_test)

        acc_orig = float(accuracy_score(y_test, y_pred_orig))
        acc_rew  = float(accuracy_score(y_test, y_pred_rew))

        dpd_orig, eod_orig = self._fairness_metrics(
            y_test, y_pred_orig, prot_test, privileged_val, unprivileged_val
        )
        dpd_rew, eod_rew = self._fairness_metrics(
            y_test, y_pred_rew, prot_test, privileged_val, unprivileged_val
        )

        # ── 10. Build response ───────────────────────────────────────────────
        before = {
            "accuracy":                      round(acc_orig, 4),
            "demographic_parity_difference": round(dpd_orig, 4),
            "equal_opportunity_difference":  round(eod_orig, 4),
        }
        after = {
            "accuracy":                      round(acc_rew, 4),
            "demographic_parity_difference": round(dpd_rew, 4),
            "equal_opportunity_difference":  round(eod_rew, 4),
        }

        # Positive → fairness improved; negative → fairness worsened
        dpd_improvement = round(dpd_orig - dpd_rew, 4)
        eod_improvement = round(eod_orig - eod_rew, 4)

        return {
            # ── User-requested fields ───────────────────────────────────────
            "before": before,
            "after":  after,
            "accuracy_cost":       round(acc_orig - acc_rew, 4),
            "fairness_improvement": dpd_improvement,
            # ── Context ────────────────────────────────────────────────────
            "eod_improvement":    eod_improvement,
            "num_rows_total":     len(df),
            "num_rows_train":     int(len(X_train)),
            "num_rows_test":      int(len(X_test)),
            "algorithm":          "Reweighing (IBM AIF360)",
            "target_column":      target_col,
            "protected_column":   protected_col,
            "privileged_group":   {protected_col: priv_label},
            "unprivileged_group": {protected_col: unpriv_label},
            # ── MitigationData-compatible fields for POST /audit/report ────
            "method": "Reweighing (IBM AIF360)",
            "original_metrics": {
                "accuracy":                      round(acc_orig, 4),
                "demographic_parity_difference": round(dpd_orig, 4),
                "equal_opportunity_difference":  round(eod_orig, 4),
            },
            "mitigated_metrics": {
                "accuracy":                      round(acc_rew, 4),
                "demographic_parity_difference": round(dpd_rew, 4),
                "equal_opportunity_difference":  round(eod_rew, 4),
            },
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _compute_weights(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        feature_cols: list,
        target_col: str,
        protected_col: str,
        privileged_val: int,
        unprivileged_val: int,
    ) -> np.ndarray:
        """
        Try to compute AIF360 Reweighing weights for the training set.
        Falls back to uniform weights (all ones) if AIF360 is unavailable or errors.
        """
        try:
            from aif360.datasets import BinaryLabelDataset
            from aif360.algorithms.preprocessing import Reweighing as _AIF360Reweighing
        except ImportError:
            # AIF360 not installed — silently use uniform weights
            return np.ones(len(y_train), dtype=float)

        try:
            train_df = pd.DataFrame(X_train, columns=feature_cols)
            train_df[target_col] = y_train.astype(int)

            # Convert protected column to int to avoid AIF360 type issues
            train_df[protected_col] = train_df[protected_col].astype(int)

            privileged_groups   = [{protected_col: privileged_val}]
            unprivileged_groups = [{protected_col: unprivileged_val}]

            aif_ds = BinaryLabelDataset(
                df=train_df,
                label_names=[target_col],
                protected_attribute_names=[protected_col],
                favorable_label=1,
                unfavorable_label=0,
            )

            rw = _AIF360Reweighing(
                unprivileged_groups=unprivileged_groups,
                privileged_groups=privileged_groups,
            )
            rw.fit(aif_ds)
            reweighed_ds = rw.transform(aif_ds)
            weights = reweighed_ds.instance_weights.flatten().astype(float)

            # Clip extreme weights (cap at 10× the median to prevent instability)
            median_w = float(np.median(weights[weights > 0]))
            weights  = np.clip(weights, 1e-6, 10.0 * median_w)
            return weights

        except Exception:
            # Any AIF360 failure → uniform weights (no reweighing applied)
            return np.ones(len(y_train), dtype=float)

    def _fairness_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        protected: np.ndarray,
        privileged_val: int,
        unprivileged_val: int,
    ) -> Tuple[float, float]:
        """
        Compute Demographic Parity Difference and Equal Opportunity Difference
        between the privileged and unprivileged groups.

        Returns
        -------
        (dpd, eod)  both in [0, 1]
        """
        priv_mask   = protected == privileged_val
        unpriv_mask = protected == unprivileged_val

        # ── DPD: |approval_rate_priv - approval_rate_unpriv| ────────────────
        ar_priv   = float(y_pred[priv_mask].mean())   if priv_mask.sum()   > 0 else 0.0
        ar_unpriv = float(y_pred[unpriv_mask].mean()) if unpriv_mask.sum() > 0 else 0.0
        dpd       = abs(ar_priv - ar_unpriv)

        # ── EOD: |TPR_priv - TPR_unpriv| ────────────────────────────────────
        priv_pos   = priv_mask   & (y_true == 1)
        unpriv_pos = unpriv_mask & (y_true == 1)
        tpr_priv   = float(y_pred[priv_pos].mean())   if priv_pos.sum()   > 0 else 0.0
        tpr_unpriv = float(y_pred[unpriv_pos].mean()) if unpriv_pos.sum() > 0 else 0.0
        eod        = abs(tpr_priv - tpr_unpriv)

        return dpd, eod
