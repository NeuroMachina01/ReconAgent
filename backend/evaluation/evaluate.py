"""
ReconAgent - Evaluation (Module 8)
Computes Precision, Recall, and a Confusion Matrix against Ground Truth via the API.
"""
import json
import logging
from pathlib import Path
from collections import defaultdict
from fastapi.testclient import TestClient

from backend.api.server import app

logging.getLogger("httpx").setLevel(logging.WARNING)

def evaluate(sample_size: int = None):
    client = TestClient(app)
    
    data_dir = Path(__file__).parent.parent / "data" / "generated"
    with open(data_dir / "payments.json") as f:
        payments = json.load(f)
    with open(data_dir / "invoices.json") as f:
        invoices = json.load(f)
    with open(data_dir / "ground_truth.json") as f:
        gt = json.load(f)
        
    gt_map = {g["payment_id"]: g for g in gt}
    
    # If sample_size is provided, pick randomly
    if sample_size:
        import random
        # Seed for stability during dev runs
        random.seed(42)
        payments = random.sample(payments, min(sample_size, len(payments)))
        print(f"Running evaluation on random slice of {len(payments)} records...")
    else:
        print(f"Running full evaluation on {len(payments)} records...")

    # Write temp files for upload
    Path("scratch").mkdir(exist_ok=True)
    with open("scratch/eval_pmts.json", "w") as f:
        json.dump(payments, f)
        
    # 1. Post to API
    print("1. Submitting batch to API...")
    with open("scratch/eval_pmts.json", "rb") as pf, open(data_dir / "invoices.json", "rb") as inf:
        res = client.post(
            "/reconcile/batch",
            files={"payments_file": ("pmts.json", pf, "application/json"),
                   "invoices_file": ("invs.json", inf, "application/json")}
        )
    
    if res.status_code != 200:
        print(f"API Error: {res.text}")
        return
        
    job_id = res.json()["job_id"]
    
    # In TestClient, BackgroundTasks execute synchronously before the client returns the response.
    # So by here, it is already "completed"! 
    
    # 2. Fetch Results
    print("2. Fetching results...")
    res = client.get(f"/reconcile/{job_id}/results")
    if res.status_code != 200:
        print(f"Error fetching results: {res.text}")
        return
        
    results = res.json()["results"]
    
    # 3. Calculate Metrics
    print("\n3. Calculating Metrics...\n")
    
    # Confusion Matrix: Actual (rows) vs Predicted (cols)
    # Actuals: exact, orphan, partial, multi, garbled_ref, timing_offset, currency_rounding
    # Predicts: MATCH, PARTIAL_MATCH, MULTI_MATCH, ESCALATE
    confusion = defaultdict(lambda: defaultdict(int))
    
    true_positives = 0
    false_positives = 0
    false_negatives = 0
        
    for res in results:
        pmt_id = res["payment_id"]
        if pmt_id not in gt_map:
            continue
        
        actual = gt_map[pmt_id]
        pred_decision = res["decision"]
        pred_ids = set(res.get("invoice_ids", []))
        
        actual_type = actual.get("category", actual["match_type"])
        actual_match_type = actual["match_type"]
        actual_ids = set(actual["invoice_ids"])
        
        # Populate confusion matrix
        confusion[actual_type][pred_decision] += 1
        
        # Precision / Recall Logic based on match_type
        if actual_match_type == "orphan":
            if pred_decision == "ESCALATE":
                true_positives += 1  # Correctly escalated
            else:
                false_positives += 1 # Falsely matched an orphan
        else:
            # Real match case
            if pred_decision == "ESCALATE":
                false_negatives += 1 # Failed to match
            else:
                # Did we find ANY correct IDs?
                if len(pred_ids.intersection(actual_ids)) > 0:
                    true_positives += 1
                else:
                    false_positives += 1
                    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    
    print("=== PERFORMANCE METRICS ===")
    print(f"Precision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    
    print("\n=== CONFUSION MATRIX ===")
    pred_labels = ["MATCH", "PARTIAL_MATCH", "MULTI_MATCH", "ESCALATE"]
    
    # Header
    header = f"{'Actual Type':<20} | " + " | ".join([f"{l:<13}" for l in pred_labels])
    print(header)
    print("-" * len(header))
    
    actual_types = ["exact", "orphan", "partial", "multi", "garbled_ref", "timing_offset", "currency_rounding"]
    for atype in actual_types:
        row = f"{atype:<20} | "
        counts = []
        for plabel in pred_labels:
            counts.append(f"{confusion[atype][plabel]:<13}")
        row += " | ".join(counts)
        print(row)
        
if __name__ == "__main__":
    # We pass sample_size=None to run full evaluation on 64 records
    evaluate(sample_size=None)
