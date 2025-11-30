from django.contrib import admin
from .models import Machine, ShiftEntry, ShiftEntryImage


class ShiftEntryImageInline(admin.TabularInline):
    model = ShiftEntryImage
    extra = 1


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'manufacturer', 'is_active')
    list_filter = ('is_active',)


@admin.register(ShiftEntry)
class ShiftEntryAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'shift',
        'machine',
        'category',
        'status',
        'priority',
        'user',
        'duration_minutes',
        'used_spare_parts',            # 🔧 neu
        'spare_part_sap_number',       # 🔧 neu (SAP direkt sichtbar)
        'spare_part_quantity_used',    # 🔧 neu
    )
    list_filter = (
        'shift',
        'machine',
        'category',
        'status',
        'priority',
        'used_spare_parts',            # 🔧 neu → Filter "Ersatzteile verwendet: ja/nein"
    )
    search_fields = (
        'title',
        'description',
        'spare_part_description',      # 🔧 neu
        'spare_part_sap_number',       # 🔧 neu
    )
    inlines = [ShiftEntryImageInline]


@admin.register(ShiftEntryImage)
class ShiftEntryImageAdmin(admin.ModelAdmin):
    list_display = ('entry', 'uploaded_at')