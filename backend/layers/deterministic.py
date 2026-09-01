"""
ReconAgent - Layer 0: Deterministic Match (Module 2)

Pure rule matching. No LLM, no vector index. Runs first, always.

Rules (all three must hold for a candidate):
  1. Amount within tolerance (default +/-1.0 INR)
  2. Date within tolerance (default 2 days)
  3. Normalized invoice_id appears in normalized payment reference

A match is recorded ONLY when exactly one candidate passes all three rules.
If zero or >1 candidates match, the payment is forwarded to Layer 1.

Every match produces a field-level receipt: which rules fired, the specific
deltas, and the candidate that was selected. This receipt is the audit trail
for the deterministic layer — it must exist for every decision, not just be
inferable from the code (per backend.md).
"""

from __future__ import annotations

import re
import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────

def normalize_ref(text: str) -> str:
    """
    Normalize a reference string for containment checks.
    Strips non-alphanumeric chars and lowercases.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def days_between(date_a: str, date_b: str) -> int:
    """Absolute day difference between two ISO date strings."""
    d_a = date.fromisoformat(date_a)
    d_b = date.fromisoformat(date_b)
    return abs((d_a - d_b).days)


# ── Layer 0 ──────────────────────────────────────────────────────────

def deterministic_match(
    payments: list[dict],
    invoices: list[dict],
    amount_tol: float = 1.0,
    date_tol_days: int = 2,
) -> tuple[list[dict], list[dict]]:
    """
    Deterministic rule-based matching. Zero LLM calls.

    For each payment, find invoices where ALL three rules hold:
      1. |invoice.amount - payment.amount| <= amount_tol
      2. |days_between(invoice.due_date, payment.date)| <= date_tol_days
      3. normalize_ref(invoice.invoice_id) in normalize_ref(payment.reference)

    If exactly one candidate matches → confirmed match (confidence=1.0).
    Otherwise → forwarded as unmatched.

    Returns:
        (matched, unmatched)
        - matched: list of match records with field-level receipts
        - unmatched: list of payment records that didn't match
    """
    matched: list[dict] = []
    unmatched: list[dict] = []

    for p in payments:
        p_ref_norm = normalize_ref(p["reference"])

        candidates: list[dict[str, Any]] = []
        for inv in invoices:
            inv_ref_norm = normalize_ref(inv["invoice_id"])

            amount_delta = abs(inv["amount"] - p["amount"])
            date_delta = days_between(inv["due_date"], p["date"])
            ref_match = inv_ref_norm in p_ref_norm

            rule_amount = amount_delta <= amount_tol
            rule_date = date_delta <= date_tol_days
            rule_ref = ref_match

            if rule_amount and rule_date and rule_ref:
                candidates.append({
                    "invoice_id": inv["invoice_id"],
                    "amount_delta": round(amount_delta, 2),
                    "date_delta_days": date_delta,
                    "ref_contained": True,
                    "rules_passed": {
                        "amount_within_tol": True,
                        "date_within_tol": True,
                        "ref_in_reference": True,
                    },
                })

        if len(candidates) == 1:
            candidate = candidates[0]
            receipt = {
                "payment_id": p["payment_id"],
                "decision": "MATCH",
                "invoice_ids": [candidate["invoice_id"]],
                "confidence": 1.0,
                "reasoning": f"Exact match found deterministically. Amount delta: {candidate['amount_delta']}, Date delta: {candidate['date_delta_days']} days. Reference fully contained.",
                "status": "confirmed",
                "method": "deterministic",
                "receipt": {
                    "rule": "exact_match_all_three",
                    "amount_delta": candidate["amount_delta"],
                    "amount_tol_used": amount_tol,
                    "date_delta_days": candidate["date_delta_days"],
                    "date_tol_used": date_tol_days,
                    "ref_normalized_invoice": normalize_ref(candidate["invoice_id"]),
                    "ref_normalized_payment": p_ref_norm,
                    "ref_contained": True,
                    "candidates_found": 1,
                },
            }
            matched.append(receipt)
            logger.info(
                "Layer 0 MATCH: %s -> %s | amount_delta=%.2f date_delta=%d ref=contained",
                p["payment_id"],
                candidate["invoice_id"],
                candidate["amount_delta"],
                candidate["date_delta_days"],
            )
        else:
            unmatched.append(p)
            if candidates:
                logger.debug(
                    "Layer 0 SKIP: %s had %d candidates (ambiguous), forwarding",
                    p["payment_id"],
                    len(candidates),
                )
            else:
                logger.debug(
                    "Layer 0 SKIP: %s had 0 candidates, forwarding",
                    p["payment_id"],
                )

    logger.info(
        "Layer 0 complete: %d matched, %d unmatched (forwarded to Layer 1)",
        len(matched),
        len(unmatched),
    )

    return matched, unmatched


# ── CLI runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )

    data_dir = Path(__file__).parent.parent / "data" / "generated"
    with open(data_dir / "payments.json") as f:
        payments = json.load(f)
    with open(data_dir / "invoices.json") as f:
        invoices = json.load(f)

    matched, unmatched = deterministic_match(payments, invoices)

    print()
    print(f"=== Layer 0 Results ===")
    print(f"  Matched:   {len(matched)}")
    print(f"  Unmatched: {len(unmatched)} (forwarded to Layer 1)")
    print()

    # Show matched receipts
    print("=== Matched Receipts ===")
    for m in matched[:10]:
        r = m["receipt"]
        print(
            f"  {m['payment_id']:>8} -> {m['invoice_ids'][0]:>14}  "
            f"conf={m['confidence']:.1f}  "
            f"amt_delta={r['amount_delta']:>6.2f}  "
            f"date_delta={r['date_delta_days']}d  "
            f"rule={r['rule']}"
        )
    if len(matched) > 10:
        print(f"  ... and {len(matched) - 10} more")

    print()

    # Verify against ground truth (for dev only — pipeline never reads GT)
    with open(data_dir / "ground_truth.json") as f:
        gt = json.load(f)
    gt_map = {g["payment_id"]: g for g in gt}

    correct = 0
    wrong = 0
    for m in matched:
        g = gt_map.get(m["payment_id"])
        if g and m["invoice_ids"][0] in g["invoice_ids"]:
            correct += 1
        else:
            wrong += 1
            print(f"  !! WRONG MATCH: {m['payment_id']} -> {m['invoice_ids'][0]}, expected {g['invoice_ids'] if g else 'N/A'}")

    print(f"=== Ground Truth Check (dev only) ===")
    print(f"  Correct: {correct}/{len(matched)}")
    print(f"  Wrong:   {wrong}/{len(matched)}")
    print()

    # Check that no orphans were matched
    orphan_pmts = {g["payment_id"] for g in gt if g["match_type"] == "orphan"}
    matched_pmts = {m["payment_id"] for m in matched}
    orphans_matched = orphan_pmts & matched_pmts
    print(f"  Orphans incorrectly matched: {len(orphans_matched)}")
    if orphans_matched:
        for oid in orphans_matched:
            print(f"    !! {oid}")

    # Show what categories remain unmatched
    unmatched_ids = {u["payment_id"] for u in unmatched}
    print()
    print("=== Unmatched breakdown by GT category ===")
    from collections import Counter
    cats = Counter()
    for g in gt:
        if g["payment_id"] in unmatched_ids:
            cats[g["match_type"]] += 1
    for cat, count in sorted(cats.items()):
        print(f"  {cat:<16} {count}")
