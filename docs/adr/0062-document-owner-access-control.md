# 0062 — Document owner access control

## Status

Accepted

## Context

A live-site design review surfaced a real, likely long-standing broken
access control bug: `GET /documents` (list) and `GET /documents/{id}`
(detail) had no ownership check at all, and `search_service.hybrid_search`
-- the retrieval function backing `GET /documents/search`, `POST /chat`,
and `POST /legal/draft` -- searched across every user's document chunks
unscoped. Only `DELETE /documents/{id}` was correctly protected
(`document.owner_id != current_user.id and current_user.role != "admin"`
-> 403).

Concretely, before this fix:

- Any authenticated user could list and read every other user's documents
  by ID (an IDOR on `GET /documents/{id}`).
- `POST /chat` could ground and cite answers in documents the caller
  didn't own.
- `POST /legal/draft` was worse: its caller-supplied `document_ids` field
  had no ownership check, so a caller could pass another user's document
  ID directly and have it retrieved, quoted, and drafted from.
- The Manager Agent's `search` tool and the Communication Agent's
  drafting step (`POST /manager/ask`) inherited both issues transitively,
  since they call the same underlying functions.

"Workspace members" (shared visibility beyond the owner) was raised as a
question during triage but explicitly deferred: there is no existing
schema concept to hang it on (`Organization` exists per ADR 0029 but is
deliberately not wired to documents yet; `Case` has a single `user_id`
owner, no collaborator list). Scope for this fix is owner-only, matching
`delete_document`'s already-correct pattern.

## Decision

**`search_service.hybrid_search`** gains a required (keyword-only)
`owner_id: UUID` parameter. Both its semantic and keyword queries now
join `Document` and filter `Document.owner_id == owner_id`. Making it
required rather than optional means a future caller that forgets to pass
it gets a `TypeError` at call time, not a silent unscoped search --
secure by construction, not by convention. The existing `document_ids`
parameter still narrows *within* that owner's own documents; it can no
longer widen scope to someone else's, which is what closes the
`/legal/draft` IDOR (a caller-supplied ID for a document they don't own
now simply returns no chunks for that ID, same effect as it not
existing).

Six call sites were threaded with `owner_id`: `chat.py::_retrieve`
(via `answer_grounded_question`'s `user_id`), `legal.py::_retrieve` (via
`_generate_draft`'s `user_id`), `documents.py`'s `/search` endpoint,
`tools.py::_search_handler` (the Manager Agent's `search` tool), and
`communication_agent.py::draft_communication`.

**`list_documents`** now filters `WHERE Document.owner_id ==
current_user.id` unless the caller is an admin (who sees everything,
matching the existing admin-bypass semantics of `delete_document`).
**`get_document`** gets the identical ownership check `delete_document`
already had, verbatim: 403 if `document.owner_id != current_user.id and
current_user.role != "admin"`.

Admin bypass was deliberately *not* extended to the search/chat/legal-
draft grounding paths -- an admin's AI-generated answer surfacing another
user's private document content is a different, worse failure mode than
an admin viewing one specific document through the management UI, and
there's no existing precedent for admin bypass on content retrieval in
this codebase.

## Verification

No sandbox available with Docker/Postgres by default in this session
(same constraint as ADR 0061), but a local Postgres 16 + pgvector (built
from source; no bottle for this platform/PG version combination) + Redis
were installed and a real migrated database was used for verification --
not hand-tracing this time. New tests
(`tests/test_document_access_control.py`, 8 tests, real DB, no mocked
`hybrid_search`) directly exercise: list excludes another user's
documents; list includes admin's view of everything; get 403s for a
non-owner and succeeds for the owner and for an admin; the search
endpoint returns nothing for another user's content; `/legal/draft`
cannot retrieve or quote another user's document even when its ID is
supplied directly in the request; `/chat` does not ground an answer in
another user's document. 51/51 tests pass across the new file plus every
existing test file touching the changed code paths
(`test_chat.py`, `test_legal.py`, `test_manager_agent.py`,
`test_manager_router.py`, `test_communication_agent.py`, `test_auth.py`).

`test_documents.py`'s own suite could not be run for real in this
session: its fixtures upload through the live `/documents` endpoint,
which triggers the real `DOCUMENT_UPLOADED` background-event chain
(OCR -> embeddings -> auto task/entity/vehicle extraction), and those
subscribers make real, unmocked LLM calls with no Ollama available here.
Confirmed by reproducing the identical hang against the pre-fix code
(`git stash`) -- this is a pre-existing environmental gap unrelated to
this change, not a regression it introduces.
