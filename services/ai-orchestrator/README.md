# ai-orchestrator

Planning, memory, tool routing, agent selection. Phase 2a.

Implemented inside `services/api` (`api/chat.py`, `POST /chat`) as a
retrieval-augmented chat endpoint — see
`docs/adr/0003-phase2a-ai-gateway-orchestrator.md`. No autonomous
multi-step planning or persisted conversation memory yet; that's scoped
to the Planner Agent (Phase 2b).
