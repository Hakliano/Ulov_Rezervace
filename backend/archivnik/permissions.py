from rest_framework.permissions import BasePermission

from archivnik.auth import get_actor_from_request


class ArchivnikPermission(BasePermission):
    def has_permission(self, request, view):
        return get_actor_from_request(request) is not None
