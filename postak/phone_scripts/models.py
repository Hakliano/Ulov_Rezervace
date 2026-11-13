from django.conf import settings
from django.db import models

from .constants import Product, SalesStyle, SpecialAction, StepType, VersionStatus, WebStatus


class PhoneScript(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    product = models.CharField(max_length=32, choices=Product.choices)
    is_active = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    published_snapshot = models.JSONField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    current_version = models.ForeignKey(
        'PhoneScriptVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['product', 'name']
        verbose_name = 'Scénář'
        verbose_name_plural = 'Scénáře'

    def __str__(self):
        if self.current_version_id:
            return f'{self.name} (v{self.current_version.version_number})'
        return self.name

    @property
    def current_published_number(self) -> int | None:
        if self.current_version_id:
            return self.current_version.version_number
        return self.version or None


class PhoneScriptVersion(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
    )
    is_current = models.BooleanField(
        default=False,
        help_text='Právě publikovaná verze pro telefonisty.',
    )
    snapshot = models.JSONField()
    note = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='phone_script_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('script', 'version_number')]
        verbose_name = 'Verze scénáře'
        verbose_name_plural = 'Verze scénářů'

    def __str__(self):
        return f'{self.script.slug} v{self.version_number} ({self.status})'

    @property
    def status_label(self) -> str:
        return self.get_status_display()

class ScriptTopicArea(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='areas')
    slug = models.SlugField(max_length=60)
    name = models.CharField(max_length=200)
    sort_order = models.PositiveSmallIntegerField(default=0)
    entry_step = models.ForeignKey(
        'ScriptStep',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='area_entries',
    )

    class Meta:
        ordering = ['sort_order', 'pk']
        unique_together = [('script', 'slug')]
        verbose_name = 'Tematická oblast'
        verbose_name_plural = 'Tematické oblasti'

    def __str__(self):
        return self.name


class ScriptStep(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='steps')
    step_id = models.CharField(max_length=80)
    topic_area = models.ForeignKey(
        ScriptTopicArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='steps',
    )
    step_type = models.CharField(
        max_length=32,
        choices=StepType.choices,
        default=StepType.QUESTION,
    )
    say_text = models.TextField()
    goal_note = models.TextField(blank=True)

    class Meta:
        ordering = ['step_id']
        unique_together = [('script', 'step_id')]
        verbose_name = 'Krok scénáře'
        verbose_name_plural = 'Kroky scénáře'

    def __str__(self):
        return self.step_id


class AnswerOption(models.Model):
    step = models.ForeignKey(ScriptStep, on_delete=models.CASCADE, related_name='answers')
    label = models.CharField(max_length=300)
    sort_order = models.PositiveSmallIntegerField(default=0)
    target_step = models.ForeignKey(
        ScriptStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_answers',
    )
    special_action = models.CharField(
        max_length=32,
        choices=SpecialAction.choices,
        blank=True,
        default=SpecialAction.NONE,
    )
    jump_area = models.ForeignKey(
        ScriptTopicArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jump_answers',
    )

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Odpověď zákazníka'
        verbose_name_plural = 'Odpovědi zákazníka'

    def __str__(self):
        return self.label[:60]


class InitialBranch(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='initial_branches')
    web_status = models.CharField(max_length=32, choices=WebStatus.choices)
    sales_style = models.CharField(max_length=32, choices=SalesStyle.choices)
    entry_step = models.ForeignKey(
        ScriptStep,
        on_delete=models.PROTECT,
        related_name='initial_branches',
    )

    class Meta:
        unique_together = [('script', 'web_status', 'sales_style')]
        verbose_name = 'Vstupní větev'
        verbose_name_plural = 'Vstupní větve'

    def __str__(self):
        return f'{self.web_status} / {self.sales_style}'


class OpeningGreeting(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='openings')
    name = models.CharField(max_length=120)
    text = models.TextField(help_text='Použijte {agent_name} pro jméno telefonisty.')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Úvodní oslovení'
        verbose_name_plural = 'Úvodní oslovení'

    def __str__(self):
        return self.name


class Objection(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='objections')
    slug = models.SlugField(max_length=60)
    title = models.CharField(max_length=200)
    sort_order = models.PositiveSmallIntegerField(default=0)
    root_step = models.ForeignKey(
        ScriptStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='objection_roots',
    )

    class Meta:
        ordering = ['sort_order', 'pk']
        unique_together = [('script', 'slug')]
        verbose_name = 'Námitka'
        verbose_name_plural = 'Námitky'

    def __str__(self):
        return self.title


class ObjectionResponse(models.Model):
    objection = models.ForeignKey(Objection, on_delete=models.CASCADE, related_name='responses')
    say_text = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    target_step = models.ForeignKey(
        ScriptStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='objection_responses',
    )
    hard_reject = models.BooleanField(
        default=False,
        help_text='Výslovný zákaz dalšího kontaktu — ukončení hovoru.',
    )
    return_only = models.BooleanField(
        default=True,
        help_text='Po přečtení textu jen zavřít námitku a vrátit se na původní krok.',
    )

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Reakce na námitku'
        verbose_name_plural = 'Reakce na námitky'

    def __str__(self):
        return self.say_text[:60]


class ProductPriceRow(models.Model):
    script = models.ForeignKey(PhoneScript, on_delete=models.CASCADE, related_name='pricing')
    product_name = models.CharField(max_length=120)
    monthly_czk = models.PositiveIntegerField()
    activation_czk = models.PositiveIntegerField()
    description_short = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Cenová řádka'
        verbose_name_plural = 'Cenové řádky'

    def __str__(self):
        return self.product_name
