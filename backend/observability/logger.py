"""
ReconAgent - Observability (Module 6)
Structured JSON logging for layer transitions.
"""
import json
import logging
from datetime import datetime, timezone

class StructuredLogger:
    def __init__(self, log_file: str = None):
        self.log_file = log_file
        
    def log_retrieval(self, payment_id: str, candidates: list[dict]):
        record = {
            "payment_id": payment_id,
            "layer": "retrieval",
            "candidates": candidates,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._write(record)
        
    def log_llm_reasoning(self, decision_dict: dict):
        record = dict(decision_dict)
        record["layer"] = "llm_reasoning"
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._write(record)
        
    def _write(self, record: dict):
        line = json.dumps(record)
        logging.info(line)
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(line + '\n')
