"""
ReconAgent — Synthetic Data + Ground Truth Generator (Module 1)

Produces:
  - invoices.json   (50–70 records)
  - payments.json   (60–80 records)
  - ground_truth.json  (one entry per payment → list of correct invoice_ids)

The ground truth file is the held-out answer key. The matching pipeline
must NEVER read it. All accuracy/precision/recall numbers are scored
against this file and this file only.

Category distribution (approximate, from backend.md#data):
  exact_match         35%   — Layer 0 test
  partial_payment     15%   — Layer 2 amount-delta
  multi_invoice       10%   — Layer 2 multi-select
  garbled_reference   15%   — Layer 1 lexical signal
  timing_offset       10%   — Layer 1 date-proximity
  currency_rounding    5%   — Layer 0 tolerance band
  true_orphan         10%   — escalation path (built first, not last)
"""

from __future__ import annotations

import json
import random
import string
import os
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict


# ── Schema (matches backend.md exactly) ──────────────────────────────

class PaymentRecord(TypedDict):
    payment_id: str          # PMT-0001
    amount: float
    date: str                # ISO date
    reference: str           # raw, messy text — "NEFT-RAJESH ENT-4521"
    source: str              # NEFT / UPI / card / RTGS
    currency: str


class InvoiceRecord(TypedDict):
    invoice_id: str          # INV-2026-0447
    amount: float
    due_date: str
    vendor_or_customer: str
    description: str
    status: str              # open / partially_paid / closed


class GroundTruthEntry(TypedDict):
    payment_id: str
    invoice_ids: list[str]   # empty = orphan
    match_type: str          # exact | partial | multi_invoice | orphan
    category: str            # exact | partial | multi | orphan | garbled_ref | timing_offset | currency_rounding


# ── Reference data ───────────────────────────────────────────────────

VENDORS = [
    "Rajesh Enterprises", "Priya Exports Ltd", "Sharma Electronics",
    "Gupta Traders", "Mehta Fabrics", "Anil Steels Pvt Ltd",
    "Sunita Packaging", "Verma Industries", "Kapoor Chemicals",
    "Bharat Auto Parts", "Deepak Electricals", "Lakshmi Textiles",
    "Sanjay Logistics", "Nitin Pharma", "Patel Agro Foods",
    "Khan Construction", "Joshi IT Solutions", "Reddy Marine Services",
    "Singh Transport Co", "Mohan Polymers", "Anand Precision Tools",
    "Ravi Office Supplies", "Tata Components Ltd", "Mahindra Infra",
    "Bajaj Spares", "Godrej Fixtures", "Wipro Consumables",
    "Birla Cement Supplies", "Reliance Petro Stores", "Infosys Sub-Contracts",
]

DESCRIPTIONS = [
    "Office supplies Q3 2026", "Server maintenance Aug 2026",
    "Raw materials — steel rods batch 44", "Logistics forwarding Delhi–Mumbai",
    "Annual software license renewal", "Electrical wiring Phase 2",
    "Packaging materials — corrugated boxes", "Quarterly consulting retainer",
    "Warehouse rent July 2026", "Machinery spare parts order #7891",
    "Textile dyeing chemicals lot 12", "IT hardware — 20x laptops",
    "Construction cement batch delivery", "Pharma excipients order",
    "Vehicle fleet fuel reimbursement", "Canteen supplies Aug–Sep",
    "Export documentation and customs fees", "Lab equipment calibration",
    "Security services Q3 invoice", "HVAC maintenance annual contract",
    "Printed marketing materials", "Freight charges — port to warehouse",
    "Audit and compliance retainer", "Plumbing fixtures for site B",
    "Employee uniform procurement", "Cloud hosting — AWS/GCP usage",
    "Catering for annual day event", "Fire safety equipment inspection",
    "Pest control quarterly service", "Generator diesel refill",
]

PAYMENT_SOURCES = ["NEFT", "UPI", "card", "RTGS"]

# ── Helpers ──────────────────────────────────────────────────────────

_inv_counter = 0
_pmt_counter = 0


def _next_inv_id() -> str:
    global _inv_counter
    _inv_counter += 1
    return f"INV-2026-{_inv_counter:04d}"


def _next_pmt_id() -> str:
    global _pmt_counter
    _pmt_counter += 1
    return f"PMT-{_pmt_counter:04d}"


def _random_amount(lo: float = 500.0, hi: float = 500000.0) -> float:
    """Return a realistic INR amount rounded to 2 decimals."""
    return round(random.uniform(lo, hi), 2)


