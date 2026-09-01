"""
ReconAgent - Layer 1: Hybrid Retrieval (Module 3)

Every unmatched payment is a **query**; every open invoice is a **document**.
Three independent signals, fused via Reciprocal Rank Fusion (RRF):
  1. Lexical similarity  — BM25 over payment reference vs invoice description
  2. Amount proximity    — ranked by |invoice.amount - payment.amount|
  3. Date proximity      — ranked by |days_between(invoice.due_date, payment.date)|

RRF fusion function and BM25 scorer ported from Nexus-RAG (see reuse-map.md).
Hybrid retrieval scaffolding adapted from AlphaRAG-10K-Engine, re-pointed from
filing chunks to invoice description/reference fields.

Guardrail: if the top candidate's fused score is below a floor threshold,
skip Layer 2 and escalate directly — no LLM call on noise.
"""

from __future__ import annotations

import math
import re
import logging
from collections import Counter
from datetime import date
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── BM25 Scorer (ported from Nexus-RAG) ─────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25:
    """
    Okapi BM25 scorer. Ported from Nexus-RAG's BM25 implementation,
    applied to invoice description text instead of document chunks.
    """

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[list[str]] = [_tokenize(doc) for doc in documents]
        self.doc_count = len(self.corpus)
        self.avg_dl = sum(len(d) for d in self.corpus) / max(self.doc_count, 1)

        # Document frequency for each term
        self.df: dict[str, int] = {}
        for doc_tokens in self.corpus:
            for term in set(doc_tokens):
                self.df[term] = self.df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        """Inverse document frequency with smoothing."""
        df = self.df.get(term, 0)
        return math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, doc_idx: int) -> float:
        """Score a single document against a query."""
        query_terms = _tokenize(query)
        doc_tokens = self.corpus[doc_idx]
        doc_len = len(doc_tokens)
        tf_counter = Counter(doc_tokens)

        score = 0.0
        for term in query_terms:
            tf = tf_counter.get(term, 0)
            idf = self._idf(term)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_dl)
            score += idf * (numerator / denominator)
        return score

    def rank(self, query: str) -> list[tuple[int, float]]:
        """
        Rank all documents by BM25 score for a query.
        Returns list of (doc_idx, score) sorted descending.
        """
        scores = [(i, self.score(query, i)) for i in range(self.doc_count)]
        return sorted(scores, key=lambda x: -x[1])


# ── RRF Fusion (ported from Nexus-RAG) ───────────────────────────────

def rrf_score(ranks: dict[str, int], k: int = 60) -> float:
    """
    Reciprocal Rank Fusion score.
    Ported directly from Nexus-RAG. Inputs changed from original ranked
    lists to three new ones: lexical rank, amount-proximity rank,
    date-proximity rank.
    """
    return sum(1.0 / (k + r) for r in ranks.values())


# ── Ranking helpers ──────────────────────────────────────────────────

def _rank_by_key(
    invoices: list[dict],
    key_fn: Callable[[dict], float],
) -> dict[str, int]:
    """
    Rank invoices by a numeric key (ascending — smaller = better = rank 1).
    Returns {invoice_id: rank} where rank is 1-based.
    """
    scored = [(inv["invoice_id"], key_fn(inv)) for inv in invoices]
    scored.sort(key=lambda x: x[1])
    return {inv_id: rank + 1 for rank, (inv_id, _) in enumerate(scored)}


def _days_between(date_a: str, date_b: str) -> int:
    """Absolute day difference between two ISO date strings."""
    return abs((date.fromisoformat(date_a) - date.fromisoformat(date_b)).days)


def _ref_id_similarity(ref: str, invoice_id: str) -> float:
    """
    Measure how similar a payment reference is to an invoice_id.
    Uses normalized longest common subsequence — catches garbled/truncated IDs.
    Returns 0.0–1.0 (higher = more similar).
    """
    ref_norm = re.sub(r"[^a-z0-9]", "", ref.lower())
    id_norm = re.sub(r"[^a-z0-9]", "", invoice_id.lower())

    if not id_norm:
        return 0.0

    # Longest common subsequence length
    m, n = len(id_norm), len(ref_norm)
    # Optimized 2-row DP
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if id_norm[i - 1] == ref_norm[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)

    lcs_len = prev[n] if prev else 0
    return lcs_len / m  # Normalize by invoice_id length


def bm25_rank(
    query: str,
    invoices: list[dict],
    bm25_index: BM25,
) -> dict[str, int]:
    """
    Rank invoices by BM25 score of query against invoice descriptions.
    Returns {invoice_id: rank} where rank is 1-based.
    """
    ranked = bm25_index.rank(query)
    result = {}
    for rank_pos, (doc_idx, _score) in enumerate(ranked):
        result[invoices[doc_idx]["invoice_id"]] = rank_pos + 1
    return result


