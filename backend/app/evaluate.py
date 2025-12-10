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


def evaluate_predictions(ground_truth_path: str, predict_path: str) -> Dict[str, Any]:
    """Evaluate predictions file against ground-truth file and return metrics.

    This function prefers an explicit numeric score/probability column when
    available; otherwise it treats predictions as class labels and skips AUC.
    """
    df_true = pd.read_csv(ground_truth_path)
    df_pred = pd.read_csv(predict_path)

    if "id" not in df_true.columns or "label" not in df_true.columns:
        raise ValueError("Ground truth CSV must have columns: id,label")
    if "id" not in df_pred.columns:
        raise ValueError("Prediction CSV must contain an id column")

    # Preferred score column names (case-insensitive)
    preferred_score_names = {"label_pred", "probability", "score", "prediction", "label_score", "prob"}
    score_column: Optional[str] = None
    pred_label_column: Optional[str] = None

    # Detect explicit score column
    for col in df_pred.columns:
        if col.lower() in preferred_score_names:
            score_column = col
            break

    # If no explicit score column, pick predicted-label column if available
    if score_column is None:
        if "label_pred" in df_pred.columns:
            pred_label_column = "label_pred"
        elif "label" in df_pred.columns:
            pred_label_column = "label"
        else:
            raise ValueError(
                "Prediction CSV must have either a probability column or a predicted label column (label_pred/label/probability/score)"
            )

    logger.debug(
        "evaluate_predictions: predict columns=%s, score_column=%s, pred_label_column=%s",
        list(df_pred.columns),
        score_column,
        pred_label_column,
    )

    # Merge on id and compute metrics
    if score_column is not None:
        merged = pd.merge(df_true[["id", "label"]], df_pred[["id", score_column]], on="id", how="inner")
    else:
        merged = pd.merge(df_true[["id", "label"]], df_pred[["id", pred_label_column]], on="id", how="inner")

    if merged.empty:
        logger.warning("evaluate_predictions: merged dataframe empty after joining on id")
        raise ValueError("No matching ids between ground truth and predictions")

    auc = None
    fpr: List[float] = []
    tpr: List[float] = []
    prec_curve: List[float] = []
    rec_curve: List[float] = []

    if score_column is not None:
        logger.debug("evaluate_predictions: computing AUC using score column '%s'", score_column)
        y_score = pd.to_numeric(merged[score_column], errors="raise")
        y_true = _coerce_binary_labels(merged["label"], y_score)
        try:
            auc = float(roc_auc_score(y_true, y_score))
        except Exception as exc:
            auc = None
            logger.warning("evaluate_predictions: failed to compute ROC AUC (%s)", exc)
            logger.debug("evaluate_predictions: y_true sample=%s, y_score sample=%s",
                         y_true.head().tolist() if hasattr(y_true, "head") else y_true[:5],
                         y_score.head().tolist() if hasattr(y_score, "head") else y_score[:5])

        y_hat = (y_score >= 0.5).astype(int)
        f1 = float(f1_score(y_true, y_hat, zero_division=0))
        acc = float(accuracy_score(y_true, y_hat))
        rec = float(recall_score(y_true, y_hat, zero_division=0))
        prec_value = float(precision_score(y_true, y_hat, zero_division=0))

        try:
            fpr, tpr, _ = roc_curve(y_true, y_score)
        except Exception:
            fpr, tpr = [], []
        try:
            prec_curve, rec_curve, _ = precision_recall_curve(y_true, y_score)
        except Exception:
            prec_curve, rec_curve = [], []
    else:
        # Label-only predictions: compute classification metrics, skip AUC
        logger.debug("evaluate_predictions: label-only predictions using column %s", pred_label_column)
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
    if len(fpr) and len(tpr):
        result["ROC"] = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
    if len(prec_curve) and len(rec_curve):
        result["PR"] = {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()}
    if auc is not None and auc <= 0:
        logger.warning("evaluate_predictions: computed ROC AUC <= 0 (value=%s)", auc)
    logger.debug("evaluate_predictions: result=%s", {"auc": auc, "f1": f1, "acc": acc, "n_samples": len(merged)})

    return result


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
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Groundtruth not found: {gt_path}")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Submission file not found: {pred_path}")

    gt = _read_label_map(gt_path)
    pred = _read_label_map(pred_path)

    # Try to detect a numeric score column in the prediction CSV
    score_column: Optional[str] = None
    score_lookup: Dict[str, float] = {}
    try:
        _pred_df = pd.read_csv(pred_path)
        pred_cols = _pred_df.columns.tolist()
        preferred = {"label_pred", "probability", "score", "prediction", "label_score", "prob"}
        for c in pred_cols:
            if c.lower() in preferred and c.lower() != "id":
                score_column = c
                break
        # if no explicit name, look for extra numeric columns
        if score_column is None:
            extras = [c for c in pred_cols if c.lower() not in ("id", "label", "label_pred")]
            for ex in extras:
                try:
                    sample = _pred_df[ex].dropna().head(5).astype(float)
                    if not sample.empty:
                        score_column = ex
                        break
                except Exception:
                    continue

        if score_column is not None and "id" in [c.lower() for c in pred_cols]:
            id_col = [c for c in pred_cols if c.lower() == "id"][0]
            for _, row in _pred_df.iterrows():
                raw_id = row.get(id_col)
                raw_score = row.get(score_column)
                if pd.isna(raw_id) or pd.isna(raw_score):
                    continue
                try:
                    score_lookup[str(raw_id)] = float(raw_score)
                except Exception:
                    continue
    except Exception as exc:
        logger.debug("compute_classification_metrics: failed to inspect prediction file (%s)", exc)
        score_column = None

    if not gt:
        logger.debug("compute_classification_metrics: groundtruth empty for %s", gt_path)
        return {"acc": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "auc": None}

    y_true: List[Any] = []
    y_pred: List[Any] = []
    y_scores_for_auc: List[float] = []
    y_true_for_auc: List[Any] = []

    for k, v in gt.items():
        if k not in pred:
            continue
        y_true.append(v)
        y_pred.append(pred[k])
        if score_column is not None:
            sc = score_lookup.get(k)
            if sc is not None:
                try:
                    y_scores_for_auc.append(float(sc))
                    # store corresponding true value (coerced later)
                    y_true_for_auc.append(v)
                except Exception:
                    pass

    if not y_true:
        logger.debug("compute_classification_metrics: no overlapping ids between gt and pred")
        return {"acc": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "auc": None}

    def _coerce(val: Any):
        try:
            return int(val)
        except Exception:
            try:
                return float(val)
            except Exception:
                return val

    y_true_num = [_coerce(v) for v in y_true]
    y_pred_num = [_coerce(v) for v in y_pred]

    unique_labels = sorted(set(y_true_num), key=lambda x: str(x))
    logger.debug(
        "compute_classification_metrics: unique_labels=%s, sample_scores=%s, score_column=%s",
        unique_labels,
        (y_scores_for_auc[:5] if y_scores_for_auc else []),
        score_column,
    )

    average = "binary" if len(unique_labels) == 2 else "macro"
    score_kwargs = {"zero_division": 0}
    if average == "binary":
        score_kwargs["pos_label"] = unique_labels[-1]

    acc = float(accuracy_score(y_true_num, y_pred_num))
    precision = float(precision_score(y_true_num, y_pred_num, average=average, **score_kwargs))
    recall = float(recall_score(y_true_num, y_pred_num, average=average, **score_kwargs))
    f1 = float(f1_score(y_true_num, y_pred_num, average=average, **score_kwargs))

    auc: Optional[float] = None
    logger.warning(
        "compute_classification_metrics: unique labels=%i unique scores=%i score_column=%s",
        len(set(y_true_num)),
        len(set(y_scores_for_auc)) if y_scores_for_auc else 0,
        score_column,
    )

    # Compute AUC only when we detected a score column and have numeric scores
    if score_column is not None and y_scores_for_auc and len(set(y_scores_for_auc)) > 1 and len(set(y_true_for_auc)) > 1:
        try:
            y_true_for_auc_num = [_coerce(v) for v in y_true_for_auc]
            auc = float(roc_auc_score(y_true_for_auc_num, y_scores_for_auc))
            logger.warning("auc: (%s)", auc)
        except Exception as exc:
            auc = None
            logger.warning("compute_classification_metrics: failed to compute ROC AUC (%s)", exc)
    else:
        logger.debug("compute_classification_metrics: skip ROC AUC (score_column=%s scores=%s labels=%s)", score_column, y_scores_for_auc, y_true_num)

    return {"acc": acc, "precision": precision, "recall": recall, "f1": f1, "auc": ("-" if auc is None else auc)}
