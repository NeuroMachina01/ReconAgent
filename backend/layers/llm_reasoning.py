"""
ReconAgent - Layer 2: LLM Reasoning + Confidence (Module 4)

Structured LLM decisions over candidates retrieved by Layer 1.
Uses the Groq client wrapper (ported from JARVIS per reuse-map.md) with
Llama-3-8B-Instruct, structured JSON output, low temperature.

Decisions: MATCH | PARTIAL_MATCH | MULTI_MATCH | ESCALATE
Each with confidence score and grounded reasoning.

Self-correction/retry pattern ported from AlphaRAG-10K-Engine:
  - If invoice_ids contains anything outside the candidate list → reject + retry
  - If it fails twice → force-escalate
  (Non-negotiable requirement #2: programmatic validation, not just prompting)

Confidence routing (fixed per backend.md):
  >= 0.85       → auto-accept as confirmed match
  0.5 - 0.85   → accept, flag "reviewed, moderate confidence"
  < 0.5 or ESCALATE → exception list with model's stated reason
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Groq Client Wrapper (ported from JARVIS) ────────────────────────

_groq_client = None

def _get_groq_client():
    """
    Lazy-init Groq client. Ported from JARVIS's Groq API client wrapper.
    API key from env var only — never hardcoded (non-negotiable #6).
    """
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set. "
                "Set it before running Layer 2. Never hardcode API keys."
            )
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ── System prompt + few-shot examples ────────────────────────────────

SYSTEM_PROMPT = """You are a reconciliation analyst. You are given one payment and up to 5 candidate invoices retrieved by similarity. Decide whether the payment matches ONE candidate, PARTIALLY matches (amount differs meaningfully), matches MULTIPLE candidates combined, or should be ESCALATED because no candidate is a credible match. Ground your decision only in the candidates provided — never invent an invoice_id that is not in the candidate list.

Respond as JSON:
{
  "decision": "MATCH" | "PARTIAL_MATCH" | "MULTI_MATCH" | "ESCALATE",
  "invoice_ids": [...],
  "confidence": 0.0-1.0,
  "reasoning": "one sentence"
}"""

# Four few-shot examples (all required per spec — escalate example is NOT optional)
FEW_SHOT_EXAMPLES = [
    # 1. Exact match
    {
        "role": "user",
        "content": json.dumps({
            "payment": {"payment_id": "PMT-EX01", "amount": 15000.00, "date": "2026-07-15", "reference": "NEFT-ACME-INV-2026-0100", "source": "NEFT", "currency": "INR"},
            "candidates": [
                {"invoice_id": "INV-2026-0100", "amount": 15000.00, "due_date": "2026-07-14", "vendor_or_customer": "Acme Corp", "description": "Monthly consulting", "rrf_score": 0.062, "amount_delta": 0.00, "date_delta_days": 1},
                {"invoice_id": "INV-2026-0205", "amount": 14800.00, "due_date": "2026-07-20", "vendor_or_customer": "Beta Ltd", "description": "Office supplies", "rrf_score": 0.048, "amount_delta": 200.00, "date_delta_days": 5},
            ]
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"decision": "MATCH", "invoice_ids": ["INV-2026-0100"], "confidence": 0.95, "reasoning": "Amount matches exactly, date is within 1 day, and the invoice ID appears in the payment reference."}),
    },
    # 2. Partial payment
    {
        "role": "user",
        "content": json.dumps({
            "payment": {"payment_id": "PMT-EX02", "amount": 42000.00, "date": "2026-06-20", "reference": "UPI-DELTA-INV-2026-0300", "source": "UPI", "currency": "INR"},
            "candidates": [
                {"invoice_id": "INV-2026-0300", "amount": 60000.00, "due_date": "2026-06-18", "vendor_or_customer": "Delta Inc", "description": "Q2 retainer", "rrf_score": 0.058, "amount_delta": 18000.00, "date_delta_days": 2},
                {"invoice_id": "INV-2026-0301", "amount": 42500.00, "due_date": "2026-07-01", "vendor_or_customer": "Echo Ltd", "description": "Hardware order", "rrf_score": 0.045, "amount_delta": 500.00, "date_delta_days": 11},
            ]
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"decision": "PARTIAL_MATCH", "invoice_ids": ["INV-2026-0300"], "confidence": 0.82, "reasoning": "Payment of 42000 is 70% of invoice 60000; the invoice ID is in the reference and dates align within 2 days, indicating a partial payment."}),
    },
    # 3. Multi-invoice
    {
        "role": "user",
        "content": json.dumps({
            "payment": {"payment_id": "PMT-EX03", "amount": 75000.00, "date": "2026-08-05", "reference": "RTGS-FOXTROT-MULTI-AUG26", "source": "RTGS", "currency": "INR"},
            "candidates": [
                {"invoice_id": "INV-2026-0400", "amount": 30000.00, "due_date": "2026-08-04", "vendor_or_customer": "Foxtrot Co", "description": "Batch A materials", "rrf_score": 0.055, "amount_delta": 45000.00, "date_delta_days": 1},
                {"invoice_id": "INV-2026-0401", "amount": 25000.00, "due_date": "2026-08-04", "vendor_or_customer": "Foxtrot Co", "description": "Batch B materials", "rrf_score": 0.053, "amount_delta": 50000.00, "date_delta_days": 1},
                {"invoice_id": "INV-2026-0402", "amount": 20000.00, "due_date": "2026-08-04", "vendor_or_customer": "Foxtrot Co", "description": "Batch C materials", "rrf_score": 0.051, "amount_delta": 55000.00, "date_delta_days": 1},
            ]
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"decision": "MULTI_MATCH", "invoice_ids": ["INV-2026-0400", "INV-2026-0401", "INV-2026-0402"], "confidence": 0.88, "reasoning": "Combined invoice total (30000+25000+20000=75000) exactly matches the payment amount, all from the same vendor with the same date."}),
    },
    # 4. Genuine escalate (NOT optional per spec)
    {
        "role": "user",
        "content": json.dumps({
            "payment": {"payment_id": "PMT-EX04", "amount": 125000.00, "date": "2026-07-10", "reference": "NEFT-UNKNOWN-REF-9999", "source": "NEFT", "currency": "INR"},
            "candidates": [
                {"invoice_id": "INV-2026-0500", "amount": 8000.00, "due_date": "2026-06-01", "vendor_or_customer": "Golf Ltd", "description": "Stationery", "rrf_score": 0.042, "amount_delta": 117000.00, "date_delta_days": 39},
                {"invoice_id": "INV-2026-0501", "amount": 220000.00, "due_date": "2026-08-15", "vendor_or_customer": "Hotel Corp", "description": "Annual contract", "rrf_score": 0.040, "amount_delta": 95000.00, "date_delta_days": 36},
            ]
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"decision": "ESCALATE", "invoice_ids": [], "confidence": 0.15, "reasoning": "No candidate has a credible amount match or date proximity; the reference does not correspond to any known invoice. This payment requires manual review."}),
    },
]


# ── LLM call with validation + retry (AlphaRAG retry pattern) ────────

def _build_user_message(payment: dict, candidates: list[dict]) -> str:
    """Build the user message with payment and candidate details for the LLM."""
    # Include the fields the LLM needs to reason about
    candidate_summaries = []
    for c in candidates:
        candidate_summaries.append({
            "invoice_id": c["invoice_id"],
            "amount": c.get("_invoice_amount", 0),
            "due_date": c.get("_invoice_due_date", ""),
            "vendor_or_customer": c.get("_invoice_vendor", ""),
            "description": c.get("_invoice_description", ""),
            "rrf_score": c["rrf_score"],
            "amount_delta": c["amount_delta"],
            "date_delta_days": c["date_delta_days"],
        })

    return json.dumps({
        "payment": {
            "payment_id": payment["payment_id"],
            "amount": payment["amount"],
            "date": payment["date"],
            "reference": payment["reference"],
            "source": payment["source"],
            "currency": payment["currency"],
        },
        "candidates": candidate_summaries,
    })


def _parse_llm_response(raw: str) -> dict | None:
    """Try to parse the LLM's JSON response. Returns None if unparseable."""
    import re
    # Strip <think>...</think> blocks from reasoning models
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    print(f"RAW TEXT: {text}")
    
    # Extract JSON object even if LLM chatters before/after
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned unparseable JSON: %s", text[:200])
        return None

    # Validate required fields
    required = {"decision", "invoice_ids", "confidence", "reasoning"}
    if not required.issubset(parsed.keys()):
        logger.warning("LLM response missing fields: %s", required - parsed.keys())
        return None

    valid_decisions = {"MATCH", "PARTIAL_MATCH", "MULTI_MATCH", "ESCALATE"}
    if parsed["decision"] not in valid_decisions:
        logger.warning("LLM returned invalid decision: %s", parsed["decision"])
        return None

    return parsed


def _validate_invoice_ids(
    response: dict,
    valid_ids: set[str],
) -> bool:
    """
    Programmatic validation (non-negotiable #2):
    Every invoice_id in the response MUST be in the candidate list.
    Returns True if valid, False if any ID is outside the candidates.
    """
    if response["decision"] == "ESCALATE":
        # Escalate can have empty invoice_ids
        return True

    for inv_id in response["invoice_ids"]:
        if inv_id not in valid_ids:
            logger.warning(
                "VALIDATION FAIL: LLM returned invoice_id '%s' not in candidates %s",
                inv_id, valid_ids,
            )
            return False

    if not response["invoice_ids"]:
        logger.warning("VALIDATION FAIL: Non-ESCALATE decision with empty invoice_ids")
        return False

    return True


def llm_reason(
    payment: dict,
    candidates: list[dict],
    invoices: list[dict],
    max_retries: int = 2,
) -> dict:
    """
    Run LLM reasoning over candidates for a single payment.

    Implements the AlphaRAG self-correction/retry pattern:
      - Call LLM with structured prompt + few-shot examples
      - Validate invoice_ids are in candidate list (programmatic, not just prompted)
      - If validation fails, retry with correction prompt
      - If fails twice, force-escalate

    Returns a decision dict with routing information.
    """
    client = _get_groq_client()
    valid_ids = {c["invoice_id"] for c in candidates}
    inv_map = {i["invoice_id"]: i for i in invoices}

    # Enrich candidates with invoice details for the LLM
    enriched_candidates = []
    for c in candidates:
        inv = inv_map.get(c["invoice_id"], {})
        enriched = dict(c)
        enriched["_invoice_amount"] = inv.get("amount", 0)
        enriched["_invoice_due_date"] = inv.get("due_date", "")
        enriched["_invoice_vendor"] = inv.get("vendor_or_customer", "")
        enriched["_invoice_description"] = inv.get("description", "")
        enriched_candidates.append(enriched)

    user_message = _build_user_message(payment, enriched_candidates)

    for attempt in range(max_retries):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *FEW_SHOT_EXAMPLES,
            {"role": "user", "content": user_message},
        ]

        # Add correction prompt on retry
        if attempt > 0:
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response contained invoice_ids not in the candidate list. "
                    f"The ONLY valid invoice_ids are: {sorted(valid_ids)}. "
                    f"Please respond again with only IDs from this list, or ESCALATE if none match."
                ),
            })

        start_ms = time.time()
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            )
            latency_ms = int((time.time() - start_ms) * 1000)
            raw_content = completion.choices[0].message.content
        except Exception as e:
            latency_ms = int((time.time() - start_ms) * 1000)
            logger.error("Groq API error for %s: %s", payment["payment_id"], e)
            continue

        parsed = _parse_llm_response(raw_content)
        if parsed is None:
            logger.warning(
                "Attempt %d: unparseable response for %s",
                attempt + 1, payment["payment_id"],
            )
            continue

        if _validate_invoice_ids(parsed, valid_ids):
            # Valid response — apply confidence routing
            confidence = float(parsed.get("confidence", 0))
            decision = parsed["decision"]

            if decision == "ESCALATE" or confidence < 0.5:
                status = "exception"
            elif confidence >= 0.85:
                status = "confirmed"
            else:
                status = "review"

            result = {
                "payment_id": payment["payment_id"],
                "decision": decision,
                "invoice_ids": parsed["invoice_ids"],
                "confidence": confidence,
                "reasoning": parsed["reasoning"],
                "status": status,
                "method": "llm_reasoning",
                "model": "openai/gpt-oss-120b",
                "latency_ms": latency_ms,
                "attempts": attempt + 1,
                "candidates_shown": [c["invoice_id"] for c in candidates],
            }

            logger.info(
                "Layer 2 %s: %s -> %s | conf=%.2f status=%s | %dms",
                decision, payment["payment_id"],
                parsed["invoice_ids"], confidence, status, latency_ms,
            )
            return result
        else:
            logger.warning(
                "Attempt %d: invoice_id validation failed for %s, retrying",
                attempt + 1, payment["payment_id"],
            )

    # All retries exhausted — force-escalate (non-negotiable #2)
    logger.warning(
        "Layer 2 FORCE-ESCALATE: %s after %d failed attempts",
        payment["payment_id"], max_retries,
    )
    return {
        "payment_id": payment["payment_id"],
        "decision": "ESCALATE",
        "invoice_ids": [],
        "confidence": 0.0,
        "reasoning": "Force-escalated: LLM failed validation after max retries",
        "status": "exception",
        "method": "llm_reasoning_force_escalate",
        "model": "openai/gpt-oss-120b",
        "latency_ms": 0,
        "attempts": max_retries,
        "candidates_shown": [c["invoice_id"] for c in candidates],
    }


