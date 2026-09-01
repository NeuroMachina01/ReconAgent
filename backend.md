# ReconAgent — Backend Specification

Read `../SKILL.md` first for the problem statement and non-negotiables. This file is the implementation contract for every backend module. Treat schemas and thresholds below as fixed unless the user explicitly changes them — do not silently substitute your own.

## data — synthetic data + ground truth

Generate two files plus one held-out answer key. Never let the matching pipeline read the answer key.

```python
class PaymentRecord(TypedDict):
    payment_id: str      # PMT-0001
    amount: float
    date: str              # ISO date
    reference: str          # raw, messy text — "NEFT-RAJESH ENT-4521"
    source: str               # NEFT / UPI / card / RTGS
    currency: str

class InvoiceRecord(TypedDict):
    invoice_id: str        # INV-2026-0447
    amount: float
    due_date: str
    vendor_or_customer: str
    description: str
    status: str               # open / partially_paid / closed

class GroundTruthMap(TypedDict):
    payment_id: str
    invoice_ids: list[str]   # empty = orphan, no correct match exists
    match_type: str            # exact | partial | multi_invoice | orphan
```

Target 50–70 invoices, 60–80 payments, with this approximate distribution — the orphan category is not optional:

| Category | % | Tests |
|---|---|---|
| Exact match | 35% | Layer 0 |
| Partial payment | 15% | Layer 2 amount-delta handling |
| Multi-invoice payment | 10% | Layer 2 multi-select |
| Garbled/typo'd reference | 15% | Layer 1 lexical signal |
| Timing offset (2–5 days) | 10% | Layer 1 date-proximity signal |
| Currency rounding (±₹1–5) | 5% | Layer 0 tolerance band |
| **True orphan** | **10%** | Escalation path — build this category first, not last |

## layer-0 — deterministic match

Pure rule matching. No LLM, no vector index. Runs first, always.

```python
def deterministic_match(payments, invoices, amount_tol=1.0, date_tol_days=2):
    matched, unmatched = [], []
    for p in payments:
        candidates = [
            inv for inv in invoices
            if abs(inv["amount"] - p["amount"]) <= amount_tol
            and abs(days_between(inv["due_date"], p["date"])) <= date_tol_days
            and normalize_ref(inv["invoice_id"]) in normalize_ref(p["reference"])
        ]
        if len(candidates) == 1:
            matched.append({"payment_id": p["payment_id"], "invoice_id": candidates[0]["invoice_id"],
                             "confidence": 1.0, "method": "deterministic"})
        else:
            unmatched.append(p)
    return matched, unmatched
```

Log the exact rule that fired for every match — this is the receipt for this layer, and it must exist for every deterministic decision, not just be inferable from the code.

## layer-1 — hybrid retrieval

Every unmatched payment is a **query**; every open invoice is a **document**. Reuse the Nexus-RAG RRF function and BM25 scorer here — see `reuse-map.md`. Do not write a new fusion algorithm from scratch.

Three signals minimum, fused with reciprocal rank fusion:

```python
def rrf_score(ranks: dict[str, int], k: int = 60) -> float:
    return sum(1.0 / (k + r) for r in ranks.values())

def retrieve_candidates(payment, invoices, top_k=5):
    lexical_ranks = bm25_rank(payment["reference"], [i["description"] for i in invoices])
    amount_ranks  = rank_by(lambda i: abs(i["amount"] - payment["amount"]))
    date_ranks    = rank_by(lambda i: abs(days_between(i["due_date"], payment["date"])))
    fused = {
        inv["invoice_id"]: rrf_score({
            "lex": lexical_ranks[inv["invoice_id"]],
            "amt": amount_ranks[inv["invoice_id"]],
            "date": date_ranks[inv["invoice_id"]],
        }) for inv in invoices
    }
    return sorted(fused.items(), key=lambda x: -x[1])[:top_k]
```

**Guardrail — implement this, it is not optional:** if the top candidate's fused score is below a floor threshold, skip Layer 2 and escalate directly. No LLM call on noise. This also saves latency/cost during the live demo.

## layer-2 — LLM reasoning + confidence

Use the Groq client wrapper from JARVIS (see `reuse-map.md`), Llama-3-8B-Instruct, structured JSON output only, temperature low.

```
SYSTEM: You are a reconciliation analyst. You are given one payment and up
to 5 candidate invoices retrieved by similarity. Decide whether the payment
matches ONE candidate, PARTIALLY matches (amount differs meaningfully),
matches MULTIPLE candidates combined, or should be ESCALATED because no
candidate is a credible match. Ground your decision only in the candidates
provided — never invent an invoice_id that is not in the candidate list.

Respond as JSON:
{
  "decision": "MATCH" | "PARTIAL_MATCH" | "MULTI_MATCH" | "ESCALATE",
  "invoice_ids": [...],
  "confidence": 0.0-1.0,
  "reasoning": "one sentence"
}
```

