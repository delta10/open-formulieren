from django.contrib import admin

from .fields import PaymentBackendChoiceField
from .models import SubmissionPayment


class PaymentBackendChoiceFieldMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, PaymentBackendChoiceField):
            assert not db_field.choices
            _old = db_field.choices
            db_field.choices = db_field._get_plugin_choices()
            field = super().formfield_for_dbfield(db_field, request, **kwargs)
            db_field.choices = _old
            return field

        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(SubmissionPayment)
class SubmissionPaymentAdmin(admin.ModelAdmin):
    fields = (
        "uuid",
        "created",
        "submission",
        "plugin_id",
        "plugin_options",
        "public_order_id",
        "amount",
        "status",
    )
    raw_id_fields = ("submission",)
    readonly_fields = (
        "uuid",
        "created",
    )
    list_display = (
        "uuid",
        "created",
        "submission",
        "plugin_id",
        "public_order_id",
        "amount",
        "status",
    )
    list_filter = ("status",)
    search_fields = (
        "public_order_id",
        "submission__uuid",
        "uuid",
    )
