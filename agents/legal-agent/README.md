# legal-agent

Legal reasoning, objection drafting. Phase 2b.

Implemented inside `services/api` (`api/legal.py`, `POST /legal/draft`).
Deliberately narrow: grounded drafting from ingested documents only, never
free-form legal advice or invented case law/citations — every response is
a draft requiring attorney review. See
`docs/adr/0004-phase2b-legal-planner-workflow.md`.