Include four few-shot examples in the prompt: exact match, partial payment, multi-invoice, and a genuine escalate. The escalate example is not optional — without it the model tends toward false confidence.

**Validation after every call (implement this in code, not just in the prompt):** if `invoice_ids` contains anything outside the candidate list shown, reject the response and retry once; if it fails twice, force-escalate the record.

Confidence routing table — fixed unless the user says otherwise:

| Confidence | Action |
|---|---|
| ≥ 0.85 | Auto-accept as confirmed match |
| 0.5 – 0.85 | Accept, flag "reviewed, moderate confidence" |
| < 0.5 or decision = ESCALATE | Exception list, with the model's stated reason attached |

## orchestration — LangGraph StateGraph

Reuse the FastAPI + StateGraph skeleton from JARVIS. New nodes, same wiring pattern.

```python
class ReconState(TypedDict):
    payments: list[PaymentRecord]
    invoices: list[InvoiceRecord]
    deterministic_matches: list[dict]
    unmatched_queue: list[PaymentRecord]
    candidates: dict[str, list]
    llm_decisions: list[dict]
    exceptions: list[dict]
    metrics: dict

graph = StateGraph(ReconState)
graph.add_node("deterministic_match", deterministic_match_node)
graph.add_node("retrieve", retrieve_node)
graph.add_node("llm_reason", llm_reason_node)
graph.add_node("audit_report", audit_node)

graph.add_edge("deterministic_match", "retrieve")
graph.add_conditional_edges("retrieve", route_on_candidates,
    {"has_candidates": "llm_reason", "no_candidates": "audit_report"})
graph.add_conditional_edges("llm_reason", route_on_decision,
    {"resolved": "audit_report", "escalate": "audit_report"})
```

Every node must write to `metrics` and `exceptions` as a side effect of running — the audit trail is produced by the graph executing, not assembled afterward from scattered state.

## observability — logging, groundedness, calibration

One JSON log line per payment per layer it passes through:

```json
{"payment_id": "PMT-0042", "layer": "retrieval",
 "candidates": [{"invoice_id": "INV-2026-0447", "lexical_rank": 1, "amount_rank": 2, "date_rank": 1, "rrf_score": 0.041}],
 "timestamp": "..."}

{"payment_id": "PMT-0042", "layer": "llm_reasoning",
 "candidates_shown": ["INV-2026-0447", "INV-2026-0512"],
 "decision": "PARTIAL_MATCH", "invoice_ids": ["INV-2026-0447"],
 "confidence": 0.78, "reasoning": "...",
 "model": "llama-3-8b-instruct", "latency_ms": 340}
```

**Faithfulness check (implement this, mirrors AlphaRAG's grounding pattern):** for every MATCH/PARTIAL_MATCH, programmatically verify the stated reasoning is actually true against the raw data — if the reasoning claims "date matches within 2 days," check that against the actual dates. Flag reasoning that doesn't check out. This catches hallucinated justification, which is a different failure mode than a hallucinated invoice_id and must be checked separately.

**Calibration check:** after scoring against ground truth, verify that an 0.85-confidence decision is actually correct roughly 85% of the time. Report this as a simple predicted-vs-actual table or a Brier score. If confidence numbers don't calibrate, say so in the report rather than hiding it — that honesty is itself part of THE BAR.

## api

```
POST /reconcile/batch                          upload payments.json + invoices.json, returns job_id
GET  /reconcile/{job_id}/progress               for polling fallback if SSE isn't implemented
GET  /reconcile/{job_id}/results                matched pairs, confidence, method per row
GET  /reconcile/{job_id}/metrics                precision/recall/confusion matrix/exception counts
GET  /reconcile/{job_id}/trace/{payment_id}     full reasoning trace for one payment — the "receipt"
```

`/trace/{payment_id}` is the highest-value endpoint in the whole system — it is what gets clicked on during judging. Build it correctly before spending time on anything cosmetic.

## config

`GROQ_API_KEY` and any index/DB connection strings come from environment variables only. Never commit them, never inline them in a request. If using in-memory Qdrant or a similar index, document explicitly that it resets on process restart.

## evaluation

Score every pipeline output against `GroundTruthMap`, never the reverse. Report:
- Precision / recall / F1, broken out per layer (deterministic vs. retrieval+LLM)
- Confusion matrix: matched-correct, matched-wrong, escalated-correctly (true orphan), escalated-unnecessarily, missed-should-have-escalated
- One explicit sentence in the report noting that a wrong auto-match is worse than an unresolved exception, because it silently corrupts the books — this directly answers the "false-positive cost" language in THE BAR
