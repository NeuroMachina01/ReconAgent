# ReconAgent — Frontend Specification

Read `../SKILL.md` first. This UI must not be a generic admin dashboard — every screen maps to a backend module in `backend.md`. If you cannot name which API response a piece of UI is rendering, do not build it.

## Design identity

Do not default to the AlphaRAG cyberpunk theme, a generic light-mode SaaS look, or a templated dark dashboard. Build this specific identity: a **financial control room** — precise, dark, ledger-accurate.

**Color tokens** — use exactly these, no substitutions:
| Token | Hex | Use |
|---|---|---|
| Ink | `#0B1220` | Page background |
| Paper | `#121B2E` | Card / panel surfaces |
| Signal | `#4C7DFF` | Primary actions, links, in-progress state |
| Ledger | `#34D399` | Confirmed matches, calibration success |
| Flag | `#F5A623` | Partial matches, moderate confidence |
| Alarm | `#FF6B6B` | Escalations, exceptions |
| Chalk | `#E7ECF5` | Primary text |

**Type** — Space Grotesk for page titles/hero only (used sparingly). Inter for all body text. **JetBrains Mono for every number: amounts, confidence scores, IDs, timestamps, without exception.** The mono face is what makes this read as a ledger instead of a dashboard — do not fall back to the body face for numeric data anywhere.

**Layout anchor:** the product is organized around a horizontal funnel that narrows as records resolve (total → rules-cleared → reasoning-resolved → escalated). This is not one widget among many — it is the primary visual on the home/dashboard page, and every other page is a drill-down from a point on it.

**Signature component — the Receipt:** clicking a transaction does not open a generic modal. It renders a receipt: monospace type, dotted tear-edge at the bottom, itemized (amount matched, date delta, reference similarity, confidence bar, one line of reasoning verbatim from the LLM). Build this component early and reuse it everywhere a transaction needs to be shown in detail.

**Motion budget:** exactly two animated moments — the funnel filling live as a batch processes, and the receipt printing/unfurling on click. No animation anywhere else. Respect `prefers-reduced-motion`.

**No gradients, no rounded pill buttons, no decorative icons, no stock illustration.** Numbers should feel counted, not designed.

## Pages

**Home / new batch** — upload `payments.json` + `invoices.json`, one button: "Run reconciliation." A quiet preview of the three-stage pipeline below the button, not marketing copy.

**Live run** — the funnel filling in real time (see backend connection below). A mono-type counter: records processed / total. This is the screen open during judging.

**Results dashboard** — funnel at rest with final numbers. Three panels: match rate by layer, confusion matrix against ground truth, confidence calibration strip. Every number here must trace to `GET /reconcile/{job_id}/metrics` — do not invent placeholder numbers during development; wire the real endpoint from day one, even if it returns zeros at first.

**Transaction trace (the Receipt)** — full pipeline history for one payment: candidates retrieved with individual signal scores, the LLM's verbatim reasoning, confidence, final decision. Source: `GET /reconcile/{job_id}/trace/{payment_id}`. Build this before anything cosmetic elsewhere — it is the page that answers THE BAR's "measured accuracy" requirement directly.

**Exceptions** — the full escalated list, sortable, each row showing the model's stated reason. This is a first-class page, not a tab buried in the dashboard. If it's hard to find, it will not get shown.

## Connecting backend and frontend

- Stack: React (Vite or Next) + Tailwind, calling the FastAPI backend from `backend.md#api`.
- **CORS**: enable `CORSMiddleware` on FastAPI for the frontend's deployed origin plus `localhost`. If nothing loads, this is the first thing to check.
- **Live batch progress**: wrap the LangGraph run in a FastAPI `StreamingResponse` (SSE), emitting one event per record: `{"payment_id": ..., "layer": ..., "decision": ...}`. Frontend subscribes with `EventSource`, updates the funnel counters as events arrive. Build the 1-second polling version against `/reconcile/{job_id}/progress` first and get it working end to end — only upgrade to SSE once the simple version works.
- **Data fetching**: React Query or SWR for `results`, `metrics`, `trace/{payment_id}` — gives loading/error states for free.
- **Config**: single env var, `VITE_API_BASE_URL` (or `NEXT_PUBLIC_API_BASE_URL`). Never hardcode the backend URL anywhere else in the codebase.

## Deployment

- Backend: Railway or Render, git-push deploy, `GROQ_API_KEY` set as an environment variable there — never in code, never in a committed `.env`.
- Frontend: Vercel, connect the repo, set `VITE_API_BASE_URL` to the deployed backend URL.
- If using in-memory Qdrant or similar, note explicitly that state resets on backend restart/redeploy — do not build any frontend feature that assumes data survives a restart unless persistent storage is added.
- **Before considering this module done, run one full flow against the deployed URLs, not localhost.** Localhost working is not the same claim as production working.

## Feature priority if time is short

Build in this order; stop wherever the clock runs out — each item is independently demoable:
1. Live-filling funnel during a real batch run
2. The Receipt — transaction trace with field-level justification
3. Exceptions list as a real page
4. Confidence calibration strip

Do not spend time on: settings pages, user accounts, animated elements outside the funnel/receipt, or any stat card that doesn't map to a real API response.
