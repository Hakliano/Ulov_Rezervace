from rest_framework.permissions import BasePermission

from flow.auth import get_flow_user_from_request


class FlowPermission(BasePermission):
    """Vyžaduje platný X-Flow-Token."""

    def has_permission(self, request, view):
        return get_flow_user_from_request(request) is not None