def _random_date(start: date = date(2026, 6, 1),
                 end: date = date(2026, 8, 25)) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _garble_reference(ref: str) -> str:
    """Introduce typos / truncation / case shifts into a reference string."""
    mutations: list = []

    # random case flip
    ref_chars = list(ref)
    for i in range(len(ref_chars)):
        if random.random() < 0.15 and ref_chars[i].isalpha():
            ref_chars[i] = ref_chars[i].swapcase()
    ref = "".join(ref_chars)
    mutations.append("case_flip")

    # random char substitution (1–2 chars)
    ref_list = list(ref)
    for _ in range(random.randint(1, 2)):
        idx = random.randint(0, len(ref_list) - 1)
        if ref_list[idx].isalpha():
            ref_list[idx] = random.choice(string.ascii_letters)
        elif ref_list[idx].isdigit():
            ref_list[idx] = random.choice(string.digits)
    ref = "".join(ref_list)

    # random truncation (remove 2–4 trailing chars)
    if len(ref) > 8 and random.random() < 0.5:
        ref = ref[: -(random.randint(2, 4))]

    return ref


def _make_clean_reference(inv_id: str, vendor: str) -> str:
    """Build a clean payment reference that embeds the invoice ID."""
    source = random.choice(PAYMENT_SOURCES)
    short_vendor = vendor.split()[0].upper()
    return f"{source}-{short_vendor}-{inv_id}"


# ── Category generators ─────────────────────────────────────────────
# Each returns (list[InvoiceRecord], list[PaymentRecord], list[GroundTruthEntry])

def _gen_exact_match(n: int):
    """Exact amount, date within 2 days, invoice_id in reference."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        inv_id = _next_inv_id()
        vendor = random.choice(VENDORS)
        amount = _random_amount()
        due = _random_date()
        inv: InvoiceRecord = {
            "invoice_id": inv_id,
            "amount": amount,
            "due_date": due.isoformat(),
            "vendor_or_customer": vendor,
            "description": random.choice(DESCRIPTIONS),
            "status": "open",
        }
        pmt_id = _next_pmt_id()
        pmt_date = due + timedelta(days=random.randint(0, 2))
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": amount,               # exact
            "date": pmt_date.isoformat(),
            "reference": _make_clean_reference(inv_id, vendor),
            "source": random.choice(PAYMENT_SOURCES),
            "currency": "INR",
        }
        invoices.append(inv)
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[inv_id], match_type="exact", category="exact"))
    return invoices, payments, gt


def _gen_partial_payment(n: int):
    """Payment amount < invoice amount (e.g. 60-90% of invoice)."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        inv_id = _next_inv_id()
        vendor = random.choice(VENDORS)
        inv_amount = _random_amount(5000, 200000)
        due = _random_date()
        inv: InvoiceRecord = {
            "invoice_id": inv_id,
            "amount": inv_amount,
            "due_date": due.isoformat(),
            "vendor_or_customer": vendor,
            "description": random.choice(DESCRIPTIONS),
            "status": "partially_paid",
        }
        pmt_id = _next_pmt_id()
        pmt_amount = round(inv_amount * random.uniform(0.6, 0.9), 2)
        pmt_date = due + timedelta(days=random.randint(0, 3))
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": pmt_amount,
            "date": pmt_date.isoformat(),
            "reference": _make_clean_reference(inv_id, vendor),
            "source": random.choice(PAYMENT_SOURCES),
            "currency": "INR",
        }
        invoices.append(inv)
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[inv_id], match_type="partial", category="partial"))
    return invoices, payments, gt


