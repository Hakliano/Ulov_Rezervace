from django.conf import settings
from django.db import models


class ChatZprava(models.Model):
    odesilatel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_odeslane',
    )
    prijemce = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_prijate',
    )
    text = models.TextField(max_length=5000)
    precteno = models.BooleanField(default=False)
    vytvoreno = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['vytvoreno']
        indexes = [
            models.Index(fields=['prijemce', 'precteno']),
            models.Index(fields=['odesilatel', 'prijemce']),
        ]