# ── Confidence routing ───────────────────────────────────────────────

def route_decision(decision: dict) -> str:
    """
    Apply confidence routing table (fixed per backend.md):
      >= 0.85       -> "confirmed" (auto-accept)
      0.5 - 0.85   -> "review" (flag moderate confidence)
      < 0.5 / ESC  -> "exception"
    """
    return decision["status"]


# ── Batch processing ─────────────────────────────────────────────────

def reason_all(
    candidates_for_llm: list[dict],
    invoices: list[dict],
    payments: list[dict],
    metrics_ref: dict = None,
) -> tuple[list[dict], list[dict]]:
    """
    Run LLM reasoning for all payments with candidates.

    Returns:
        (resolved, exceptions)
        - resolved: decisions that are confirmed or review
        - exceptions: decisions that are exceptions (escalated)
    """
    pmt_map = {p["payment_id"]: p for p in payments}
    resolved = []
    exceptions = []

    for retrieval_result in candidates_for_llm:
        pid = retrieval_result["payment_id"]
        payment = pmt_map[pid]
        candidates = retrieval_result["candidates"]

        decision = llm_reason(payment, candidates, invoices)

        if decision["status"] == "exception":
            exceptions.append(decision)
            if metrics_ref is not None:
                metrics_ref["layer2_exceptions"] = len(exceptions)
                metrics_ref["total_exceptions"] = metrics_ref.get("total_exceptions", 0) + 1
        else:
            resolved.append(decision)

        # Throttling to bypass Groq Free Tier 30 RPM limit
        import time
        time.sleep(2.1)
            if metrics_ref is not None:
                metrics_ref["layer2_resolved"] = len(resolved)
                metrics_ref["total_reconciled"] = metrics_ref.get("total_reconciled", 0) + 1

    logger.info(
        "Layer 2 complete: %d resolved, %d exceptions",
        len(resolved), len(exceptions),
    )
    return resolved, exceptions


