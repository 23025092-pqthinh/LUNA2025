from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..deps import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

def _get_metric_from_score(score_json, key):
    if not score_json:
        return None
    # try several casings
    for k in (key, key.upper(), key.lower(), key.capitalize()):
        v = score_json.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                return None
    return None

@router.get("/")
def leaderboard(dataset_id: int | None = None, metric: str = "AUC", db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    Return submission-level leaderboard filtered by dataset_id (if provided)
    and sorted by the chosen metric (descending). Only submissions that have
    a non-null value for the chosen metric in score_json are returned.
    Allowed metrics: AUC, F1, ACC, PRECISION (case-insensitive).
    """
    allowed = {"auc": "AUC", "f1": "F1", "acc": "ACC", "precision": "PRECISION", "recall": "RECALL"}
    metric_key = allowed.get(metric.lower(), "AUC")

    # use outerjoin so submissions without a linked user are still considered
    q = db.query(models.Submission, models.User.username, models.User.group_name) \
          .outerjoin(models.User, models.User.id == models.Submission.user_id)
    if dataset_id:
        q = q.filter(models.Submission.dataset_id == dataset_id)
    rows = q.all()

    # select newest submission per uploader (per dataset) -> key by (user_id, dataset_id)
    latest_map = {}  # (user_id, dataset_id) -> (Submission, username, group)
    for sub, username, group in rows:
        key = (sub.user_id, sub.dataset_id)
        cur = latest_map.get(key)
        # choose by created_at, fallback to id when created_at missing
        def _ts(s):
            if s.created_at is not None:
                return s.created_at
            return None

        if cur is None:
            latest_map[key] = (sub, username, group)
            continue
        prev_sub = cur[0]
        # compare created_at; if equal/None, compare id
        prev_ts = _ts(prev_sub)
        this_ts = _ts(sub)
        replace = False
        if prev_ts is None and this_ts is not None:
            replace = True
        elif prev_ts is not None and this_ts is None:
            replace = False
        elif prev_ts is None and this_ts is None:
            replace = (sub.id is not None and prev_sub.id is not None and sub.id > prev_sub.id)
        else:
            replace = (this_ts > prev_ts) or (this_ts == prev_ts and sub.id is not None and prev_sub.id is not None and sub.id > prev_sub.id)

        if replace:
            latest_map[key] = (sub, username, group)

    out = []
    for (user_id, ds_id), (sub, username, group) in latest_map.items():
        if not sub.score_json:
            continue
        val = _get_metric_from_score(sub.score_json, metric_key)
        if val is None:
            continue
        auc_v = _get_metric_from_score(sub.score_json, "AUC")
        f1_v = _get_metric_from_score(sub.score_json, "F1")
        prec_v = _get_metric_from_score(sub.score_json, "PRECISION")
        rec_v = _get_metric_from_score(sub.score_json, "RECALL")
        acc_v = _get_metric_from_score(sub.score_json, "ACC")

        out.append({
            "submission_id": sub.id,
            "group_name": group or f"user-{sub.user_id}",
            "uploader_id": sub.user_id,
            "uploader_username": username,
            "dataset_id": sub.dataset_id,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "metric": val,
            "metric_name": metric_key,
            "auc": auc_v,
            "f1": f1_v,
            "precision": prec_v,
            "recall": rec_v,
            "acc": acc_v,
        })

    # sort by metric desc, tiebreaker by created_at desc
    out.sort(key=lambda x: (-(x["metric"] if x["metric"] is not None else -1e9), x["created_at"] or ""))
    return out

@router.get("/history")
def history(group_name: str, dataset_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    q = db.query(models.Submission, models.User.group_name)        .join(models.User, models.User.id == models.Submission.user_id)        .filter(models.User.group_name == group_name, models.Submission.dataset_id == dataset_id)        .order_by(models.Submission.created_at.asc())
    rows = q.all()
    out = []
    for sub, _ in rows:
        auc = _get_metric_from_score(sub.score_json, "AUC") if sub.score_json else None
        out.append({
            "submission_id": sub.id,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "auc": auc
        })
    return out
