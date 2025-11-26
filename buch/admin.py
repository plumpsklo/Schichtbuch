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
    list_display = ('date', 'shift', 'machine', 'category', 'status', 'priority', 'user', 'duration_minutes')
    list_filter = ('shift', 'machine', 'category', 'status', 'priority')
    search_fields = ('title', 'description')
    inlines = [ShiftEntryImageInline]


@admin.register(ShiftEntryImage)
class ShiftEntryImageAdmin(admin.ModelAdmin):
    list_display = ('entry', 'uploaded_at')