# ── CLI runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path
    from backend.layers.deterministic import deterministic_match
    from backend.layers.retrieval import retrieve_all

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

    # Layer 0
    print("=== Layer 0 ===")
    l0_matched, l0_unmatched = deterministic_match(payments, invoices)
    print(f"  Matched: {len(l0_matched)}, Forwarded: {len(l0_unmatched)}")
    print()

    # Layer 1
    print("=== Layer 1 ===")
    for_llm, direct_escalations = retrieve_all(l0_unmatched, invoices)
    print(f"  Candidates for LLM: {len(for_llm)}")
    print(f"  Direct escalations: {len(direct_escalations)}")
    print()

    # Layer 2 (Sample first 5 to avoid API rate limits)
    print("=== Layer 2 ===")
    resolved, exceptions = reason_all(for_llm[:5], invoices, payments)
    print()
    print(f"  Resolved: {len(resolved)}")
    print(f"  Exceptions: {len(exceptions)}")
    print()

    # Show results by status
    confirmed = [d for d in resolved if d["status"] == "confirmed"]
    review = [d for d in resolved if d["status"] == "review"]
    print(f"  Confirmed (>=0.85): {len(confirmed)}")
    print(f"  Review (0.5-0.85):  {len(review)}")
    print(f"  Exception (<0.5):   {len(exceptions)}")
    print()

    # Show sample decisions
    print("=== Sample Decisions ===")
    for d in (resolved + exceptions)[:8]:
        print(
            f"  {d['payment_id']:>8}  {d['decision']:<14}  "
            f"inv={d['invoice_ids']}  conf={d['confidence']:.2f}  "
            f"status={d['status']}  {d['latency_ms']}ms"
        )
        print(f"           reasoning: {d['reasoning']}")
        print()

    # Ground truth check
    with open(data_dir / "ground_truth.json") as f:
        gt = json.load(f)
    gt_map = {g["payment_id"]: g for g in gt}

    print("=== Ground Truth Check (dev only) ===")
    correct = 0
    wrong = 0
    correct_escalations = 0
    wrong_escalations = 0

    all_decisions = resolved + exceptions
    for d in all_decisions:
        g = gt_map.get(d["payment_id"])
        if not g:
            continue

        if g["match_type"] == "orphan":
            if d["decision"] == "ESCALATE":
                correct_escalations += 1
            else:
                wrong += 1
                print(f"  !! Orphan not escalated: {d['payment_id']} -> {d['decision']}")
        else:
            if d["decision"] == "ESCALATE":
                wrong_escalations += 1
            else:
                # Check if selected invoice_ids are correct
                gt_ids = set(g["invoice_ids"])
                sel_ids = set(d["invoice_ids"])
                if sel_ids & gt_ids:  # At least one correct
                    correct += 1
                else:
                    wrong += 1
                    print(f"  !! Wrong: {d['payment_id']} selected={d['invoice_ids']} expected={g['invoice_ids']}")

    print(f"  Correct matches: {correct}")
    print(f"  Correct escalations (orphans): {correct_escalations}")
    print(f"  Wrong matches: {wrong}")
    print(f"  Unnecessary escalations: {wrong_escalations}")
