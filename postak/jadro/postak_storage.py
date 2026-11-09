"""Úložiště souborů Pošťáka — lokální disk nebo Bunny.net (prefix postak/)."""

from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

from .bunny_client import BunnyStorageError, get_bunny_client


@deconstructible
class PostakBunnyStorage(Storage):
    """Soubory Pošťáka — Bunny Storage nebo lokální disk (bez generování URL z FileField)."""

    def __init__(self):
        self._local = FileSystemStorage(location=settings.MEDIA_ROOT)

    def _client(self):
        return get_bunny_client()

    def _use_bunny(self) -> bool:
        return self._client() is not None

    def deconstruct(self):
        return (PostakBunnyStorage.__qualname__, [], {})

    def _open(self, name, mode='rb'):
        if 'w' in mode:
            raise ValueError('Použijte save().')
        if self._use_bunny():
            data = self._client().get(name)
            return ContentFile(data)
        return self._local._open(name, mode)

    def _save(self, name, content):
        if self._use_bunny():
            client = self._client()
            if hasattr(content, 'chunks'):
                data = b''.join(content.chunks())
            else:
                data = content.read()
            client.put(name, data, content_type=getattr(content, 'content_type', None) or 'application/octet-stream')
            return name
        return self._local._save(name, content)

    def delete(self, name):
        if self._use_bunny():
            self._client().delete(name)
            return
        self._local.delete(name)

    def exists(self, name):
        if self._use_bunny():
            return self._client().exists(name)
        return self._local.exists(name)

    def size(self, name):
        if self._use_bunny():
            return len(self._client().get(name))
        return self._local.size(name)

    def path(self, name):
        if self._use_bunny():
            raise NotImplementedError('Bunny storage nemá lokální cestu.')
        return self._local.path(name)

    def url(self, name):
        raise NotImplementedError('Soubory Pošťáka nemají veřejné URL — stahujte přes aplikaci.')

    def get_available_name(self, name, max_length=None):
        if self._use_bunny():
            return name
        return self._local.get_available_name(name, max_length)


def read_storage_file(field_file) -> bytes:
    with field_file.open('rb') as f:
        return f.read()