def ref_id_rank(
    payment_ref: str,
    invoices: list[dict],
) -> dict[str, int]:
    """
    Rank invoices by how similar the payment reference is to each invoice_id.
    Higher similarity = better rank (rank 1).
    """
    scored = [
        (inv["invoice_id"], _ref_id_similarity(payment_ref, inv["invoice_id"]))
        for inv in invoices
    ]
    # Sort descending by similarity (higher = better), use invoice_id as tiebreaker
    scored.sort(key=lambda x: (-x[1], x[0]))
    return {inv_id: rank + 1 for rank, (inv_id, _) in enumerate(scored)}


# ── Main retrieval function ──────────────────────────────────────────

# Floor threshold: if the best RRF score is below this, skip LLM and
# escalate directly. With 4 signals and k=60, a perfectly-ranked #1 in
# all four signals scores 4 * (1/61) ~ 0.0656. We use 0.048 as the floor —
# roughly a candidate averaging rank ~23 across all 4 signals: noise.
RRF_FLOOR_THRESHOLD = 0.048


def retrieve_candidates(
    payment: dict,
    invoices: list[dict],
    bm25_index: BM25,
    top_k: int = 5,
    rrf_floor: float = RRF_FLOOR_THRESHOLD,
) -> dict[str, Any]:
    """
    Retrieve top-k invoice candidates for a single unmatched payment.

    Four signals fused via RRF:
      1. Lexical: BM25(payment.reference, invoice.description)
      2. Amount proximity: |invoice.amount - payment.amount|
      3. Date proximity: |days_between(invoice.due_date, payment.date)|
      4. Reference-ID similarity: LCS of payment reference vs invoice_id

    Returns a dict with:
      - "candidates": list of candidate dicts with per-signal ranks and fused score
      - "escalate_direct": True if top score < rrf_floor (skip Layer 2)
      - "payment_id": the payment being queried
    """
    # Signal 1: Lexical (BM25)
    lex_ranks = bm25_rank(payment["reference"], invoices, bm25_index)

    # Signal 2: Amount proximity
    amt_ranks = _rank_by_key(
        invoices,
        lambda inv: abs(inv["amount"] - payment["amount"]),
    )

    # Signal 3: Date proximity
    date_ranks = _rank_by_key(
        invoices,
        lambda inv: _days_between(inv["due_date"], payment["date"]),
    )

    # Signal 4: Reference-ID similarity (catches garbled/partial invoice IDs in ref)
    rid_ranks = ref_id_rank(payment["reference"], invoices)

    # Fuse with RRF (4 signals)
    fused: dict[str, float] = {}
    for inv in invoices:
        inv_id = inv["invoice_id"]
        fused[inv_id] = rrf_score({
            "lex": lex_ranks[inv_id],
            "amt": amt_ranks[inv_id],
            "date": date_ranks[inv_id],
            "ref_id": rid_ranks[inv_id],
        })

    # Sort descending by fused score, take top_k
    sorted_candidates = sorted(fused.items(), key=lambda x: -x[1])[:top_k]

    # Build candidate detail list
    candidates = []
    for inv_id, score in sorted_candidates:
        inv = next(i for i in invoices if i["invoice_id"] == inv_id)
        candidates.append({
            "invoice_id": inv_id,
            "rrf_score": round(score, 6),
            "lexical_rank": lex_ranks[inv_id],
            "amount_rank": amt_ranks[inv_id],
            "date_rank": date_ranks[inv_id],
            "ref_id_rank": rid_ranks[inv_id],
            "amount_delta": round(abs(inv["amount"] - payment["amount"]), 2),
            "date_delta_days": _days_between(inv["due_date"], payment["date"]),
        })

    # Guardrail: if top score < floor, escalate directly — no LLM on noise
    top_score = candidates[0]["rrf_score"] if candidates else 0.0
    escalate_direct = top_score < rrf_floor

    if escalate_direct:
        logger.info(
            "Layer 1 ESCALATE-DIRECT: %s | top_rrf=%.6f < floor=%.4f, skipping LLM",
            payment["payment_id"], top_score, rrf_floor,
        )
    else:
        logger.info(
            "Layer 1 CANDIDATES: %s | top=%s (rrf=%.6f) | %d candidates",
            payment["payment_id"],
            candidates[0]["invoice_id"] if candidates else "none",
            top_score,
            len(candidates),
        )

    return {
        "payment_id": payment["payment_id"],
        "candidates": candidates,
        "escalate_direct": escalate_direct,
        "top_rrf_score": round(top_score, 6),
        "rrf_floor_threshold": rrf_floor,
    }


