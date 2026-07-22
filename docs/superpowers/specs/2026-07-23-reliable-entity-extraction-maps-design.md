# Reliable Entity Extraction + Maps Links — Design

## Context

User complaint: extracted addresses are "never a full address," and wants
entity extraction to be fully automatic "like it worked in v2" (with the
caveat, confirmed during this brainstorm, that v2 actually auto-extracted
*less* than this app already does — only `correspondent`/organization
entities, never addresses; the real ask is v2-level *reliability*, achieved
through full automation, which is a higher bar than v2 ever hit).

Live production data (`178.254.22.178`, queried directly, 2026-07-23)
confirms the complaint is real and worse than expected:

- 15 `AddressDetail` rows exist. **Only 1** has any structured field
  populated (`street='Gaslaan', house_number='16', postal_code='9671 CT',
  city='WINSCHOTEN'`). The other 14 have a raw `name` string that's
  frequently address-shaped ("Achterweg 15", "9671 CT WINSCHOTEN", "26831
  Bunde") but every structured column is `NULL`.
- Several extractions are outright misclassified, not just malformed: an
  email address, a URL, and a person's salutation line ("t.a.v. mevrouw A.
  Thole") were extracted as `entity_type="address"` and only caught because
  a human rejected them via the review queue.
- **Zero** `Residency` rows exist anywhere in the database, despite the
  temporal residency-timeline feature (`entity_agent.py`, commit `95a1bd5`,
  2026-07-11) being wired to fire automatically on every
  `RESIDENCE_CATEGORY_SLUGS` document. It has never once produced a row in
  production.
- The same real address ("Gaslaan 16") exists as two separate fragmented
  `AddressDetail` rows — one garbage (empty fields), one good — instead of
  one complete record.

Separately: `person`/`location`/`other` entity types are **currently,
deliberately** excluded from auto-extraction. `entity_agent.py:26-31`:
"Person/location/other entities were the dominant source of low-quality
'random entity' noise... and are now manual-only." Given organization/
address — the two types judged "trustworthy enough" for that decision —
are themselves this unreliable, broadening scope before fixing the
underlying quality problem would make the noise problem worse, not better.

## Goal

Get automatic entity extraction to a state where: addresses are actually
complete (structured fields populated, not just a raw string), garbage
entities (emails/URLs/salutations) never get created as address/person
entities in the first place (code-level guardrail, not prompt-only), the
residency timeline actually produces rows, duplicate fragments of the same
real-world address merge into one complete record, and — once all of the
above is proven reliable — person/location entities can be safely
auto-extracted using the same guardrail pattern. Complete addresses should
produce a maps link, surfaced in the web UI and in a new Signal
notification when a residency is confirmed.

**Explicitly out of scope for this spec** (flagged during brainstorming as
a separate, bigger piece that depends on this foundation): cross-document
knowledge reconciliation — merging/enriching entity data by cross-
referencing *multiple* documents' partial extractions into one fuller
picture over time. That's a real, valuable follow-up once single-document
extraction itself is reliable, not before.

## Architecture

Six components, in dependency order (1-4 must land before 5 is useful, and
before 6 is safe to attempt):

```
Document text
     |
     v
entity_agent.py: LLM identifies "this text span is an address" (semantic)
     |
     v
[NEW] address_parser.py: parse_address(text) -> structured fields (syntactic, deterministic)
     |
     v
[NEW] classification guardrail: reject if text matches email/URL/salutation pattern
     |
     v
entity_agent.py: dedup/merge against existing AddressDetail rows (partial-match fill-in, not fragment-create)
     |
     v
entity_agent.py: _update_residency (bug-fixed) -> Residency row
     |
     v
[NEW] build_maps_url() -> surfaced in web UI + Signal notification on residency confirmation
```

### 1. `address_parser.py` (new file)

**Responsibility**: turn a raw address-like string into structured fields,
deterministically. No LLM call, no network I/O — pure string parsing, so
it's fast, free, and independently unit-testable without mocking Ollama.

```python
def parse_address(raw_text: str) -> dict[str, str | None]:
    """Returns {"street": ..., "house_number": ..., "postal_code": ...,
    "city": ..., "country": ...} -- any field not confidently parsed is None,
    never guessed."""
```

Regex-based, covering the two formats seen in real production data so far:
- **NL postal code**: `\d{4}\s?[A-Z]{2}` (e.g. `9671 CT`), typically
  followed by the city name.
- **DE postal code**: `\b\d{5}\b` (e.g. `26831`), typically followed by the
  city name.
- **Street + house number**: a leading word sequence followed by a number,
  optionally with a letter suffix (`Achterweg 15`, `Gaslaan 16`).

This deliberately does NOT try to be a general-purpose international
address parser — it's scoped to the NL/DE patterns this app's real
documents actually contain (per the live data above), matching the
project's established YAGNI discipline. If a string doesn't match any
pattern confidently, every field stays `None` rather than a wrong guess.

Also in this module: `build_maps_url(street, house_number, postal_code,
city, country) -> str | None`, joining whichever fields are non-`None`
into a Google Maps universal search link
(`https://www.google.com/maps/search/?api=1&query=<urlencoded fields>`).
Returns `None` if there isn't enough to build a meaningful query (e.g. only
a country). No API key needed — this is a plain web link, works whether or
not the recipient has the Google Maps app.

