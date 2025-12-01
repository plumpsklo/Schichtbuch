from django.db import models
from django.contrib.auth.models import User


# ---------------------------------------------------
# Maschinen
# ---------------------------------------------------
class Machine(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------
# Haupt-Eintrag im Schichtbuch
# ---------------------------------------------------
class ShiftEntry(models.Model):
    SHIFT_CHOICES = [
        ('F', 'Frühschicht'),
        ('S', 'Spätschicht'),
        ('N', 'Nachtschicht'),
    ]

    CATEGORY_CHOICES = [
        ('STOER', 'Störung'),
        ('WART', 'Wartung'),
        ('UMBAU', 'Umbau'),
        ('KONT', 'Kontrolle / Inspektion'),
    ]

    STATUS_CHOICES = [
        ('OFFEN', 'Offen'),
        ('IN_ARB', 'In Bearbeitung'),
        ('ERLED', 'Erledigt'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField()
    time = models.TimeField(default=None, null=True, blank=True)
    shift = models.CharField(max_length=1, choices=SHIFT_CHOICES)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=2)  # 1=hoch, 2=normal, 3=niedrig
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OFFEN')

    # ⚠️ Alte Ersatzteil-Felder (werden später NICHT gelöscht)
    used_spare_parts = models.BooleanField(default=False)
    spare_part_description = models.CharField(max_length=200, blank=True)
    spare_part_sap_number = models.CharField(max_length=50, blank=True)
    spare_part_quantity_used = models.PositiveIntegerField(null=True, blank=True)
    spare_part_quantity_remaining = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.machine} - {self.title}"


# ---------------------------------------------------
# Strukturierte Ersatzteile (NEU, korrekt)
# ---------------------------------------------------
class SparePart(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="spare_parts",
    )

    sap_number = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True)

    quantity_used = models.PositiveIntegerField(default=0)
    quantity_remaining = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ersatzteil"
        verbose_name_plural = "Ersatzteile"

    def __str__(self):
        return f"{self.sap_number} ({self.entry_id})"


# ---------------------------------------------------
# Bilder
# ---------------------------------------------------
class ShiftEntryImage(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='shift_images/')
    comment = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bild zu: {self.entry}"


# ---------------------------------------------------
# Videos
# ---------------------------------------------------
class ShiftEntryVideo(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    video = models.FileField(upload_to='shift_videos/')
    comment = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video zu: {self.entry}"


# ---------------------------------------------------
# Likes
# ---------------------------------------------------
class Like(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('entry', 'user')

    def __str__(self):
        return f"Like von {self.user} für {self.entry}"


# ---------------------------------------------------
# Ergänzungen / Updates zu einem Eintrag
# ---------------------------------------------------
class ShiftEntryUpdate(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="updates"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    comment = models.TextField()
    action_time = models.DateTimeField()

    status_before = models.CharField(
        max_length=10,
        choices=ShiftEntry.STATUS_CHOICES,
        blank=True
    )
    status_after = models.CharField(
        max_length=10,
        choices=ShiftEntry.STATUS_CHOICES,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["action_time", "id"]

    def __str__(self):
        return f"Update zu {self.entry} von {self.user} am {self.action_time}"