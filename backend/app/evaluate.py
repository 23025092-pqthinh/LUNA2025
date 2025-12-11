import csv
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)

logger = logging.getLogger(__name__)


def analyze_groundtruth(ground_truth_path: str) -> Dict[str, Any]:
    """Read a ground-truth CSV and return simple diagnostics.

    Returns a dict with columns, schema_valid, counts and label distribution.
    """
    df = pd.read_csv(ground_truth_path)
    cols = df.columns.tolist()
    stats: Dict[str, Any] = {"columns": cols}

    missing_id = "id" not in cols
    missing_label = "label" not in cols
    stats["schema_valid"] = not (missing_id or missing_label)
    if not stats["schema_valid"]:
        errors = []
        if missing_id:
            errors.append("Missing 'id' column")
        if missing_label:
            errors.append("Missing 'label' column")
        stats["errors"] = errors
        return stats

    stats["total_rows"] = int(len(df))
    stats["null_id"] = int(df["id"].isna().sum())
    stats["null_label"] = int(df["label"].isna().sum())
    stats["duplicate_id"] = int(df["id"].duplicated().sum())
    try:
        dist = df["label"].value_counts(dropna=False).to_dict()
        stats["label_distribution"] = {str(k): int(v) for k, v in dist.items()}
    except Exception:
        stats["label_distribution"] = {}
    return stats


def _coerce_binary_labels(label_series: pd.Series, score_series: pd.Series) -> pd.Series:
    """Coerce arbitrary label values into {0,1} for binary-AUC calculation.

    If labels are already numeric ints, return directly. Otherwise use the mean
    score per label to identify the positive class.
    """
    try:
        return label_series.astype(int)
    except Exception:
        unique_labels = label_series.dropna().unique().tolist()
        if not unique_labels:
            raise ValueError("Ground truth label column is empty")
        if len(unique_labels) == 1:
            return pd.Series(0, index=label_series.index)
        if len(unique_labels) > 2:
            raise ValueError("ROC AUC requires binary ground truth labels")

        scoring = (
            pd.DataFrame({"label": label_series, "score": score_series}).dropna(subset=["label", "score"])
        )
        if scoring.empty:
            raise ValueError("Score column contains no numeric data for label mapping")
        label_scores = scoring.groupby("label")["score"].mean()
        label_scores = label_scores.reindex(unique_labels, fill_value=float("-inf"))
        positive_label = label_scores.idxmax()
        label_map = {positive_label: 1}
        for label in unique_labels:
            if label != positive_label:
                label_map[label] = 0
        mapped = label_series.map(label_map)
        return mapped.fillna(0).astype(int)