### 2. Classification guardrail (in `entity_agent.py`)

Before `_get_or_create_address_entity` (or a future person-entity
equivalent) ever creates an `Entity` row, reject text matching:
- Contains `@` (email) or `http`/`www.` (URL).
- Matches a "directed at a person" pattern: `t.a.v.`, `de heer`,
  `mevrouw`, `dhr.`, `mw.` (case-insensitive), which are salutation
  prefixes, not addresses.

This is a **code-level filter**, not a prompt instruction — this project
already has a documented lesson (`ai_gateway.py`'s own docstring, re:
`json_mode`) that prompt-only constraints on small local models are
unreliable and grammar/code-level enforcement is required. Rejected
candidates are logged (not silently dropped) so extraction failures stay
diagnosable, same discipline as `manager_agent.py`'s tool-call error
handling.

### 3. Residency-trigger bug fix (in `entity_agent.py` / `document_classification.py`)

Root cause not yet known — needs a live trace before fixing, not a blind
guess. Investigation plan:
1. Query production: has any real document actually been assigned a
   category slug in `RESIDENCE_CATEGORY_SLUGS = {"identity_document",
   "mortgage_housing", "rental_contract", "government"}`? If zero
   documents ever get classified into those slugs, the bug is in
   `document_classification.py`, not `entity_agent.py`.
2. If documents ARE classified correctly, add temporary logging around
   `_update_residency`'s call site (`entity_agent.py:268-272`) to see if
   it's reached at all, and if so, whether it raises (check for a silently
   swallowed exception — `extract_entities`'s caller in `documents.py`'s
   event-handler wiring is a plausible place for a broad `except Exception`
   to hide this, same class of bug as the pre-existing `except Exception`
   noted in `manager_agent.py:63` for preference lookups, though that one
   is intentional and documented).
3. Fix whatever's actually found — this section of the plan will name the
   exact bug once step 1/2 locate it.

### 4. Dedup/merge fix (in `entity_agent.py`, `_get_or_create_address_entity`)

Current behavior (`_normalize_address_key`, `entity_agent.py:95-99`)
presumably requires enough matching fields to compute a stable key: since
14/15 real rows have all-`None` structured fields, they likely never
produced a comparable key at all, so every extraction of "the same"
real-world address created a new fragment instead of matching an existing
one. Once (1)+(2) make structured fields actually populate reliably, match
a new extraction against an existing `AddressDetail` for the same user
using this priority order (first rule that both rows have enough data to
evaluate wins):
1. `postal_code` + `house_number` match (most reliable — postal code
   alone is near-unique to a single building in NL/DE).
2. `street` (case-insensitive) + `house_number` match, if either row lacks
   `postal_code`.
