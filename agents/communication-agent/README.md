# communication-agent

Multi-channel (Signal, email) grounded message drafting. Phase 24.

Implemented inside `services/api` (`api/communication_agent.py`), not as a
separate service — see `docs/adr/0041-phase24-communication-agent.md`
for why. Dispatched via the Planning Engine's `draft_communication` goal
type (`api/planning_engine.py`) the same way every other agent is. This
stub stays in place as a placeholder for a future split.
