"""Public RI/news schemas must not leak internal-only fields.

These tests pin the legal posture decided in DISCLAIMER.md / the lineage
plan: the public ``LakeRIDocumentSchema`` exposes a link back to CVM but
not the extracted text body nor the legacy R2 mirror URL. If a future
refactor accidentally re-adds either, this test fails before deploy.
"""

from core.models.schemas import (
    LakeRIDocumentInternalSchema,
    LakeRIDocumentSchema,
    SourceAttributionSchema,
)


def test_public_ri_schema_does_not_expose_text_excerpt():
    fields = set(LakeRIDocumentSchema.model_fields.keys())
    assert "text_excerpt" not in fields, (
        "LakeRIDocumentSchema is the *public* response; text_excerpt belongs "
        "to LakeRIDocumentInternalSchema."
    )


def test_public_ri_schema_does_not_expose_r2_public_url():
    fields = set(LakeRIDocumentSchema.model_fields.keys())
    assert "r2_public_url" not in fields, (
        "RI mirror is deprecated; public schema must not expose r2_public_url."
    )


def test_public_ri_schema_keeps_canonical_cvm_link():
    fields = set(LakeRIDocumentSchema.model_fields.keys())
    assert "pdf_url" in fields, "Public RI schema must expose the upstream CVM URL."
    assert "pdf_source" in fields, "Public RI schema must expose static attribution."


def test_internal_ri_schema_includes_text_for_lagoai():
    fields = set(LakeRIDocumentInternalSchema.model_fields.keys())
    assert "text_excerpt" in fields, (
        "Internal schema must keep text_excerpt so the LagoAI insight "
        "pipeline can consume it without going through the public API."
    )


def test_source_attribution_schema_has_renderable_fields():
    # Front-end contract: enough to render `<a href={homepage_url}>{display_name}</a>`.
    fields = set(SourceAttributionSchema.model_fields.keys())
    assert {"slug", "display_name", "homepage_url"}.issubset(fields)
