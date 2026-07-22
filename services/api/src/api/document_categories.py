"""Document category taxonomy (Phase 24, ported from CollaBrains v2's
seed_categories.py -- see docs/superpowers/plans/2026-07-10-document-categories.md).

Slugs and doc_types are English identifiers, not user-facing strings --
display names live in apps/web/src/locales/{en,nl,de}.json under the
"categories" namespace, keyed by slug. This is the one difference from
v2's approach, which baked Dutch names directly into this data; the
taxonomy structure itself (6 parent groups, ~20 subcategories) is
otherwise a direct port.
"""

DOCUMENT_CATEGORIES: list[dict] = [
    # -- Finance --
    {"slug": "finance", "icon": "Coins", "color": "#FF9500", "parent": None, "doc_types": []},
    {"slug": "payslip", "icon": "Banknote", "color": "#FF9500", "parent": "finance",
     "doc_types": ["payslip", "salary", "annual_statement"]},
    {"slug": "tax", "icon": "Landmark", "color": "#FF3B30", "parent": "finance", "doc_types": ["tax"]},
    {"slug": "pension_benefits", "icon": "PiggyBank", "color": "#FFCC00", "parent": "finance",
     "doc_types": ["pension", "benefits"]},
    {"slug": "bank_statement", "icon": "Building2", "color": "#34AADC", "parent": "finance",
     "doc_types": ["bank_statement", "bank"]},
    {"slug": "invoice", "icon": "Receipt", "color": "#FF3B30", "parent": "finance",
     "doc_types": ["invoice", "receipt", "subscription"]},
    {"slug": "guardianship", "icon": "Gavel", "color": "#FF9500", "parent": "finance",
     "doc_types": ["guardianship"]},

    # -- Housing & Vehicle --
    {"slug": "housing_vehicle", "icon": "Home", "color": "#34C759", "parent": None, "doc_types": []},
    {"slug": "mortgage_housing", "icon": "Home", "color": "#007AFF", "parent": "housing_vehicle",
     "doc_types": ["mortgage", "housing", "notarial"]},
    {"slug": "vehicle", "icon": "Car", "color": "#FF6B35", "parent": "housing_vehicle", "doc_types": ["vehicle"]},
    {"slug": "rental_contract", "icon": "Key", "color": "#34C759", "parent": "housing_vehicle", "doc_types": []},

    # -- Insurance & Care --
    {"slug": "insurance_care", "icon": "Shield", "color": "#4CD964", "parent": None, "doc_types": []},
    {"slug": "insurance", "icon": "Shield", "color": "#4CD964", "parent": "insurance_care",
     "doc_types": ["policy", "insurance"]},
    {"slug": "medical_care", "icon": "HeartPulse", "color": "#5AC8FA", "parent": "insurance_care",
     "doc_types": ["medical", "care", "prescription", "lab_result"]},

    # -- Work & Education --
    {"slug": "work_education", "icon": "Briefcase", "color": "#5856D6", "parent": None, "doc_types": []},
    {"slug": "employment_contract", "icon": "FileText", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["contract"]},
    {"slug": "education", "icon": "GraduationCap", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["education"]},
    {"slug": "cv_references", "icon": "User", "color": "#5856D6", "parent": "work_education", "doc_types": ["cv"]},

    # -- Government & Identity --
    {"slug": "government_identity", "icon": "Shield", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "government", "icon": "Landmark", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["government"]},
    {"slug": "identity_document", "icon": "CreditCard", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["identity_document"]},
    {"slug": "notarial", "icon": "Scale", "color": "#8E8E93", "parent": "government_identity", "doc_types": []},

    # -- Other --
    {"slug": "other_group", "icon": "Inbox", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "correspondence", "icon": "Mail", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["correspondence"]},
    {"slug": "other_documents", "icon": "File", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["other", "legal", "warranty"]},
]

DOC_TYPE_TO_CATEGORY_SLUG: dict[str, str] = {
    doc_type: cat["slug"] for cat in DOCUMENT_CATEGORIES for doc_type in cat["doc_types"]
}

VALID_DOC_TYPES: frozenset[str] = frozenset(DOC_TYPE_TO_CATEGORY_SLUG) | {"other"}
