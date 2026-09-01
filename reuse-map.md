# ReconAgent — Reuse Map

Exact guidance on what to port from prior projects versus what must be written new. Check this before implementing Layer 1, orchestration, Layer 2, or the frontend scaffold — real time is recoverable here. Do not reuse anything not listed below without checking with the user first; the point of this file is precision, not "reuse whatever's convenient."

## From AlphaRAG-10K-Engine

| Reuse | Where it goes | Change required |
|---|---|---|
| Hybrid retrieval scaffolding (indexing + query infrastructure) | Layer 1 | Re-point the indexed text from filing chunks to invoice `description`/`reference` fields. The retrieval *infrastructure* transfers; the *content* it indexes does not. |
| LangGraph self-correction / retry loop | Layer 2 | This is the pattern for "if the LLM's output fails validation, retry with a correction prompt." Reuse the retry/critique node shape for enforcing the invoice_id-must-be-in-candidates rule. |
| FastAPI app structure, routing conventions, error middleware | API layer | Reuse directly if solid; adapt route names to the ReconAgent endpoint list in `backend.md#api`. |
| Next.js scaffold — routing, layout shell, API client hooks | Frontend | Reuse the *scaffolding* only. |
| **Cyberpunk visual theme** | — | **Do not reuse.** ReconAgent has its own identity (`frontend.md`). Re-skinning AlphaRAG's theme reads as derivative, not distinctive, and actively works against the design brief. |

## From Nexus-RAG

| Reuse | Where it goes | Change required |
|---|---|---|
| Manual RRF fusion function | Layer 1 | Port as-is. Inputs change from whatever ranked lists Nexus-RAG originally fused to three new ones: lexical rank, amount-proximity rank, date-proximity rank. |
| BM25 scorer | Layer 1 | Port as-is, applied to invoice `description` text instead of document text. |

This is the single highest-leverage reuse in the whole project — the retrieval layer's hardest math (rank fusion) is already written and validated. Do not re-derive it.

## From JARVIS

| Reuse | Where it goes | Change required |
|---|---|---|
| FastAPI + LangGraph StateGraph skeleton | Orchestration | Reuse the state-schema-definition and conditional-edge wiring pattern. Nodes themselves are new (deterministic_match, retrieve, llm_reason, audit_report instead of JARVIS's voice/agent nodes). |
| Groq API client wrapper | Layer 2 | Reuse directly for the Llama-3-8B-Instruct calls — no reason to write a new HTTP client for the same provider. |

## Nothing existing covers — budget real build time for these

- **Deterministic rules engine (Layer 0)** — no prior project does exact-match/tolerance-band filtering; this is pure new logic, though it's the simplest module in the system.
- **Numeric proximity signals** (amount-decay, date-decay scoring) — prior RAG work only scores text; these are new scoring functions.
- **Synthetic data generator with the categorized-messiness distribution**, including the orphan category — new.
- **Faithfulness check and calibration check** — conceptually similar in spirit to Sentinel's walk-forward validation discipline (checking whether a model's stated confidence is honest, not just its headline accuracy) but not portable code — different domain, different data shape. Treat Sentinel as inspiration for the *rigor*, not a source of reusable functions.
- **The Receipt component and the funnel visualization** — no prior project has either visual metaphor; build fresh per `frontend.md`.
- **Ground-truth scoring/evaluation module** — new, though the discipline of "score against a held-out labeled set, never against training data" is the same principle Sentinel already follows.