def retrieve_all(
    unmatched_payments: list[dict],
    invoices: list[dict],
    top_k: int = 5,
    rrf_floor: float = RRF_FLOOR_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """
    Run retrieval for all unmatched payments.

    Returns:
        (candidates_for_llm, direct_escalations)
        - candidates_for_llm: retrieval results where top score >= floor
        - direct_escalations: retrieval results where top score < floor
          (these skip Layer 2 entirely)
    """
    # Build BM25 index once over all invoice descriptions
    descriptions = [inv["description"] for inv in invoices]
    bm25_index = BM25(descriptions)

    candidates_for_llm: list[dict] = []
    direct_escalations: list[dict] = []

    for payment in unmatched_payments:
        result = retrieve_candidates(
            payment, invoices, bm25_index, top_k=top_k, rrf_floor=rrf_floor,
        )
        if result["escalate_direct"]:
            direct_escalations.append(result)
        else:
            candidates_for_llm.append(result)

    logger.info(
        "Layer 1 complete: %d -> LLM, %d -> direct escalation",
        len(candidates_for_llm),
        len(direct_escalations),
    )

    return candidates_for_llm, direct_escalations


# ── CLI runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path
    from backend.layers.deterministic import deterministic_match

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

    # Run Layer 0 first
    print("=== Layer 0 ===")
    l0_matched, l0_unmatched = deterministic_match(payments, invoices)
    print(f"  L0 matched: {len(l0_matched)}, forwarded: {len(l0_unmatched)}")
    print()

    # Run Layer 1 on unmatched
    print("=== Layer 1 ===")
    for_llm, escalated = retrieve_all(l0_unmatched, invoices)
    print()
    print(f"  Candidates for LLM:   {len(for_llm)}")
    print(f"  Direct escalations:   {len(escalated)}")
    print()

    # Show top candidates for first 5 payments headed to LLM
    print("=== Sample Candidates (for LLM) ===")
    for result in for_llm[:5]:
        pid = result["payment_id"]
        print(f"  {pid}:")
        for c in result["candidates"][:3]:
            print(
                f"    {c['invoice_id']:>14}  rrf={c['rrf_score']:.6f}  "
                f"lex_r={c['lexical_rank']:>2}  amt_r={c['amount_rank']:>2}  "
                f"date_r={c['date_rank']:>2}  ref_r={c['ref_id_rank']:>2}  "
                f"amt_delta={c['amount_delta']:>12.2f}  "
                f"date_delta={c['date_delta_days']}d"
            )
        print()

    # Show direct escalations
    if escalated:
        print("=== Direct Escalations (skipping LLM) ===")
        for result in escalated:
            pid = result["payment_id"]
            top = result["candidates"][0] if result["candidates"] else None
            if top:
                print(
                    f"  {pid}  top={top['invoice_id']} rrf={top['rrf_score']:.6f} "
                    f"< floor={result['rrf_floor_threshold']}"
                )
            else:
                print(f"  {pid}  no candidates at all")
        print()

    # Dev-only: check against ground truth
    with open(data_dir / "ground_truth.json") as f:
        gt = json.load(f)
    gt_map = {g["payment_id"]: g for g in gt}

    print("=== Ground Truth Check (dev only) ===")

    # For LLM candidates: is the correct invoice in the top-k?
    correct_in_topk = 0
    total_non_orphan = 0
    for result in for_llm:
        g = gt_map.get(result["payment_id"])
        if not g:
            continue
        if g["match_type"] == "orphan":
            continue
        total_non_orphan += 1
        candidate_ids = {c["invoice_id"] for c in result["candidates"]}
        if any(inv_id in candidate_ids for inv_id in g["invoice_ids"]):
            correct_in_topk += 1

    print(f"  Correct invoice in top-{5} candidates: {correct_in_topk}/{total_non_orphan}")

    # For direct escalations: are they actually orphans?
    orphan_correct = 0
    orphan_wrong = 0
    for result in escalated:
        g = gt_map.get(result["payment_id"])
        if g and g["match_type"] == "orphan":
            orphan_correct += 1
        else:
            orphan_wrong += 1
            actual = g["match_type"] if g else "unknown"
            print(f"  !! Wrongly escalated: {result['payment_id']} (actual: {actual})")

    print(f"  Direct escalations that are real orphans: {orphan_correct}/{len(escalated)}")
    if orphan_wrong:
        print(f"  !! Wrongly escalated non-orphans: {orphan_wrong}")
