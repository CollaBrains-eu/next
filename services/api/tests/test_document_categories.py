from api.document_categories import DOC_TYPE_TO_CATEGORY_SLUG, VALID_DOC_TYPES

NEW_DOC_TYPE_CATEGORIES = {
    "receipt": "invoice",
    "subscription": "invoice",
    "prescription": "medical_care",
    "lab_result": "medical_care",
    "warranty": "other_documents",
}


def test_new_doc_types_are_valid_and_mapped_to_the_expected_category():
    for doc_type, category_slug in NEW_DOC_TYPE_CATEGORIES.items():
        assert doc_type in VALID_DOC_TYPES
        assert DOC_TYPE_TO_CATEGORY_SLUG[doc_type] == category_slug