def _gen_multi_invoice(n: int):
    """One payment covers 2–3 invoices combined."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        count = random.randint(2, 3)
        vendor = random.choice(VENDORS)
        inv_ids = []
        total = 0.0
        due = _random_date()
        for _ in range(count):
            inv_id = _next_inv_id()
            inv_ids.append(inv_id)
            amt = _random_amount(2000, 80000)
            total += amt
            inv: InvoiceRecord = {
                "invoice_id": inv_id,
                "amount": amt,
                "due_date": due.isoformat(),
                "vendor_or_customer": vendor,
                "description": random.choice(DESCRIPTIONS),
                "status": "open",
            }
            invoices.append(inv)

        pmt_id = _next_pmt_id()
        # Reference mentions the vendor but not specific invoice IDs
        source = random.choice(PAYMENT_SOURCES)
        ref = f"{source}-{vendor.split()[0].upper()}-MULTI-{due.strftime('%b%y').upper()}"
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": round(total, 2),
            "date": (due + timedelta(days=random.randint(0, 2))).isoformat(),
            "reference": ref,
            "source": source,
            "currency": "INR",
        }
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=inv_ids, match_type="multi_invoice", category="multi"))
    return invoices, payments, gt


def _gen_garbled_reference(n: int):
    """Invoice ID is in the reference but garbled/typo'd."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        inv_id = _next_inv_id()
        vendor = random.choice(VENDORS)
        amount = _random_amount()
        due = _random_date()
        inv: InvoiceRecord = {
            "invoice_id": inv_id,
            "amount": amount,
            "due_date": due.isoformat(),
            "vendor_or_customer": vendor,
            "description": random.choice(DESCRIPTIONS),
            "status": "open",
        }
        pmt_id = _next_pmt_id()
        clean_ref = _make_clean_reference(inv_id, vendor)
        garbled_ref = _garble_reference(clean_ref)
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": amount,
            "date": (due + timedelta(days=random.randint(0, 1))).isoformat(),
            "reference": garbled_ref,
            "source": random.choice(PAYMENT_SOURCES),
            "currency": "INR",
        }
        invoices.append(inv)
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[inv_id], match_type="exact", category="garbled_ref"))
    return invoices, payments, gt


