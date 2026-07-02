# planner-agent

Task planning and scheduling. Phase 2b.

Implemented inside `services/api` (`api/planner_agent.py`,
`POST /documents/{id}/extract-tasks`, `GET /tasks`,
`PATCH /tasks/{id}`). Scoped to task extraction from document text —
no calendar sync, recurrence, or real user assignment yet. See
`docs/adr/0004-phase2b-legal-planner-workflow.md`.
