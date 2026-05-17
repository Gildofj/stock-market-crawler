"""SourceRegistry behavior: lookups, URL heuristics, and fail-open policy."""

from crawler.services.source_registry import (
    SourceNotFoundError,
    SourceRecord,
    SourceRegistry,
    get_source_registry,
)


def _seeded_registry() -> SourceRegistry:
    """A SourceRegistry pre-populated with two records, no DB touch."""
    registry = SourceRegistry()
    registry._by_slug = {
        "cvm": SourceRecord(
            id="00000000-0000-0000-0000-000000000001",
            slug="cvm",
            display_name="CVM",
            homepage_url="https://dados.cvm.gov.br/",
            tos_url=None,
            license_label="public-domain",
            risk_tier="low",
            enabled=True,
        ),
        "infomoney": SourceRecord(
            id="00000000-0000-0000-0000-000000000002",
            slug="infomoney",
            display_name="InfoMoney",
            homepage_url="https://www.infomoney.com.br/",
            tos_url="https://www.infomoney.com.br/termos-de-uso/",
            license_label="rss-fair-use",
            risk_tier="medium",
            enabled=False,  # Simulates a takedown response.
        ),
    }
    registry._loaded_at = float("inf")  # Skip refresh.
    return registry


def test_get_returns_seeded_record():
    registry = _seeded_registry()
    record = registry.get("cvm")
    assert record.display_name == "CVM"
    assert record.enabled is True


def test_get_raises_for_unknown_slug(monkeypatch):
    registry = _seeded_registry()
    # Block refresh from masking the miss by also blanking _by_slug after.
    monkeypatch.setattr(registry, "refresh", lambda *a, **kw: None)
    try:
        registry.get("does-not-exist")
    except SourceNotFoundError:
        pass
    else:
        raise AssertionError("Expected SourceNotFoundError for unknown slug.")


def test_is_enabled_respects_kill_switch():
    registry = _seeded_registry()
    assert registry.is_enabled("cvm") is True
    assert registry.is_enabled("infomoney") is False, (
        "Operator disabled InfoMoney via SQL — registry must reflect that."
    )


def test_is_enabled_fails_open_for_unknown(monkeypatch):
    """Unknown slug ≠ disabled. Fail-open avoids stopping collection on a
    missing migration or typo. Explicit operator action is required to halt."""
    registry = _seeded_registry()
    monkeypatch.setattr(registry, "refresh", lambda *a, **kw: None)
    assert registry.is_enabled("not-seeded-yet") is True


def test_slug_for_url_recognizes_known_hosts():
    registry = _seeded_registry()
    assert registry.slug_for_url("https://www.infomoney.com.br/foo/bar") == "infomoney"
    assert registry.slug_for_url("https://dados.cvm.gov.br/feed") == "cvm"
    assert registry.slug_for_url("https://www.unknown-site.com/page") is None
    assert registry.slug_for_url(None) is None
    assert registry.slug_for_url("") is None


def test_all_enabled_sorts_by_display_name():
    registry = _seeded_registry()
    # Re-enable infomoney to test ordering with multiple entries.
    registry._by_slug["infomoney"] = SourceRecord(
        **{**registry._by_slug["infomoney"].__dict__, "enabled": True}
    )
    enabled = registry.all_enabled()
    assert [r.slug for r in enabled] == ["cvm", "infomoney"], (
        "all_enabled must sort by display_name alphabetically."
    )


def test_singleton_accessor_returns_same_instance():
    a = get_source_registry()
    b = get_source_registry()
    assert a is b
