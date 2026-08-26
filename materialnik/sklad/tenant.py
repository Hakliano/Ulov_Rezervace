"""Tenant z credentials/session — nikdy z URL nebo JSON body jako zdroj pravdy."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

_tenant_id: ContextVar[UUID | None] = ContextVar('materialnik_tenant_id', default=None)
_bypass: ContextVar[bool] = ContextVar('materialnik_tenant_bypass', default=False)


class TenantRequiredError(RuntimeError):
    pass


def get_tenant_id():
    return _tenant_id.get()


def set_tenant_id(value):
    return _tenant_id.set(value)


def reset_tenant_id(token):
    _tenant_id.reset(token)


def bypass_tenant(enabled=True):
    return _bypass.set(enabled)


def tenant_bypass():
    return _bypass.get()


def require_tenant_id():
    tid = get_tenant_id()
    if tid is None and not tenant_bypass():
        raise TenantRequiredError('Chybí tenant kontext.')
    return tid
