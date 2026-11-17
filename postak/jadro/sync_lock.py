"""Souborový zámek proti souběhu sync běhů (cron + ruční tlačítko)."""

from __future__ import annotations

import os
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # Windows / některá dev prostředí
    fcntl = None  # type: ignore[assignment]

LOCK_DIR = os.environ.get('POSTAK_SYNC_LOCK_DIR', '/var/lock')


class SyncAlreadyRunning(Exception):
    pass


@contextmanager
def sync_file_lock(name: str):
    if fcntl is None:
        yield
        return
    os.makedirs(LOCK_DIR, exist_ok=True)
    path = os.path.join(LOCK_DIR, f'postak-sync-{name}.lock')
    with open(path, 'a+', encoding='utf-8') as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SyncAlreadyRunning(name) from exc
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)