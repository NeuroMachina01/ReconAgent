"""
ReconAgent - Observability (Module 6)
Faithfulness / Groundedness Check (rules-based).
"""
import re

def check_groundedness(decision: dict, candidates: list[dict], payment: dict) -> list[str]:
    """
    Checks if the reasoning provided by the LLM is factually faithful to the raw data.
    Returns a list of violation strings. Empty list means perfectly grounded.
    
    Mirrors AlphaRAG's grounding pattern: flags hallucinated justifications.
    """
    reasoning = decision.get("reasoning", "").lower()
    violations = []
    
    # 1. Invoice ID verification (handled primarily by validation loop, but strict invariant check here)
    selected_ids = decision.get("invoice_ids", [])
    valid_ids = {c["invoice_id"] for c in candidates}
    for sid in selected_ids:
        if sid not in valid_ids:
            violations.append(f"GROUNDEDNESS_VIOLATION: Selected invoice {sid} was not in candidates.")
            
    if not selected_ids:
        return violations # Can't check amounts/dates without selected invoices
        
    # Get total candidate amount
    selected_cands = [c for c in candidates if c["invoice_id"] in selected_ids]
    # For amounts we need the raw invoice amount. The candidate dict passed to here should contain amount_delta at least,
    # or we can pass the raw invoices. We'll reconstruct total amount from amount_delta if necessary, 
    # but let's assume we have `amount_delta` and `date_delta_days` in the candidate dicts.
    
    # 2. Date checks
    if "date match" in reasoning or "exact date" in reasoning or "same date" in reasoning:
        # Check if any selected candidate has date_delta_days > 0
        for c in selected_cands:
            if c.get("date_delta_days", 0) > 0:
                violations.append(f"FAITHFULNESS_VIOLATION: Reasoning claims exact date match, but {c['invoice_id']} differs by {c.get('date_delta_days')} days.")
                
    # Check for "within X days"
    within_match = re.search(r"within (\d+) day", reasoning)
    if within_match:
        claimed_days = int(within_match.group(1))
        for c in selected_cands:
            actual_days = c.get("date_delta_days", 0)
            if actual_days > claimed_days:
                violations.append(f"FAITHFULNESS_VIOLATION: Reasoning claims within {claimed_days} days, but {c['invoice_id']} differs by {actual_days} days.")
                
    # 3. Amount checks
    if "exact amount" in reasoning or "amount match" in reasoning:
        if "partial" not in reasoning: # Exclude "partial amount match"
            for c in selected_cands:
                # amount_delta == 0
                if c.get("amount_delta", 0) > 0.01:
                    violations.append(f"FAITHFULNESS_VIOLATION: Reasoning claims exact amount match, but {c['invoice_id']} has delta of {c.get('amount_delta')}.")
                    
    return violations
