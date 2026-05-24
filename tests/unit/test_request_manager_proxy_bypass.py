"""Tests for the selective proxy bypass added to RequestManager.

The bypass routes Brazilian public-data hosts (B3 / CVM / BCB) around the
residential proxy. The proxy itself is a webshare endpoint that often loses
auth credentials during deploys and starts 407-ing every request — bypassing
known-public hosts keeps the universe-refresh job healthy even when the
proxy is broken.
"""

from __future__ import annotations

import pytest

from crawler.services.request_manager import RequestManager


@pytest.fixture
def proxied_manager() -> RequestManager:
    manager = RequestManager(
        proxies=["http://user:pass@proxy.example.com:8080"],
        bypass_domains=frozenset({"dados.cvm.gov.br", "arquivos.b3.com.br"}),
    )
    yield manager
    manager._session.close()
    if manager._session_direct is not manager._session:
        manager._session_direct.close()


def test_bypass_exact_match(proxied_manager: RequestManager):
    assert proxied_manager._should_bypass("https://dados.cvm.gov.br/foo/bar") is True


def test_bypass_subdomain_match(proxied_manager: RequestManager):
    # The bypass rule must also catch deeper subdomains so we don't accidentally
    # route api.dados.cvm.gov.br through the proxy when its parent is exempt.
    assert (
        proxied_manager._should_bypass("https://api.dados.cvm.gov.br/v1/cad") is True
    )


def test_no_bypass_for_unrelated_host(proxied_manager: RequestManager):
    assert proxied_manager._should_bypass("https://www.example.com/path") is False


def test_proxy_session_used_when_not_bypassed(proxied_manager: RequestManager):
    # When a host is not in the bypass set, requests must go through the
    # proxied session (the one constructed with a `proxy=` kwarg).
    assert proxied_manager._should_bypass("https://www.bcb.gov.example/") is False
    assert proxied_manager._session is not proxied_manager._session_direct


def test_direct_session_aliased_when_no_proxy_configured():
    # No proxy → no point in spinning up a second connection pool. Both
    # sessions must alias to the same underlying object so close() is idempotent.
    manager = RequestManager(proxies=None)
    try:
        assert manager._session is manager._session_direct
        assert manager._async_session is manager._async_session_direct
    finally:
        manager._session.close()


def test_bypass_set_loaded_from_settings_when_not_passed(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(
        settings,
        "CRAWLER_PROXY_BYPASS_DOMAINS",
        "dados.cvm.gov.br,arquivos.b3.com.br",
    )
    manager = RequestManager(proxies=["http://u:p@px:80"])
    try:
        assert "dados.cvm.gov.br" in manager._bypass
        assert manager._should_bypass("https://arquivos.b3.com.br/x") is True
    finally:
        manager._session.close()
        if manager._session_direct is not manager._session:
            manager._session_direct.close()


def test_empty_bypass_set_disables_bypass():
    manager = RequestManager(proxies=["http://u:p@px:80"], bypass_domains=frozenset())
    try:
        assert manager._should_bypass("https://dados.cvm.gov.br/anything") is False
    finally:
        manager._session.close()
        if manager._session_direct is not manager._session:
            manager._session_direct.close()
