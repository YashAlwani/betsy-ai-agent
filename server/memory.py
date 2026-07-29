"""Betsy's supplier memory: learned reliability scores.

The world only states objective facts (expected vs actual delivery dates).
Betsy observes delivered POs and maintains her own EMA reliability score per
supplier, persisted in betsy.db — the world's hidden ground truth is never read.
EMA math is unchanged from the original orders.py _apply_ema (DL-06).
"""
from datetime import datetime

from server import config, db, notifier

EMA_ALPHA = 0.2       # new delivery counts 20%, history 80%
NEUTRAL_PRIOR = 0.8   # score for a supplier Betsy has never observed


def get_scores() -> dict:
    """supplier_id -> learned score details (only observed suppliers)."""
    return db.load_supplier_scores()


def get_score(supplier_id: str) -> float:
    scores = db.load_supplier_scores()
    if supplier_id in scores:
        return scores[supplier_id]["reliability_score"]
    return NEUTRAL_PRIOR


def observe_deliveries(purchase_orders: list, suppliers: list) -> list:
    """Process newly delivered POs: update EMA scores, log, notify.

    Idempotent — each PO is processed once (processed_deliveries table).
    Returns the list of updates applied.
    """
    processed = db.load_processed_deliveries()
    scores = db.load_supplier_scores()
    names = {s["supplier_id"]: s["name"] for s in suppliers}
    updates = []

    delivered = [
        po for po in purchase_orders
        if po.get("status") == "delivered"
        and po.get("actual_delivery")
        and po["po_id"] not in processed
    ]
    delivered.sort(key=lambda po: (po.get("actual_delivery") or "", po["po_id"]))

    for po in delivered:
        try:
            expected = datetime.fromisoformat(po["expected_delivery"][:19])
            actual   = datetime.fromisoformat(po["actual_delivery"][:19])
            lateness = max(0, (actual - expected).days)
        except Exception:
            db.mark_delivery_processed(po["po_id"], 0)
            continue

        sid = po["supplier_id"]
        entry = scores.get(sid, {"reliability_score": NEUTRAL_PRIOR, "deliveries_observed": 0})
        performance = max(0.0, 1.0 - lateness * 0.1)
        old_score = entry["reliability_score"]
        new_score = round(
            min(1.0, max(0.0, EMA_ALPHA * performance + (1 - EMA_ALPHA) * old_score)), 4
        )
        observed = entry["deliveries_observed"] + 1

        db.upsert_supplier_score(sid, new_score, observed)
        db.mark_delivery_processed(po["po_id"], lateness)
        scores[sid] = {"reliability_score": new_score, "deliveries_observed": observed}

        supplier_name = names.get(sid, sid)
        if new_score < config.SCORE_DROP_THRESHOLD and old_score >= config.SCORE_DROP_THRESHOLD:
            notifier.notify_score_drop(
                supplier_name=supplier_name,
                old_score=old_score,
                new_score=new_score,
                po_id=po["po_id"],
            )

        db.save_log_entry({
            "timestamp": datetime.now().isoformat(),
            "trigger":   "ema_score_update",
            "analysis":  (
                f"{supplier_name} delivered PO {po['po_id']} "
                f"{'on time' if lateness == 0 else f'{lateness}d late'} — "
                f"score {old_score:.4f} → {new_score:.4f}"
            ),
            "decision":  "score_updated",
            "confidence": performance,
            "metadata": {
                "supplier_id":   sid,
                "supplier_name": supplier_name,
                "po_id":         po["po_id"],
                "lateness_days": lateness,
                "performance":   round(performance, 4),
                "old_score":     old_score,
                "new_score":     new_score,
                "ema_alpha":     EMA_ALPHA,
            },
        })
        updates.append({"supplier_id": sid, "po_id": po["po_id"],
                        "old_score": old_score, "new_score": new_score,
                        "lateness_days": lateness})

    return updates


def merge_scores_into_suppliers(suppliers: list) -> list:
    """Attach Betsy's learned reliability_score to world supplier payloads."""
    scores = db.load_supplier_scores()
    merged = []
    for sup in suppliers:
        entry = scores.get(sup["supplier_id"])
        merged.append({
            **sup,
            "reliability_score": entry["reliability_score"] if entry else NEUTRAL_PRIOR,
            "deliveries_observed": entry["deliveries_observed"] if entry else 0,
        })
    return merged
