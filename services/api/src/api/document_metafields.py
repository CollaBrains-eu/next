"""Document metafield extraction: per-doc-type structured field extraction
(sub-project 3, metafields + UI redesign). Runs after classification -- needs
doc_type to pick the right field schema -- following the same single
schema-constrained chat_completion pattern as document_classification.py.
"""
import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import Document

logger = logging.getLogger(__name__)

# (field_name, kind) pairs per doc_type. kind is "string" | "date" -- "date" drives
# the frontend's per-field "add to calendar" affordance without the frontend having
# to string-sniff values. Every date-kind field name ends in "_date" by convention,
# so the frontend can also derive kind from the name alone without a schema fetch.
DOC_TYPE_METAFIELD_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "payslip": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "salary": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "annual_statement": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "tax": [("tax_year", "string"), ("amount_due", "string"), ("filing_deadline_date", "date")],
    "pension": [("monthly_amount", "string"), ("provider", "string")],
    "benefits": [("monthly_amount", "string"), ("provider", "string")],
    "bank_statement": [("account_number", "string"), ("period", "string"), ("closing_balance", "string")],
    "bank": [("account_number", "string"), ("period", "string"), ("closing_balance", "string")],
    "invoice": [("amount", "string"), ("due_date", "date"), ("invoice_number", "string")],
    "receipt": [("vendor", "string"), ("amount", "string"), ("purchase_date", "date")],
    "subscription": [("provider", "string"), ("monthly_amount", "string"), ("renewal_date", "date")],
    "guardianship": [("case_number", "string"), ("court", "string"), ("effective_date", "date")],
    "mortgage": [("loan_amount", "string"), ("interest_rate", "string"), ("property_address", "string")],
    "housing": [("monthly_rent", "string"), ("start_date", "date"), ("property_address", "string")],
    "notarial": [("deed_type", "string"), ("execution_date", "date"), ("notary", "string")],
    "vehicle": [("license_plate", "string"), ("make_model", "string"), ("registration_date", "date")],
    "policy": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
    "insurance": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
    "medical": [("provider", "string"), ("visit_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date")],
    "prescription": [
        ("medication", "string"), ("dosage", "string"), ("prescribing_doctor", "string"), ("issue_date", "date"),
    ],
    "lab_result": [("test_name", "string"), ("result_summary", "string"), ("test_date", "date")],
    "contract": [("counterparty", "string"), ("start_date", "date"), ("end_date", "date")],
    "education": [("institution", "string"), ("program", "string"), ("graduation_date", "date")],
    "cv": [("full_name", "string"), ("most_recent_role", "string")],
    "government": [("reference_number", "string"), ("deadline_date", "date")],
    "identity_document": [
        ("document_number", "string"), ("birth_date", "date"), ("nationality", "string"), ("expiry_date", "date"),
    ],
    "correspondence": [("subject", "string"), ("reply_by_date", "date")],
    "legal": [("case_number", "string"), ("court", "string"), ("hearing_date", "date")],
    "warranty": [("product", "string"), ("vendor", "string"), ("warranty_expiry_date", "date")],
}

METAFIELD_PROMPT = """Extract the following fields from this document, if present. Return \
ONLY a JSON object (no prose, no markdown fences) with exactly these keys: {fields}. Use \
null for any field that isn't clearly present in the document. Format any date-like field \
as YYYY-MM-DD.

Document:
{text}"""


def _schema_for(doc_type: str) -> list[tuple[str, str]]:
    return DOC_TYPE_METAFIELD_SCHEMA.get(doc_type, [])


def _json_schema_for(fields: list[tuple[str, str]]) -> dict:
    return {
        "type": "object",
        "properties": {name: {"type": ["string", "null"]} for name, _ in fields},
        "required": [name for name, _ in fields],
    }


def _parse_metafields(raw: str, fields: list[tuple[str, str]]) -> dict:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.warning("document_metafields: could not parse output: %r", raw[:500])
        return {}

    allowed_keys = {name for name, _ in fields}
    return {key: str(value)[:500] for key, value in payload.items() if key in allowed_keys and value is not None}


async def extract_metafields(*, doc_type: str, text: str, user_id: UUID) -> dict:
    """Extract structured metafields for `doc_type` via the AI Gateway. Returns {} for
    doc_types with no declared schema, or on unparseable model output (graceful
    degradation, same as classify_document -- a bad extraction call must never crash
    the document pipeline it's a subscriber of)."""
    fields = _schema_for(doc_type)
    if not fields:
        return {}

    prompt = METAFIELD_PROMPT.format(fields=", ".join(name for name, _ in fields), text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="document.extract_metafields",
        schema=_json_schema_for(fields),
    )
    return _parse_metafields(raw, fields)


async def extract_and_persist_metafields(
    db: AsyncSession, *, document_id: UUID, doc_type: str, text: str, user_id: UUID
) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None

    metafields = await extract_metafields(doc_type=doc_type, text=text, user_id=user_id)
    if metafields:
        document.metafields = metafields
        await db.commit()
        await db.refresh(document)
    return document


def is_date_field(doc_type: str, field_key: str) -> bool:
    return any(name == field_key and kind == "date" for name, kind in _schema_for(doc_type))
