from core.models.schemas import (
    LakeRIDocumentInternalSchema,
    LakeRIDocumentSchema,
    SourceAttributionSchema,
)


def test_public_ri_schema_does_not_expose_text_excerpt():
    fields = set(LakeRIDocumentSchema.model_fields.keys())
    assert "text_excerpt" not in fields


def test_public_ri_schema_keeps_canonical_cvm_link():
    fields = set(LakeRIDocumentSchema.model_fields.keys())
    assert "pdf_url" in fields
    assert "pdf_source" in fields


def test_internal_ri_schema_includes_text_for_lagoai():
    fields = set(LakeRIDocumentInternalSchema.model_fields.keys())
    assert "text_excerpt" in fields


def test_source_attribution_schema_has_renderable_fields():
    fields = set(SourceAttributionSchema.model_fields.keys())
    assert {"slug", "display_name", "homepage_url"}.issubset(fields)
