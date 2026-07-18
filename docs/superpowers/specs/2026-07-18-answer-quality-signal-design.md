# Answer-Quality Signal: Surface Reflection + Capture User Feedback — Design

## Status
Proposed

## Context

The Reflection Engine (`services/api/src/api/reflection.py`) already computes `sufficient_evidence`, `confidence` (0-100), and `issues` for every grounded chat answer, via a second independent LLM call. Today this is entirely invisible: it's logged to `ReflectionLog` (verdict only, not the answer text), used once to trigger a single bounded retry, and never shown to the user or an admin. Two ADRs (0015, 0030) explicitly reject building a formal eval/training framework — no budget for that, and this design doesn't attempt one.

Two existing signals are computed and thrown away or hidden:
1. The reflection verdict (already computed, zero marginal LLM cost to surface it).
2. Nothing captures whether the *user* actually found an answer useful — no thumbs up/down, no correction mechanism anywhere.

The interesting, currently-impossible correlation: an answer the model was *confident* about but the *user* rejected is exactly the shape of a hallucination worth investigating. Nothing today can surface that case, because the two signals never meet — one is silently logged without the answer text, the other doesn't exist.

## Goals

1. Surface the existing reflection verdict inline on chat answers as a subtle confidence indicator — zero new compute, the number already exists.
2. Add thumbs up/down on chat answers, storing the answer text alongside the vote (nothing persists answer text today) and the reflection verdict computed for that same answer.
3. A small admin view surfacing the interesting cases: thumbs-down answers, and separately, high-confidence-but-thumbs-down answers (the correlation that actually matters) — reusing the existing admin-only reporting pattern (`GET /learning/dataset`).

## Non-goals

- Any new LLM call, eval loop, benchmark suite, or training pipeline — explicitly rejected by ADR 0015/0030 and not reconsidered here.
- Retrying or regenerating an answer based on a thumbs-down — that's a UX escalation decision for later, once there's actual data showing it's warranted.
- Applying this to the Manager Agent's tool-routed answers (`/manager/ask`) in this pass — reflection today only wires into the two direct grounded-chat HTTP endpoints (`chat.py`), a known existing gap per ADR 0020. Scope this to those same endpoints; extending reflection's own coverage is a separate, larger change.

## Design

### New table: `answer_feedback`

```python
class AnswerFeedback(Base):
    __tablename__ = "answer_feedback"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)  # "up" | "down"
    reflection_confidence: Mapped[int | None] = mapped_column(nullable=True)
    reflection_sufficient_evidence: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

`chat.py`'s `answer_grounded_question()` already has the reflection result in scope at the point it returns — thread `reflection_confidence`/`reflection_sufficient_evidence` through the response so the frontend can round-trip them back on the feedback call (avoids a second DB lookup to correlate feedback with its reflection verdict).

### Backend endpoint

```python
# new: services/api/src/api/feedback_router.py
router = APIRouter(prefix="/feedback", tags=["feedback"])

class FeedbackIn(BaseModel):
    endpoint: str
    question: str
    answer: str
    rating: Literal["up", "down"]
    reflection_confidence: int | None = None
    reflection_sufficient_evidence: bool | None = None

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(body: FeedbackIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    db.add(AnswerFeedback(user_id=current_user.id, **body.model_dump()))
    await db.commit()
```

### `chat.py` response gains the reflection verdict

`ChatResponse` (or equivalent) gains `confidence: int | None` and `sufficient_evidence: bool | None`, populated from the reflection result already computed inside `answer_grounded_question()` — no new call, just returning a value already sitting in a local variable.

### Frontend

- `apps/web/src/components/ui/ChatLog.tsx` (existing chat bubble renderer): each assistant message gains two small icon buttons (thumbs up/down, reuse `icon-btn` styling already in the design system) and, when `confidence` is present and below a threshold (propose `< 60`), a subtle `Badge variant="warning"` reading `t("chat.lowConfidence")` — this is the "surface the hidden signal" half, requires no new interaction, just rendering a number that already exists in the response.
- Clicking a thumbs button calls a new `submitFeedback()` wrapper in `api.ts`, disables both buttons for that message (one vote per answer, no toggle/undo needed for v1), and shows a brief inline "Thanks" acknowledgment (reuse the existing toast pattern).

### Admin view

- New `GET /admin/feedback?rating=down&min_confidence=` (admin-gated, same `_require_admin` pattern already used throughout `admin_router.py`) — returns recent `AnswerFeedback` rows, filterable by rating and reflection confidence, so an admin can specifically query "high-confidence answers a user rejected" (`rating=down&min_confidence=70`) — the actual hallucination-hunting query this design exists to make possible.
- A small new tab in `AdminDashboard.tsx` (matching the existing tab pattern — `UsersTab`, etc.) listing these rows: question, answer, rating, confidence, date. No editing, no dataset export in this pass — just visibility.

## Testing

- Backend `test_feedback.py` (new): `POST /feedback` persists a row with the correct user/rating/reflection fields; requires auth.
- Backend `test_admin_router.py` (existing file, extend): `GET /admin/feedback` 403s for non-admin; filters correctly by `rating` and `min_confidence`.
- Backend `test_chat.py` (existing): grounded chat response includes `confidence`/`sufficient_evidence` matching the reflection call's result.
- Frontend `ChatLog.test.tsx` (existing): low-confidence badge renders only below threshold; thumbs click calls `submitFeedback` with the right payload and disables further votes on that message.
