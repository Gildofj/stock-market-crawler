"""Domain exceptions raised by the services and repositories layer.

Callers (routers, engine, tasks) discriminate failure categories by catching
these instead of bare ``Exception``. That decision can be: log + retry on
``DatabaseError``, surface as HTTP 5xx on any ``ServiceError``, or 4xx on
``DataIntegrityError`` when the constraint violation maps to a bad request.

Use ``raise XError("msg") from exc`` to preserve the underlying cause for
debugging without leaking driver-specific exception types up the stack.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for every services-layer failure."""


class DatabaseError(ServiceError):
    """Persistence operation failed (commit, bulk insert, rollback path).

    Indicates an infrastructure-level problem (connection, timeout, dialect
    error). Callers may retry idempotent operations or surface as HTTP 500.
    """


class DataIntegrityError(ServiceError):
    """A write would violate a business invariant.

    Covers duplicate unique keys, missing required FKs, NOT NULL violations
    on user-provided columns, etc. Routers can map this to HTTP 409/422.
    """
