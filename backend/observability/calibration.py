"""
ReconAgent - Observability (Module 6)
Calibration check: Predicted confidence vs Actual accuracy.
"""
from collections import defaultdict

def calibration_report(decisions: list[dict], ground_truth: list[dict]) -> str:
    """
    Groups decisions into confidence buckets and compares against ground truth.
    Returns a markdown table reporting calibration.
    """
    gt_map = {g["payment_id"]: g for g in ground_truth}
    
    # Buckets: 0.9-1.0, 0.8-0.89, 0.7-0.79, 0.6-0.69, 0.5-0.59, <0.5
    buckets = defaultdict(lambda: {"total": 0, "correct": 0})
    
    for d in decisions:
        pid = d["payment_id"]
        g = gt_map.get(pid)
        if not g:
            continue
            
        conf = d.get("confidence", 0.0)
        
        # Determine bucket
        if conf >= 0.9: b_name = "0.90 - 1.00"
        elif conf >= 0.8: b_name = "0.80 - 0.89"
        elif conf >= 0.7: b_name = "0.70 - 0.79"
        elif conf >= 0.6: b_name = "0.60 - 0.69"
        elif conf >= 0.5: b_name = "0.50 - 0.59"
        else: b_name = "< 0.50"
        
        buckets[b_name]["total"] += 1
        
        # Check correctness
        if g["match_type"] == "orphan":
            if d["decision"] == "ESCALATE":
                buckets[b_name]["correct"] += 1
        else:
            if d["decision"] != "ESCALATE":
                # Check if at least one selected ID is correct
                gt_ids = set(g["invoice_ids"])
                sel_ids = set(d["invoice_ids"])
                if sel_ids & gt_ids:
                    buckets[b_name]["correct"] += 1
                    
    # Generate report
    report = "### Confidence Calibration Report\n\n"
    report += "| Confidence Bucket | N | Actual Accuracy | Well Calibrated? |\n"
    report += "|---|---|---|---|\n"
    
    # Sort buckets descending
    bucket_order = ["0.90 - 1.00", "0.80 - 0.89", "0.70 - 0.79", "0.60 - 0.69", "0.50 - 0.59", "< 0.50"]
    
    for b_name in bucket_order:
        stats = buckets.get(b_name, {"total": 0, "correct": 0})
        total = stats["total"]
        if total == 0:
            report += f"| {b_name} | 0 | - | - |\n"
            continue
            
        acc = stats["correct"] / total
        acc_pct = f"{acc*100:.1f}%"
        
        # Check if well calibrated
        # Roughly: 0.9-1.0 should be > 90%, 0.8-0.89 around 85%, etc.
        min_expected = 0.0
        if b_name == "0.90 - 1.00": min_expected = 0.85
        elif b_name == "0.80 - 0.89": min_expected = 0.75
        elif b_name == "0.70 - 0.79": min_expected = 0.65
        elif b_name == "0.60 - 0.69": min_expected = 0.55
        elif b_name == "0.50 - 0.59": min_expected = 0.45
        
        calibrated = "[PASS] Yes" if acc >= min_expected else "[FAIL] Overconfident"
        
        report += f"| {b_name} | {total} | {acc_pct} | {calibrated} |\n"
        
    return report
