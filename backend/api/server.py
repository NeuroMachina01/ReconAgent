"""
ReconAgent - API Server (Module 7)
FastAPI endpoints for batch reconciliation.
"""
import json
import uuid
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.orchestration.graph import recon_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ReconAgent API")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (replace with DB/Redis in prod)
# job_id -> {"status": str, "state": ReconState, "error": str}
JOBS = {}


def run_pipeline(job_id: str, payments: list[dict], invoices: list[dict]):
    """Background task to run the LangGraph pipeline."""
    logger.info(f"Job {job_id} starting pipeline execution.")
    JOBS[job_id]["status"] = "processing"
    
    initial_state = {
        "payments": payments,
        "invoices": invoices,
        "metrics": {}
    }
    
    try:
        for state_val in recon_graph.stream(initial_state, stream_mode="values"):
            # state_val is the fully-reduced state after each node completes
            JOBS[job_id]["state"] = state_val
                
        JOBS[job_id]["status"] = "completed"
        logger.info(f"Job {job_id} completed successfully.")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)


@app.post("/reconcile/batch")
async def reconcile_batch(
    background_tasks: BackgroundTasks,
    payments_file: UploadFile = File(...),
    invoices_file: UploadFile = File(...)
):
    """Upload payments and invoices JSON, returns job_id."""
    try:
        p_content = await payments_file.read()
        i_content = await invoices_file.read()
        
        payments = json.loads(p_content)
        invoices = json.loads(i_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON files: {e}")
        
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "pending",
        "state": None,
        "error": None
    }
    
    background_tasks.add_task(run_pipeline, job_id, payments, invoices)
    
    return {"job_id": job_id, "status": "pending"}


@app.get("/reconcile/{job_id}/progress")
def get_progress(job_id: str):
    """Check pipeline execution progress."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = JOBS[job_id]
    state = job.get("state") or {}
    metrics = state.get("metrics", {}) if state else {}
    return {
        "job_id": job_id,
        "status": job["status"],
        "error": job["error"],
        "metrics": metrics
    }


@app.get("/reconcile/{job_id}/results")
def get_results(job_id: str):
    """Get matched pairs, confidence, method per row."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = JOBS[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job['status']})")
        
    state = job["state"]
    results = []
    
    # Deterministic matches
    for d in state.get("deterministic_matches", []):
        results.append({
            "payment_id": d["payment_id"],
            "invoice_ids": d["invoice_ids"],
            "decision": "MATCH",
            "confidence": 1.0,
            "status": "confirmed",
            "method": "deterministic",
        })
        
    # LLM decisions (Resolved)
    for d in state.get("llm_decisions", []):
        results.append({
            "payment_id": d["payment_id"],
            "invoice_ids": d["invoice_ids"],
            "decision": d["decision"],
            "confidence": d["confidence"],
            "status": d["status"],
            "method": d["method"],
        })
        
    # Exceptions
    for d in state.get("exceptions", []):
        results.append({
            "payment_id": d["payment_id"],
            "invoice_ids": d.get("invoice_ids", []),
            "decision": d.get("decision", "ESCALATE"),
            "confidence": d.get("confidence", 0.0),
            "status": d.get("status", "exception"),
            "method": d.get("method", "retrieval_direct_escalate"),
        })
        
    return {"job_id": job_id, "results": results}


@app.get("/reconcile/{job_id}/metrics")
def get_metrics(job_id: str):
    """Get pipeline metrics."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = JOBS[job_id]
    if job["status"] != "completed":
        if job["state"] is None:
            return {"job_id": job_id, "metrics": {}}
        # Return intermediate metrics
        return {"job_id": job_id, "metrics": job["state"].get("metrics", {})}
        
    metrics = job["state"].get("metrics", {})
    return {"job_id": job_id, "metrics": metrics}

@app.post("/reconcile/{job_id}/evaluate")
async def evaluate_job(job_id: str, ground_truth_file: UploadFile = File(...)):
    """Evaluate pipeline accuracy against an uploaded ground_truth.json."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = JOBS[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
        
    try:
        from collections import defaultdict
        content = await ground_truth_file.read()
        gt = json.loads(content)
        gt_map = {g["payment_id"]: g for g in gt}
        
        state = job["state"]
        results = []
        for d in state.get("deterministic_matches", []):
            results.append({"payment_id": d["payment_id"], "invoice_ids": d["invoice_ids"], "decision": "MATCH"})
        for d in state.get("llm_decisions", []):
            results.append({"payment_id": d["payment_id"], "invoice_ids": d["invoice_ids"], "decision": d["decision"]})
        for d in state.get("exceptions", []):
            results.append({"payment_id": d["payment_id"], "invoice_ids": d.get("invoice_ids", []), "decision": d.get("decision", "ESCALATE")})
            
        confusion = defaultdict(lambda: defaultdict(int))
        
        # Precision = "When the agent made a decision (MATCH or ESCALATE appropriately), how often was it right?"
        # Recall = "Of all the things the agent *should* have done correctly, how many did it do?"
        true_positives = 0
        false_positives = 0
        false_negatives = 0
            
        for res in results:
            pmt_id = res["payment_id"]
            if pmt_id not in gt_map: continue
            
            actual = gt_map[pmt_id]
            pred_decision = res["decision"]
            pred_ids = set(res.get("invoice_ids", []))
            
            actual_type = actual.get("category", actual["match_type"])
            actual_match_type = actual["match_type"]
            actual_ids = set(actual["invoice_ids"])
            
            confusion[actual_type][pred_decision] += 1
            
            # TRUE ORPHANS: The correct action is to ESCALATE
            if actual_match_type == "orphan":
                if pred_decision == "ESCALATE": 
                    true_positives += 1  # Successfully identified an anomaly
                else: 
                    false_positives += 1 # Hallucinated a match on an anomaly
            
            # REGULAR TRANSACTIONS: The correct action is to MATCH
            else:
                if pred_decision == "ESCALATE": 
                    false_negatives += 1 # Failed to automate a valid transaction
                else:
                    if len(pred_ids.intersection(actual_ids)) > 0: 
                        true_positives += 1 # Correctly automated
                    else: 
                        false_positives += 1 # Automated, but picked the wrong invoice
                        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "confusion": confusion
        }
    except Exception as e:
        logger.error(f"Error computing evaluation metrics: {e}")
        raise HTTPException(status_code=400, detail=f"Error evaluating: {str(e)}")


@app.get("/reconcile/{job_id}/trace/{payment_id}")
def get_trace(job_id: str, payment_id: str):
    """Get full reasoning trace for one payment (the 'receipt')."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = JOBS[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job['status']})")
        
    state = job["state"]
    
    # Search all result queues for the payment
    # 1. Deterministic
    for d in state.get("deterministic_matches", []):
        if d["payment_id"] == payment_id:
            return {"trace": d, "layer": 0, "method": "deterministic"}
            
    # 2. LLM Resolved
    for d in state.get("llm_decisions", []):
        if d["payment_id"] == payment_id:
            cands = state.get("candidates", {}).get(payment_id, [])
            return {"trace": d, "layer": 2, "candidates_shown": cands, "method": d["method"]}
            
    # 3. Exceptions
    for d in state.get("exceptions", []):
        if d["payment_id"] == payment_id:
            cands = state.get("candidates", {}).get(payment_id, [])
            return {"trace": d, "layer": 2, "candidates_shown": cands, "method": d.get("method", "retrieval_direct_escalate")}
            
    raise HTTPException(status_code=404, detail="Payment ID not found in results")

