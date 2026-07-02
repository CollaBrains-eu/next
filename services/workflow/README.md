# workflow

Workflow engine (Celery-based), configurable and Signal-triggerable. Phase 2b.

One concrete trigger implemented so far, in-process (not Celery — see
`docs/adr/0004-phase2b-legal-planner-workflow.md` for why that's deferred):
when a document finishes processing, it optionally triggers the Planner
Agent to extract tasks (`api/documents.py::_process_document`, gated by
`settings.auto_extract_tasks_on_ready`). Revisit Celery once Signal
(Phase 3) gives this a second real trigger source.
