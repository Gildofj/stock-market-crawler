"""Cloudflare R2 storage client (S3-compatible).

Active surface:

* ``portfolios`` — **private**, accessed via short-lived presigned URLs.

Legacy surface (kept for backwards compatibility, not used by current
spiders):

* ``ri-docs`` — was a public CDN-served mirror of CVM PDFs. Mirroring was
  removed because the upstream CVM URL is already public, durable, and
  free of redistribution claims. ``upload_ri_pdf`` is preserved so existing
  Terraform / env stays valid; new callers must not use it. See
  ``DISCLAIMER.md`` for rationale.

The client degrades gracefully when R2 credentials are not configured: every
write returns ``None`` and every read returns ``None``. This lets local /
free-tier deployments run without R2 set up.
"""

from __future__ import annotations

from typing import IO, Any

from loguru import logger

from crawler.services.config import settings


class R2Storage:
    """Thin S3-compatible wrapper for Cloudflare R2."""

    def __init__(self) -> None:
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return settings.r2_enabled

    def _client_or_none(self) -> Any | None:
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client

        creds = settings.r2_credentials
        if not creds:
            return None

        access_key, secret_key = creds

        import boto3  # local import keeps cold-start light when R2 is off
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )
        return self._client

    def upload_ri_pdf(
        self,
        key: str,
        body: bytes,
        content_type: str = "application/pdf",
    ) -> tuple[str, str | None] | None:
        """DEPRECATED. Mirroring CVM PDFs is no longer supported.

        Calling this raises a ``DeprecationWarning`` and uploads nothing.
        The method signature is preserved so old deploys keep importing,
        but every invocation is a no-op returning ``None``. Drop the call
        and store the upstream CVM URL instead — that is the canonical,
        legally clean reference.
        """
        import warnings

        warnings.warn(
            "R2Storage.upload_ri_pdf is deprecated and a no-op. "
            "Store the upstream CVM URL (pdf_url) instead of mirroring the PDF.",
            DeprecationWarning,
            stacklevel=2,
        )
        return None

    def upload_portfolio_file(
        self,
        key: str,
        body: bytes | IO[bytes],
        content_type: str,
    ) -> str | None:
        """Uploads a portfolio spreadsheet to the private bucket."""
        client = self._client_or_none()
        if client is None:
            return None
        try:
            client.put_object(
                Bucket=settings.R2_BUCKET_PORTFOLIOS,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
            return key
        except Exception as e:
            logger.error(f"R2: upload_portfolio_file failed for {key}: {e}")
            return None

    def presigned_portfolio_url(
        self,
        key: str,
        expires_in: int | None = None,
    ) -> str | None:
        """Generates a short-lived GET URL for a private portfolio object."""
        client = self._client_or_none()
        if client is None:
            return None
        try:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.R2_BUCKET_PORTFOLIOS, "Key": key},
                ExpiresIn=expires_in or settings.R2_PRESIGN_TTL_SECONDS,
            )
        except Exception as e:
            logger.error(f"R2: presigned_portfolio_url failed for {key}: {e}")
            return None


_storage: R2Storage | None = None


def get_storage() -> R2Storage:
    """Lazy singleton accessor for the R2 storage client."""
    global _storage
    if _storage is None:
        _storage = R2Storage()
    return _storage