3. Fall back to the existing exact-string `name` match (today's behavior)
   only if neither row has enough structured data to try (1) or (2).
On a match, fill in any field that's `None` on the existing row from the
new extraction (never overwrite an already-populated field with a new
value — surface a conflict for human review instead, same
`pending_review` mechanism already used for new entities). On no match,
create a new `Entity` + `AddressDetail` as today.

### 5. Maps link surfacing

- **Web**: expose `maps_url` as a computed field on address-entity API
  responses (`entities.py`, the `GET /entities/{id}` response model),
  consumed by `AddressHistory.tsx` and the entity detail view as a link
  ("Open in Maps").
- **Signal**: new notification, reusing the existing `signal_client.py`
  Phase-3c pattern (direct message to the document/residency owner, not
  the shared bot account), fired when a `Residency` row transitions to
  `status="confirmed"` **and** its linked `AddressDetail` has all of
  street/house_number/postal_code/city populated (`country` stays
  optional — this app's real documents so far are NL/DE only, and a
  missing country shouldn't block an otherwise-complete, useful maps
  link). Partial addresses don't get a notification: a strictly-worse
  maps link isn't useful, and gating on completeness doubles as a live
  correctness signal — if notifications never fire, that itself flags the
  pipeline isn't producing complete data.

### 6. Extend auto-extraction to person/location (only after 1-4 land and prove out)

Add `"person"`, `"location"` to `AUTO_EXTRACTED_ENTITY_TYPES`
(`entity_agent.py:32`), reusing the same guardrail pattern from (2)
generalized beyond just addresses (e.g. a person-name plausibility check,
still code-level not prompt-only). This directly reverses the 2026-07-09
decision to pull these back due to noise — that decision was made when
this exact document-scan mechanism had no code-level guardrails at all
(only prompt instructions), so the fix in (2) is the actual prerequisite
that makes revisiting it reasonable, not just time passing. Scope here is
deliberately light: get org/address solid first, confirm person/location
extraction quality with real production documents before expanding
further (e.g. vehicle/other), don't over-build ahead of evidence.

## Data flow example (address, end to end)

1. Document "huurcontract.pdf" (rental contract) finishes OCR/embedding →
   `EMBEDDINGS_CREATED` event → `entity_agent.extract_entities` runs.
2. LLM scan finds a text span `"Gaslaan 16, 9671 CT Winschoten"`, tags it
   `entity_type="address"`.
3. Guardrail (2) checks it: no `@`/`http`/salutation pattern → passes.
4. `address_parser.parse_address(...)` → `{"street": "Gaslaan",
   "house_number": "16", "postal_code": "9671 CT", "city": "Winschoten",
   "country": None}`.
5. Dedup/merge (4): no existing match → new `Entity` + `AddressDetail`
   created, `status="pending_review"`.
6. Document category is `rental_contract` (in `RESIDENCE_CATEGORY_SLUGS`)
   → `_update_residency` (bug-fixed per (3)) creates a `Residency` row,
   `status="pending_review"`.
7. Human reviews via `/entities/review`, confirms both.
8. Residency confirmation + complete `AddressDetail` → Signal notification
   fires with `build_maps_url(...)` link to the owning user.
9. `AddressHistory.tsx` (Settings) and the entity detail page both show
   the same "Open in Maps" link for this address going forward.

## Error handling

- `address_parser.parse_address` never raises on unparseable input — it
  returns fields as `None`, matching this project's existing "structured
  outputs, no guessing" discipline (`ai_gateway.py`'s `json_mode`
  docstring).
- The classification guardrail rejecting a candidate is a normal, logged
  outcome, not an error — same as `manager_agent.py`'s tool-call failure
  handling (log + continue, don't crash the whole extraction run over one
  bad candidate).
- `build_maps_url` returns `None` (not an empty/broken link) when there's
  insufficient data — callers (web UI, Signal notification trigger) must
  treat `None` as "don't show/send a maps link," not build one anyway.

## Testing

- `test_address_parser.py` (new): table-driven tests against real
  address-shaped strings pulled from the actual production data above
  ("Achterweg 15", "9671 CT WINSCHOTEN", "26831 Bunde", "Gaslaan 16") plus
  the known-bad strings that should now be rejected before ever reaching
  the parser (the email, the URL, the salutation line) — asserting the
  guardrail catches them, not the parser.
- `entity_agent.py` tests: extend existing address-extraction tests
  (`test_entity_agent.py` or equivalent) to assert a garbage candidate
  never creates an `Entity` row at all (guardrail), and that a
  partial-match extraction enriches an existing row instead of creating a
  duplicate (dedup fix).
- Residency bug: once root-caused, add a regression test asserting the
  specific failure mode found — can't write this test until the
  investigation in (3) identifies what actually broke.
- Live verification (this project's established practice, not just unit
  tests): re-run the exact production data query from this doc's Context
  section after deploying, confirm structured-field population rate goes
  from 1/15 to something close to 100% on new extractions, and that at
  least one real `Residency` row now exists.

## Migration note

`Residency.address_entity_id` (`models.py:400`) has no `ondelete` clause,
unlike every other FK in this schema pointing at `entities.id`
(`AddressDetail.entity_id`, `EntityMention`, `EntityRelationship` all
specify `ondelete="CASCADE"`). This causes `merge_entities`
(`entities.py:267-313`) to raise an unhandled `IntegrityError` if the
source entity has a `Residency` row — currently unreachable since merge
isn't exposed in any frontend, but worth an Alembic migration to add
`ondelete="CASCADE"` while touching this code, closing the gap before it
becomes reachable.
