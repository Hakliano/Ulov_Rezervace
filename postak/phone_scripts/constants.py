from django.db import models


class Product(models.TextChoices):
    MODERNIK = 'modernik', 'Moderník'
    HEREYOUARE = 'hereyouare', 'HereYouAre'


class WebStatus(models.TextChoices):
    HAS_WEB = 'has_web', 'Má vlastní web'
    NO_WEB = 'no_web', 'Nemá vlastní web'
    UNKNOWN = 'unknown', 'Nevíme / nezjištěno'


class SalesStyle(models.TextChoices):
    CALM = 'calm', 'Pomalý, klidný prodej'
    DYNAMIC = 'dynamic', 'Dynamický prodej'


class StepType(models.TextChoices):
    QUESTION = 'question', 'Otázka'
    INFO = 'info', 'Informace'
    CLOSING = 'closing', 'Ukončení hovoru'
    PRICING = 'pricing', 'Cenová nabídka'
    POLITE_EXIT = 'polite_exit', 'Zdvořilé ukončení'


class SpecialAction(models.TextChoices):
    NONE = '', 'Žádná'
    END_CALL = 'end_call', 'Ukončit hovor'
    JUMP_TOPIC = 'jump_topic', 'Přeskočit do oblasti'


class VersionStatus(models.TextChoices):
    DRAFT = 'draft', 'Koncept'
    PUBLISHED = 'published', 'Publikovaná'
    ARCHIVED = 'archived', 'Archivní'


def branch_key(web_status: str, sales_style: str) -> str:
    return f'{web_status}_{sales_style}'


ALL_BRANCH_KEYS = [
    branch_key(web, style)
    for web in WebStatus.values
    for style in SalesStyle.values
]
