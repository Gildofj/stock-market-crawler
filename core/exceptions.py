from __future__ import annotations


class ServiceError(Exception):
    pass


class DatabaseError(ServiceError):
    pass


class DataIntegrityError(ServiceError):
    pass
