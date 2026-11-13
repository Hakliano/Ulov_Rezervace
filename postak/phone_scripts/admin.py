from django.contrib import admin, messages

from phone_scripts.models import (
    AnswerOption,
    InitialBranch,
    Objection,
    ObjectionResponse,
    OpeningGreeting,
    PhoneScript,
    PhoneScriptVersion,
    ProductPriceRow,
    ScriptStep,
    ScriptTopicArea,
)
from phone_scripts.services.snapshot import publish_script
from phone_scripts.services.validate import validate_script


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 0
    fk_name = 'step'
    autocomplete_fields = ['target_step', 'jump_area']


class ScriptStepInline(admin.TabularInline):
    model = ScriptStep
    extra = 0
    show_change_link = True
    fields = ('step_id', 'step_type', 'say_text', 'topic_area')
    autocomplete_fields = ['topic_area']


@admin.register(PhoneScriptVersion)
class PhoneScriptVersionAdmin(admin.ModelAdmin):
    list_display = ('script', 'version_number', 'status', 'is_current', 'created_at', 'created_by')
    list_filter = ('status', 'script')
    search_fields = ('script__slug', 'note')
    readonly_fields = ('created_at', 'published_at', 'snapshot')


@admin.register(PhoneScript)
class PhoneScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'product', 'version', 'is_active', 'published_at')
    list_filter = ('product', 'is_active')
    search_fields = ('name', 'slug')
    readonly_fields = ('version', 'published_at', 'published_snapshot', 'created_at', 'updated_at')
    actions = ['validate_selected', 'publish_selected']

    @admin.action(description='Zkontrolovat scénáře')
    def validate_selected(self, request, queryset):
        for script in queryset:
            result = validate_script(script)
            if result.ok:
                msg = f'{script.slug}: OK'
                if result.warnings:
                    msg += f' (varování: {len(result.warnings)})'
                self.message_user(request, msg, messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    f'{script.slug}: ' + '; '.join(result.errors),
                    messages.ERROR,
                )

    @admin.action(description='Publikovat (nová verze + snapshot)')
    def publish_selected(self, request, queryset):
        for script in queryset:
            ok, notes = publish_script(script)
            if ok:
                msg = f'{script.slug} publikováno jako v{script.version}.'
                if notes:
                    msg += ' Varování: ' + '; '.join(notes)
                self.message_user(request, msg, messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    f'{script.slug}: publikace zamítnuta — ' + '; '.join(notes),
                    messages.ERROR,
                )


@admin.register(ScriptTopicArea)
class ScriptTopicAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'script', 'sort_order', 'entry_step')
    list_filter = ('script',)
    search_fields = ('name', 'slug')
    autocomplete_fields = ['script', 'entry_step']


@admin.register(ScriptStep)
class ScriptStepAdmin(admin.ModelAdmin):
    list_display = ('step_id', 'script', 'step_type', 'topic_area')
    list_filter = ('script', 'step_type')
    search_fields = ('step_id', 'say_text')
    autocomplete_fields = ['script', 'topic_area']
    inlines = [AnswerOptionInline]


@admin.register(InitialBranch)
class InitialBranchAdmin(admin.ModelAdmin):
    list_display = ('script', 'web_status', 'sales_style', 'entry_step')
    list_filter = ('script', 'web_status', 'sales_style')
    autocomplete_fields = ['script', 'entry_step']


class ObjectionResponseInline(admin.TabularInline):
    model = ObjectionResponse
    extra = 0
    autocomplete_fields = ['target_step']


@admin.register(Objection)
class ObjectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'script', 'sort_order')
    list_filter = ('script',)
    search_fields = ('title', 'slug')
    autocomplete_fields = ['script', 'root_step']
    inlines = [ObjectionResponseInline]


@admin.register(OpeningGreeting)
class OpeningGreetingAdmin(admin.ModelAdmin):
    list_display = ('name', 'script', 'sort_order')
    list_filter = ('script',)
    autocomplete_fields = ['script']


@admin.register(ProductPriceRow)
class ProductPriceRowAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'script', 'monthly_czk', 'activation_czk')
    list_filter = ('script',)
    autocomplete_fields = ['script']
