# Case/Document Sharing — Phase 1: Case-Member Document Access — Design

## Status
Proposed

## Context

`documents.py`'s access control is pure ownership everywhere: `get_document`, `get_document_file`, and `delete_document` all use the identical `if document.owner_id != current_user.id and current_user.role != "admin": raise 403`. `CaseMember` is never imported or referenced in `documents.py`.

Meanwhile `cases_router.py`'s `_require_case_access()` (`case.user_id == current_user.id` OR `role == "admin"` OR `is_case_member(...)` with `status == "accepted"`) already grants an accepted case member visibility into `CaseDashboardOut.documents` (titles + ids, via `get_case_dashboard()`'s direct `Document.case_id` query — no ownership filter there at all). So a case member can already *see* a document exists and its title from the case dashboard, then get a 403 the instant they click through to `/documents/{id}`. This is the concrete broken UX to fix, not a hypothetical.

The full membership machinery already exists and works, backend-only: `POST/GET /cases/{id}/members` (invite/list), `POST /cases/{id}/members/{user_id}/accept|decline` (respond to own invitation only, enforced by `_require_invited_user`), `GET /cases/invitations` (a user's own pending invitations, registered ahead of `/cases/{case_id}` to avoid the UUID-parse collision). None of it has any frontend: no UI in `CaseDetail.tsx`, no `api.ts` wrapper functions, no locale strings.

Two enrichment gaps block a usable invite UI even once wired up:
1. `list_pending_invitations()` and `list_case_members()` return bare `CaseMember` rows — no case name, no user display name. A pending invitee also cannot fetch full case details themselves (`GET /cases/{id}` requires `status == "accepted"` — a pending invitee 403s on the case they're deciding whether to join).
2. There is no non-admin user-lookup endpoint. `GET /admin/users` exists but is admin-gated. A case owner has no way to resolve "the person I want to invite" to a `user_id` UUID.

`en.json` already contains `cases.emptyMessageSub`: *"Cases you create or that get shared with you will show up here."* — the copy already anticipated this feature; only the backend delivers on it today.

## Goals

1. **Backend document access**: `get_document` and `get_document_file` grant read/download access to an accepted `CaseMember` of `document.case_id`'s case, in addition to owner/admin.
2. **User lookup**: a minimal, non-admin, exact-match endpoint so a case owner can resolve a username/email to a `user_id`.
3. **Invite/membership UI** in `CaseDetail.tsx`: invite by username/email, see accepted + pending-sent members, remove a member — visible only to the case owner.
4. **"My pending invitations" UI**, reachable via the existing `AlertsBell` pattern — accept/decline own invitations.
5. Backend enrichment: `CaseMemberOut` gains joined display fields; `CaseDashboardOut` gains `is_owner` (no way today for the frontend to know this).

## Non-goals — deferred to Phase 2

**Document-level sharing outside any case** (sharing an individual document with a specific person, independent of case membership) is explicitly Phase 2. The case-membership mechanism already exists end-to-end on the backend and just needs the document-access check plus a UI; a standalone doc-share needs a brand-new table/model, invite flow, and endpoints from scratch. Phase 1 also directly fixes the *documented, reproducible* broken UX (case-dashboard document links 403ing) — a from-scratch doc-share feature doesn't fix anything currently broken.

Also out of scope: extending `delete_document` to case members (delete stays owner/admin-only), and extending the main `/documents` list (`Workspace.tsx`) to include case-shared documents automatically — that's a separate UX decision not implied by "fix the 403"; the immediate broken UX is fully fixed without it since `CaseDashboardOut.documents` already lists them.

## Design

### (a) `documents.py` — precise enumeration

Only `get_document` and `get_document_file` change; `list_documents`, `export_documents_csv`, and `delete_document` are not touched:

```python
# new import
from api.cases import is_case_member

async def _can_read_document(db: AsyncSession, document: Document, current_user: User) -> bool:
    if document.owner_id == current_user.id or current_user.role == "admin":
        return True
    if document.case_id is not None:
        return await is_case_member(db, case_id=document.case_id, user_id=current_user.id)
    return False
```

No circular import: `documents.py` currently has zero imports from `api.cases`, and `api.cases` only imports from `api.models`.

- `get_document`: replace the ownership check with `if not await _can_read_document(db, document, current_user): raise 403`.
- `get_document_file`: same replacement.
- `delete_document`: unchanged — stays owner/admin-only.
- `list_documents`/`export_documents_csv`: unchanged — Workspace's own list stays owner-scoped.

### (b) Minimal non-admin user-lookup endpoint

New file `services/api/src/api/users_router.py`:

```python
router = APIRouter(prefix="/users", tags=["users"])

class UserLookupOut(BaseModel):
    id: UUID
    username: str
    display_name: str

@router.get("/lookup", response_model=UserLookupOut)
async def lookup_user(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any authenticated user, not admin-gated
) -> User:
    result = await db.execute(
        select(User).where(or_(func.lower(User.username) == q.lower(), func.lower(User.email) == q.lower()))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user found")
    return user
```

Exact-match only (username OR email, case-insensitive), single result or 404 — deliberately not a partial-match search, so it can't be used to enumerate the user directory. Register in `main.py`; add `/users*` to the Caddyfile `@api` matcher in the same commit.

### (c) Backend enrichment for the invite UI

`CaseMemberOut` gains display fields; both `list_case_members_endpoint` and `list_my_invitations_endpoint` batch-enrich in the router (same "router assembles Pydantic from multiple ORM sources" pattern `get_case_endpoint` already uses):

```python
class CaseMemberOut(BaseModel):
    id: UUID
    case_id: UUID
    case_name: str
    user_id: UUID
    username: str
    user_display_name: str
    role: str
    status: str
    created_at: datetime
```

`CaseDashboardOut` gains `is_owner: bool` (computed as `case.user_id == current_user.id or current_user.role == "admin"` in `get_case_endpoint`).

### (d) `apps/web/src/lib/api.ts` — new wrappers

```typescript
export interface CaseMemberOut {
  id: string; case_id: string; case_name: string; user_id: string;
  username: string; user_display_name: string; role: "worker" | "member";
  status: "pending" | "accepted" | "declined"; created_at: string;
}
export function listCaseMembers(caseId: string): Promise<CaseMemberOut[]> { ... }
export function inviteCaseMember(caseId: string, userId: string, role: "worker" | "member"): Promise<CaseMemberOut> { ... }
export function removeCaseMember(caseId: string, userId: string): Promise<void> { ... }
export function listMyCaseInvitations(): Promise<CaseMemberOut[]> { ... } // GET /cases/invitations
export function acceptCaseInvitation(caseId: string, userId: string): Promise<CaseMemberOut> { ... }
export function declineCaseInvitation(caseId: string, userId: string): Promise<CaseMemberOut> { ... }
export function lookupUser(q: string): Promise<{ id: string; username: string; display_name: string } | null> { ... } // 404 -> null, not throw
```

`CaseDashboardOut` gains `is_owner: boolean`.

### (e) `CaseDetail.tsx` — new "Members" card

A fifth `Card`, rendered only when `caseData.is_owner` shows the invite control; all users see the accepted-members list:

- Invite flow: text input (username or email) + "Invite" button → `lookupUser(q)` → if found, show a small confirm chip (`display_name`, a role `<select>` worker/member) → `inviteCaseMember(caseId, user.id, role)` → refresh. If `lookupUser` returns `null`, show `t("caseDetail.userNotFound")` inline.
- Members list: rows from `listCaseMembers(caseId)` filtered to `status === "accepted"`, each showing `user_display_name` + `role`, with a remove button (owner-only) calling `removeCaseMember`.
- Pending-sent invitations (owner-only): rows filtered to `status === "pending"`, letting the owner cancel by calling `removeCaseMember` (the existing endpoint doesn't distinguish pending vs accepted, so "remove" and "revoke invite" are the same call).

### (f) "My pending invitations" — where it lives

Extend the existing `AlertsBell.tsx`, which already implements exactly this shape for entity reviews: `getPendingReviewEntityCount()` → badge count → `Dropdown` that navigates on select.

- `AlertsBell.tsx` adds a second `useEffect` calling `listMyCaseInvitations()`, merging its count into the existing badge.
- `Cases.tsx` gains a "Pending invitations" `Card`/banner at the top of the page (only rendered when non-empty) — each row shows `case_name`, and Accept/Decline buttons calling `acceptCaseInvitation`/`declineCaseInvitation`, then removes itself from the list and (on accept) triggers the main cases list to refresh. Same "bell → navigate → real accept/decline UI lives on the target page" shape the entity-review flow already established.

## Testing

- Backend `test_documents.py` (existing): a document with `case_id` set is readable/downloadable by an *accepted* case member who is not the owner; still 403 for a *pending* member; still 403 for an unrelated user; `delete_document` still 403s for a case member.
- Backend `test_users.py` (new): `/users/lookup?q=` exact-matches username or email case-insensitively; 404 on no match; no auth → 401; a partial substring does not match.
- Backend `test_cases.py` (existing): `CaseMemberOut` responses include `case_name`/`username`/`user_display_name`; `CaseDashboardOut.is_owner` is `true` for the case creator, `false` for an accepted non-owner member.
- Frontend `CaseDetail.test.tsx` (existing): Members card renders invite controls only when `is_owner`; invite flow calls `lookupUser` then `inviteCaseMember`; a not-found lookup shows the inline error, no invite call made; remove button calls `removeCaseMember` and refreshes.
- Frontend `Cases.test.tsx` / `AlertsBell.test.tsx` (existing): pending-invitations banner/badge renders only when `listMyCaseInvitations()` is non-empty; accept/decline call the right endpoints and remove the row.