def _gen_timing_offset(n: int):
    """Correct match but payment date is 2–5 days off from due_date."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        inv_id = _next_inv_id()
        vendor = random.choice(VENDORS)
        amount = _random_amount()
        due = _random_date()
        inv: InvoiceRecord = {
            "invoice_id": inv_id,
            "amount": amount,
            "due_date": due.isoformat(),
            "vendor_or_customer": vendor,
            "description": random.choice(DESCRIPTIONS),
            "status": "open",
        }
        pmt_id = _next_pmt_id()
        # 3-5 day offset — intentionally outside Layer 0's 2-day tolerance
        offset = random.randint(3, 5)
        pmt_date = due + timedelta(days=offset)
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": amount,
            "date": pmt_date.isoformat(),
            "reference": _make_clean_reference(inv_id, vendor),
            "source": random.choice(PAYMENT_SOURCES),
            "currency": "INR",
        }
        invoices.append(inv)
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[inv_id], match_type="exact", category="timing_offset"))
    return invoices, payments, gt


def _gen_currency_rounding(n: int):
    """Amount differs by ±₹1–5 due to rounding."""
    invoices, payments, gt = [], [], []
    for _ in range(n):
        inv_id = _next_inv_id()
        vendor = random.choice(VENDORS)
        amount = _random_amount()
        due = _random_date()
        inv: InvoiceRecord = {
            "invoice_id": inv_id,
            "amount": amount,
            "due_date": due.isoformat(),
            "vendor_or_customer": vendor,
            "description": random.choice(DESCRIPTIONS),
            "status": "open",
        }
        pmt_id = _next_pmt_id()
        rounding_delta = round(random.uniform(-5.0, 5.0), 2)
        # Ensure delta is at least ±1 so it's meaningfully different
        if abs(rounding_delta) < 1.0:
            rounding_delta = random.choice([-1.0, 1.0]) * random.uniform(1.0, 5.0)
            rounding_delta = round(rounding_delta, 2)
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": round(amount + rounding_delta, 2),
            "date": (due + timedelta(days=random.randint(0, 2))).isoformat(),
            "reference": _make_clean_reference(inv_id, vendor),
            "source": random.choice(PAYMENT_SOURCES),
            "currency": "INR",
        }
        invoices.append(inv)
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[inv_id], match_type="exact", category="currency_rounding"))
    return invoices, payments, gt


def _gen_true_orphan(n: int):
    """Payments with NO correct invoice match — tests escalation path."""
    payments, gt = [], []
    for _ in range(n):
        pmt_id = _next_pmt_id()
        vendor = random.choice(VENDORS)
        source = random.choice(PAYMENT_SOURCES)
        # Reference mentions a non-existent invoice
        fake_inv = f"INV-2025-{random.randint(9000, 9999):04d}"
        pmt: PaymentRecord = {
            "payment_id": pmt_id,
            "amount": _random_amount(),
            "date": _random_date().isoformat(),
            "reference": f"{source}-{vendor.split()[0].upper()}-{fake_inv}",
            "source": source,
            "currency": "INR",
        }
        payments.append(pmt)
        gt.append(GroundTruthEntry(
            payment_id=pmt_id, invoice_ids=[], match_type="orphan", category="orphan"))
    return [], payments, gt


# ── Main generator ───────────────────────────────────────────────────

def generate_synthetic_data(
    seed: int = 42,
    output_dir: str | Path | None = None,
) -> tuple[list[InvoiceRecord], list[PaymentRecord], list[GroundTruthEntry]]:
    """
    Generate the full synthetic dataset.

    Returns (invoices, payments, ground_truth) and also writes them
    to JSON files in output_dir.
    """
    random.seed(seed)
    global _inv_counter, _pmt_counter
    _inv_counter = 0
    _pmt_counter = 0

    # Target ~65 payments total.  Distribution per backend.md:
    #   exact=35%, partial=15%, multi=10%, garbled=15%,
    #   timing=10%, rounding=5%, orphan=10%
    total_payments = 65
    counts = {
        "exact":    round(total_payments * 0.35),    # 23
        "partial":  round(total_payments * 0.15),    # 10
        "multi":    round(total_payments * 0.10),    # 6-7
        "garbled":  round(total_payments * 0.15),    # 10
        "timing":   round(total_payments * 0.10),    # 6-7
        "rounding": round(total_payments * 0.05),    # 3
        "orphan":   round(total_payments * 0.10),    # 6-7
    }

    all_invoices: list[InvoiceRecord] = []
    all_payments: list[PaymentRecord] = []
    all_gt: list[GroundTruthEntry] = []

    # Build orphans FIRST (per spec: "build this category first, not last")
    inv, pmt, gt = _gen_true_orphan(counts["orphan"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_exact_match(counts["exact"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_partial_payment(counts["partial"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_multi_invoice(counts["multi"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_garbled_reference(counts["garbled"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_timing_offset(counts["timing"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    inv, pmt, gt = _gen_currency_rounding(counts["rounding"])
    all_invoices.extend(inv)
    all_payments.extend(pmt)
    all_gt.extend(gt)

    # Shuffle to prevent ordering leakage
    random.shuffle(all_invoices)
    random.shuffle(all_payments)
    random.shuffle(all_gt)

    # Write output
    if output_dir is None:
        output_dir = Path(__file__).parent / "generated"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    invoices_path = output_dir / "invoices.json"
    payments_path = output_dir / "payments.json"
    gt_path = output_dir / "ground_truth.json"

    with open(invoices_path, "w", encoding="utf-8") as f:
        json.dump(all_invoices, f, indent=2, ensure_ascii=False)

    with open(payments_path, "w", encoding="utf-8") as f:
        json.dump(all_payments, f, indent=2, ensure_ascii=False)

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(all_gt, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"=== ReconAgent Synthetic Data Generated ===")
    print(f"  Invoices:  {len(all_invoices):>4}  -> {invoices_path}")
    print(f"  Payments:  {len(all_payments):>4}  -> {payments_path}")
    print(f"  Ground truth: {len(all_gt):>4}  -> {gt_path}")
    print()

    # Distribution breakdown
    from collections import Counter
    type_counts = Counter(e["category"] for e in all_gt)
    print("  Distribution:")
    for mtype, count in sorted(type_counts.items()):
        pct = count / len(all_gt) * 100
        print(f"    {mtype:<16} {count:>3}  ({pct:.0f}%)")

    # Sanity checks
    pmt_ids = {p["payment_id"] for p in all_payments}
    gt_pmt_ids = {e["payment_id"] for e in all_gt}
    inv_ids = {i["invoice_id"] for i in all_invoices}
    orphan_entries = [e for e in all_gt if e["match_type"] == "orphan"]

    print()
    print("  Sanity checks:")
    print(f"    Every payment has ground truth: {pmt_ids == gt_pmt_ids}")
    print(f"    Orphan count (must be > 0):     {len(orphan_entries)}")

    # Check non-orphan GT entries reference valid invoices
    gt_inv_ids = set()
    for e in all_gt:
        gt_inv_ids.update(e["invoice_ids"])
    missing = gt_inv_ids - inv_ids
    print(f"    All GT invoice_ids exist:       {len(missing) == 0}")
    if missing:
        print(f"      MISSING: {missing}")

    return all_invoices, all_payments, all_gt


if __name__ == "__main__":
    generate_synthetic_data()
