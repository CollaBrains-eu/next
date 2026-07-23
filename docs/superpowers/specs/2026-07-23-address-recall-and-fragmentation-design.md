# Address Recall and Fragmentation Fix — Design

**Status:** Approved
**Related:** `docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md` (address parsing/dedup this design extends), `docs/superpowers/plans/2026-07-23-ldap-contact-details.md` (the phone-as-address guardrail fix that surfaced these two issues)

## Problem

Live-verifying the entity extraction pipeline against two real production
documents surfaced two distinct quality gaps, both already tolerated by the
existing review-queue design but worth fixing at the source:

1. **Recall gap**: a clean, well-formatted address ("Jahnstr. 6, 26789 Leer")
   present in a document's text was never proposed as a candidate entity by
   the LLM at all — not a parsing/field-splitting problem (which
   `address_parser.py` already solves), but the LLM's semantic-recognition
   pass simply missing it.
2. **Fragmentation**: a Dutch form with labeled fields ("Straatnaam: Gaslaan
   16" ... "Postcode en woonplaats: 9671CT Winschoten") caused the LLM to
   emit two separate entity items — one with only `street`/`house_number`,
   one with only `postal_code`/`city` — creating two unrelated `Entity` rows
   for what is really one real-world address, instead of one entity with
   `_get_or_create_address_entity`'s existing gap-fill/dedup logic ever
   getting a chance to combine them (that logic dedupes across separate
   *extraction calls*, not across two items *within the same* LLM response).

## Fix 1: Deterministic Fallback Scan (Recall)

New function in `address_parser.py`:

```python
def find_full_address_matches(text: str) -> list[str]:
    """Scan raw text for high-confidence full address matches (street+number+
    postal+city together) -- a recall safety net for addresses the LLM's
    semantic pass didn't propose as a candidate at all. Deliberately uses
    only the strict _FULL_NL_RE/_FULL_DE_RE patterns (all four parts
    present), not the looser postal-only or street-only fallbacks
    parse_address() also tries -- scanning arbitrary document prose with a
    loose pattern would flag invoice numbers, case numbers, etc. as false
    positives.
    """
```

In `entity_agent.py`'s `extract_entities()`, after the main LLM-entity loop
finishes: scan `text` with `find_full_address_matches`, and for each match
run it through the *existing* `_get_or_create_address_entity()`. If the LLM
already found the same address (the common case), the existing dedup logic
(`_find_matching_address_entity`) returns/gap-fills that same entity —
nothing new is created. Only genuinely-missed addresses add a new entity,
which then also goes through the existing garbage-address guardrail like
any other address candidate.

## Fix 2: Same-Batch Complementary Merge (Fragmentation)

New helper `_maybe_merge_complementary_address_fragments()` in
`entity_agent.py`, run once per `extract_entities()` call after all of that
call's address entities (from both the LLM loop and the Fix 1 fallback
scan) are known, and *before* residency detection uses
`address_entity_ids[0]`:

- Only acts when this single extraction call produced **exactly 2** address
  entities. Three or more, or just one, means nothing to (safely) merge.
- Only merges if one entity's `AddressDetail` has `street` and/or
  `house_number` populated but *not* both `postal_code` and `city`, and the
  other has `postal_code` and/or `city` populated but *not* both `street`
  and `house_number` — i.e. two genuinely complementary fragments. Two
  candidates that each already look like a complete-ish address (e.g. a
  rental contract's landlord address and property address) never match this
  shape and are correctly left separate.
- On merge: gap-fills the kept entity's `AddressDetail` from the absorbed
  one (never overwrites a populated field — same rule as everywhere else in
  this pipeline), moves the absorbed entity's `EntityMention` to the kept
  entity, deletes the absorbed entity, and writes an `EntityMergeLog` row
  (`merged_by` = the document's owner, since this merge is a side effect of
  their upload, not a manual action) — the same audit trail the existing
  manual-merge endpoint (`entities.py`'s `merge_entity`) already produces,
  so a human reviewing entity history can see *why* a duplicate address
  disappeared.
- The kept entity is whichever of the two appears first in
  `address_entity_ids` (the order they were created/touched in this call) —
  arbitrary but deterministic.

## Interaction Between the Two Fixes

A fallback-scanned match (Fix 1) always has all four fields populated
together (the strict regex requires it), so it can never itself be one side
of a Fix 2 merge — it composes cleanly: Fix 1 adds complete addresses the
LLM missed; Fix 2 combines incomplete fragments the LLM did propose but
split across two items.

## Testing

- `test_address_parser.py`: `find_full_address_matches` returns the matched
  substring when a full address appears in surrounding prose (e.g. `"Wo?
  Jahnstr. 6, 26789 Leer\nRaum: ..."`), and an empty list when no full
  address is present.
- `test_entities.py`:
  - An address absent from the LLM's entity list but present in the raw
    document text gets created via the fallback scan.
  - A street-only fragment and a postal+city-only fragment in the same
    extraction merge into one address entity with all four fields
    populated, and an `EntityMergeLog` row records it.
  - Two extraction items that each already carry enough fields to look like
    complete, distinct addresses (e.g. two different `postal_code`s) are
    *not* merged.

## Out of Scope

- Prompt tuning to improve LLM recall directly — this project's established
  lesson is that prompt-only instructions aren't reliable on this small
  local model; the deterministic fallback scan is the reliable fix.
- Merging across more than 2 same-batch address fragments, or across
  different documents/extraction calls — both stay unmerged, `pending_review`,
  and available for manual merge via the existing endpoint if a human judges
  it correct.
