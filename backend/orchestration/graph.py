"""
ReconAgent - Orchestration (Module 5)

LangGraph StateGraph definition connecting Layer 0, Layer 1, and Layer 2.
"""

import operator
from typing import TypedDict, Annotated, Any
from langgraph.graph import StateGraph, END

from backend.layers.deterministic import deterministic_match
from backend.layers.retrieval import retrieve_all
from backend.layers.llm_reasoning import reason_all
import logging

logger = logging.getLogger(__name__)

class ReconState(TypedDict):
    payments: list[dict]
    invoices: list[dict]
    deterministic_matches: list[dict]
    unmatched_queue: list[dict]
    candidates: dict[str, list]
    llm_decisions: list[dict]
    exceptions: Annotated[list[dict], operator.add]
    metrics: dict

# ── Nodes ─────────────────────────────────────────────────────────────

def deterministic_match_node(state: ReconState) -> dict:
    """Layer 0 node."""
    logger.info("Executing deterministic_match_node")
    payments = state["payments"]
    invoices = state["invoices"]
    
    matched, unmatched = deterministic_match(payments, invoices)
    
    metrics = state.get("metrics", {})
    metrics["layer0_matched"] = len(matched)
    metrics["layer0_unmatched"] = len(unmatched)
    
    return {
        "deterministic_matches": matched,
        "unmatched_queue": unmatched,
        "metrics": metrics
    }

from backend.observability.logger import StructuredLogger

_retrieval_logger = StructuredLogger(log_file="recon_audit.jsonl")

def retrieve_node(state: ReconState) -> dict:
    """Layer 1 node."""
    logger.info("Executing retrieve_node")
    unmatched = state["unmatched_queue"]
    invoices = state["invoices"]
    
    for_llm, escalations = retrieve_all(unmatched, invoices)
    
    # Map for_llm to the dict[str, list] expected by spec
    candidates = {}
    for r in for_llm:
        pid = r["payment_id"]
        cands = r["candidates"]
        candidates[pid] = cands
        
        # Log retrieval structured log
        _retrieval_logger.log_retrieval(pid, cands)

    
    # Add to metrics
    metrics = state.get("metrics", {})
    metrics["layer1_for_llm"] = len(for_llm)
    metrics["layer1_escalated"] = len(escalations)
    
    return {
        "candidates": candidates,
        # Only output exceptions if there are any, because of operator.add
        "exceptions": escalations, 
        "metrics": metrics
    }

def llm_reason_node(state: ReconState) -> dict:
    """Layer 2 node."""
    logger.info("Executing llm_reason_node")
    # Transform dict[str, list] back to list[dict] shape expected by reason_all
    candidates_dict = state["candidates"]
    for_llm = [
        {"payment_id": pid, "candidates": cands}
        for pid, cands in candidates_dict.items()
    ]
    
    invoices = state["invoices"]
    payments = state["payments"]
    
    resolved, exceptions = reason_all(for_llm, invoices, payments, state.get("metrics"))
    
    metrics = state.get("metrics", {})
    metrics["layer2_resolved"] = len(resolved)
    metrics["layer2_exceptions"] = len(exceptions)
    
    return {
        "llm_decisions": resolved,
        "exceptions": exceptions,
        "metrics": metrics
    }

from backend.observability.grounding import check_groundedness
from backend.observability.logger import StructuredLogger

_logger = StructuredLogger(log_file="recon_audit.jsonl")

def audit_node(state: ReconState) -> dict:
    """Audit / terminal node."""
    logger.info("Executing audit_node")
    
    payments = {p["payment_id"]: p for p in state["payments"]}
    candidates = state.get("candidates", {})
    llm_decisions = state.get("llm_decisions", [])
    
    # 1. Run Groundedness Checks & Log decisions
    groundedness_violations = 0
    for d in llm_decisions:
        pid = d["payment_id"]
        cands = candidates.get(pid, [])
        pmt = payments.get(pid, {})
        
        # Log via structured logger
        _logger.log_llm_reasoning(d)
        
        # Check faithfulness
        violations = check_groundedness(d, cands, pmt)
        if violations:
            logger.warning(f"Groundedness violations for {pid}: {violations}")
            groundedness_violations += len(violations)
            d["groundedness_violations"] = violations
    
    # In a real system, this writes to DB. Here we just log metrics.
    metrics = state.get("metrics", {})
    total_exceptions = len(state.get("exceptions", []))
    total_resolved = len(llm_decisions)
    l0_matches = len(state.get("deterministic_matches", []))
    
    metrics["total_reconciled"] = l0_matches + total_resolved
    metrics["total_exceptions"] = total_exceptions
    metrics["groundedness_violations"] = groundedness_violations
    
    logger.info(f"Audit Complete. Total Reconciled: {metrics['total_reconciled']} | Total Exceptions: {total_exceptions} | Groundedness Violations: {groundedness_violations}")
    return {"metrics": metrics}

# ── Edges and Routing ────────────────────────────────────────────────

def route_on_candidates(state: ReconState) -> str:
    if state.get("candidates"):
        return "has_candidates"
    return "no_candidates"

def route_on_decision(state: ReconState) -> str:
    # Always go to audit_report after LLM, whether resolved or escalated
    # (the spec edge is just a demonstration of conditional routing, 
    # but practically all paths go to audit here)
    return "resolved" # or "escalate", both map to audit_report in spec

# ── Build Graph ──────────────────────────────────────────────────────

graph_builder = StateGraph(ReconState)
graph_builder.add_node("deterministic_match", deterministic_match_node)
graph_builder.add_node("retrieve", retrieve_node)
graph_builder.add_node("llm_reason", llm_reason_node)
graph_builder.add_node("audit_report", audit_node)

graph_builder.add_edge("__start__", "deterministic_match")
graph_builder.add_edge("deterministic_match", "retrieve")

graph_builder.add_conditional_edges(
    "retrieve", 
    route_on_candidates,
    {"has_candidates": "llm_reason", "no_candidates": "audit_report"}
)

graph_builder.add_conditional_edges(
    "llm_reason", 
    route_on_decision,
    {"resolved": "audit_report", "escalate": "audit_report"}
)

graph_builder.add_edge("audit_report", END)

recon_graph = graph_builder.compile()

# ── CLI runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
    
    data_dir = Path(__file__).parent.parent / "data" / "generated"
    with open(data_dir / "payments.json") as f:
        payments = json.load(f)
    with open(data_dir / "invoices.json") as f:
        invoices = json.load(f)
        
    # Test on a small slice (to avoid Groq rate limits)
    # We'll isolate exactly 2 clean deterministic matches, and 3 hard cases
    test_pmts = ["PMT-0012", "PMT-0018", "PMT-0054", "PMT-0039", "PMT-0004"]
    sub_payments = [p for p in payments if p["payment_id"] in test_pmts]
    
    initial_state = {
        "payments": sub_payments,
        "invoices": invoices,
        "metrics": {}
    }
    
    print(f"=== Starting Orchestration Graph with {len(sub_payments)} payments ===")
    
    final_state = recon_graph.invoke(initial_state)
    
    print("\n=== Final State Metrics ===")
    print(json.dumps(final_state["metrics"], indent=2))
    
    print(f"\nDeterministic Matches: {len(final_state.get('deterministic_matches', []))}")
    print(f"LLM Decisions: {len(final_state.get('llm_decisions', []))}")
    print(f"Exceptions: {len(final_state.get('exceptions', []))}")