def _evaluate_core(ground_truth_path: str, predict_path: str, *, return_curves: bool = True, raise_on_missing: bool = True) -> Dict[str, Any]:
    try:
        df_true = pd.read_csv(ground_truth_path)
    except Exception:
        df_true = None

    if df_true is None or "id" not in df_true.columns or "label" not in df_true.columns:
        gt_map = _read_label_map(ground_truth_path)
        if not gt_map:
            if raise_on_missing:
                raise ValueError("Ground truth CSV must have columns: id,label")
            return {"auc": None, "precision": 0.0, "recall": 0.0, "f1": 0.0, "acc": 0.0, "n_samples": 0}
        df_true = pd.DataFrame(list(gt_map.items()), columns=["id", "label"])

    # Load predictions (try pandas then fallback)
    df_pred: Optional[pd.DataFrame] = None
    try:
        df_pred = pd.read_csv(predict_path)
    except Exception:
        df_pred = None

    if df_pred is None or "id" not in df_pred.columns:
        pred_map = _read_label_map(predict_path)
        if not pred_map:
            if raise_on_missing:
                raise ValueError("Prediction CSV must contain an id column")
            return {"auc": None, "precision": 0.0, "recall": 0.0, "f1": 0.0, "acc": 0.0, "n_samples": 0}
        df_pred = pd.DataFrame(list(pred_map.items()), columns=["id", "label"])

    # Score/label detection (case-insensitive preferred names)
    preferred_score_names = {"label_pred", "probability", "score", "prediction", "label_score", "prob"}
    score_column: Optional[str] = None
    pred_label_column: Optional[str] = None
    for col in df_pred.columns:
        if col.lower() in preferred_score_names:
            score_column = col
            break

    if score_column is None:
        if "label_pred" in df_pred.columns:
            pred_label_column = "label_pred"
        elif "label" in df_pred.columns:
            pred_label_column = "label"
        else:
            if raise_on_missing:
                raise ValueError(
                    "Prediction CSV must have either a probability column or a predicted label column (label_pred/label/probability/score)"
                )
            return {"auc": None, "precision": 0.0, "recall": 0.0, "f1": 0.0, "acc": 0.0, "n_samples": 0}

    # Merge on id
    if score_column is not None:
        merged = pd.merge(df_true[["id", "label"]], df_pred[["id", score_column]], on="id", how="inner")
    else:
        merged = pd.merge(df_true[["id", "label"]], df_pred[["id", pred_label_column]], on="id", how="inner")

    if merged.empty:
        if raise_on_missing:
            logger.warning("_evaluate_core: merged dataframe empty after joining on id")
            raise ValueError("No matching ids between ground truth and predictions")
        return {"auc": None, "precision": 0.0, "recall": 0.0, "f1": 0.0, "acc": 0.0, "n_samples": 0}

    auc = None
    fpr: List[float] = []
    tpr: List[float] = []
    prec_curve: List[float] = []
    rec_curve: List[float] = []

    if score_column is not None:
        y_score = pd.to_numeric(merged[score_column], errors="raise")
        y_true = _coerce_binary_labels(merged["label"], y_score)
        try:
            auc = float(roc_auc_score(y_true, y_score))
        except Exception as exc:
            auc = None
            logger.warning("_evaluate_core: failed to compute ROC AUC (%s)", exc)

        y_hat = (y_score >= 0.5).astype(int)
        f1 = float(f1_score(y_true, y_hat, zero_division=0))
        acc = float(accuracy_score(y_true, y_hat))
        rec = float(recall_score(y_true, y_hat, zero_division=0))
        prec_value = float(precision_score(y_true, y_hat, zero_division=0))

        if return_curves:
            try:
                fpr, tpr, _ = roc_curve(y_true, y_score)
            except Exception:
                fpr, tpr = [], []
            try:
                prec_curve, rec_curve, _ = precision_recall_curve(y_true, y_score)
            except Exception:
                prec_curve, rec_curve = [], []
    else:
        pred_series = merged[pred_label_column]
        true_series = merged["label"]

        try:
            y_true_num = pd.to_numeric(true_series, errors="raise").astype(int)
            y_hat_num = pd.to_numeric(pred_series, errors="raise").astype(int)
        except Exception:
            y_true_str = true_series.astype(str)
            y_hat_str = pred_series.astype(str)
            mapping = {v: i for i, v in enumerate(sorted(y_true_str.unique(), key=str))}
            y_true_num = y_true_str.map(mapping).fillna(-1).astype(int)
            y_hat_num = y_hat_str.map(mapping).fillna(-1).astype(int)

        f1 = float(f1_score(y_true_num, y_hat_num, zero_division=0))
        acc = float(accuracy_score(y_true_num, y_hat_num))
        rec = float(recall_score(y_true_num, y_hat_num, zero_division=0))
        prec_value = float(precision_score(y_true_num, y_hat_num, zero_division=0))
        auc = None

    metrics = {"auc": ("-" if auc is None else auc), "precision": prec_value, "recall": rec, "f1": f1, "acc": acc}
    result: Dict[str, Any] = {**metrics, "n_samples": int(len(merged))}
    if return_curves and len(fpr) and len(tpr):
        result["ROC"] = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
    if return_curves and len(prec_curve) and len(rec_curve):
        result["PR"] = {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()}
    if auc is not None and isinstance(auc, (int, float)) and auc <= 0:
        logger.warning("_evaluate_core: computed ROC AUC <= 0 (value=%s)", auc)
    logger.debug("_evaluate_core: result=%s", {"auc": auc, "f1": f1, "acc": acc, "n_samples": len(merged)})

    return result


def evaluate_predictions(ground_truth_path: str, predict_path: str) -> Dict[str, Any]:
    """Evaluate predictions file against ground-truth file and return metrics.

    This function prefers an explicit numeric score/probability column when
    available; otherwise it treats predictions as class labels and skips AUC.
    """
    return _evaluate_core(ground_truth_path, predict_path, return_curves=True, raise_on_missing=True)


def _looks_like_header(row: List[str]) -> bool:
    if not row:
        return False
    first = row[0].strip().lower()
    if first != "id":
        return False
    if len(row) == 1:
        return True
    second = row[1].strip().lower()
    return second in {"label", "label_pred", "label_score", "probability", "score", "prediction"}


def _read_label_map(path: str) -> Dict[str, str]:
    """Read a simple two-column CSV (id,label) into a dict.

    Header detection is tolerant: if the first row looks like a header it will be skipped.
    """
    m: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header_skipped = False
        for row in reader:
            if not row:
                continue
            if len(row) < 2:
                continue
            if not header_skipped:
                header_skipped = True
                if _looks_like_header(row):
                    continue
            _id = row[0].strip()
            _label = row[1].strip()
            if not _id:
                continue
            m[_id] = _label
    return m


def compute_classification_metrics(gt_path: str, pred_path: str) -> Dict[str, Any]:
    """Compute classification metrics (acc, precision, recall, f1) and optional AUC.

    AUC is only computed when the prediction CSV contains an explicit numeric
    score/probability column (e.g. `prob`, `score`, `probability`). Label-only
    files (id,label) are treated as classification outputs and do not yield AUC.
    """
    # Preserve prior FileNotFoundError semantics
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Groundtruth not found: {gt_path}")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Submission file not found: {pred_path}")

    try:
        res = _evaluate_core(gt_path, pred_path, return_curves=False, raise_on_missing=False)
    except ValueError:
        # If core raised despite our non-raising request, return zeroed metrics
        return {"acc": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "auc": None}

    return {"acc": res.get("acc", 0.0), "precision": res.get("precision", 0.0), "recall": res.get("recall", 0.0), "f1": res.get("f1", 0.0), "auc": res.get("auc", None)}
