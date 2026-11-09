from .chat_services import pocet_neprectenych


def chat_badge(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'chat_neprectenych': 0}
    return {'chat_neprectenych': pocet_neprectenych(request.user)}
