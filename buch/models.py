from django.db import models
from django.contrib.auth.models import User


class Machine(models.Model):
    name = models.CharField(max_length=100)  # z.B. "RBG-01"
    location = models.CharField(max_length=100, blank=True)  # z.B. "Halle 2"
    manufacturer = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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
    date = models.DateField()  # Datum der Tätigkeit
    shift = models.CharField(max_length=1, choices=SHIFT_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=2)  # 1 = hoch, 2 = normal, 3 = niedrig
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OFFEN')

    def __str__(self):
        return f"{self.date} - {self.machine} - {self.title}"


class ShiftEntryImage(models.Model):
    entry = models.ForeignKey(ShiftEntry, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='shift_images/')
    comment = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bild zu: {self.entry}"


# ⬇️ NEU: Videos pro Eintrag
class ShiftEntryVideo(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    # landet unter MEDIA_ROOT/shift_videos/
    video = models.FileField(upload_to='shift_videos/')
    comment = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video zu: {self.entry}"