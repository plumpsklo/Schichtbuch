from django.db import models
from django.contrib.auth.models import User


# ---------------------------------------------------
# Maschinen
# ---------------------------------------------------
class Machine(models.Model):
    name = models.CharField(max_length=100)                       # z.B. "RBG-01"
    location = models.CharField(max_length=100, blank=True)       # z.B. "Halle 2"
    manufacturer = models.CharField(max_length=100, blank=True)   # z.B. "Siemens"
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------
# Haupt-Eintrag im Schichtbuch
# ---------------------------------------------------
class ShiftEntry(models.Model):
    SHIFT_CHOICES = [
        ("F", "Frühschicht"),
        ("S", "Spätschicht"),
        ("N", "Nachtschicht"),
    ]

    CATEGORY_CHOICES = [
        ("STOER", "Störung"),
        ("WART", "Wartung"),
        ("UMBAU", "Umbau"),
        ("KONT", "Kontrolle / Inspektion"),
    ]

    STATUS_CHOICES = [
        ("OFFEN", "Offen"),
        ("IN_ARB", "In Bearbeitung"),
        ("ERLED", "Erledigt"),
    ]

    created_at = models.DateTimeField(auto_now_add=True)

    # Datum & Uhrzeit des Eintrags
    date = models.DateField()
    time = models.TimeField(
        default=None,
        null=True,
        blank=True,
        verbose_name="Uhrzeit",
    )

    shift = models.CharField(
        max_length=1,
        choices=SHIFT_CHOICES,
        verbose_name="Schicht",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Mitarbeiter",
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        verbose_name="Maschine",
    )

    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        verbose_name="Kategorie",
    )
    title = models.CharField(
        max_length=200,
        verbose_name="Titel",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Dauer (Minuten)",
    )
    priority = models.PositiveIntegerField(
        default=2,      # 1 = hoch, 2 = normal, 3 = niedrig
        verbose_name="Priorität",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="OFFEN",
        verbose_name="Status",
    )

    # ⚠️ Alte Ersatzteil-Felder (für bestehende Daten / Anzeige)
    used_spare_parts = models.BooleanField(
        default=False,
        verbose_name="(alt) Ersatzteile verwendet",
    )
    spare_part_description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="(alt) Ersatzteil-Beschreibung",
    )
    spare_part_sap_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="(alt) SAP-Nummer",
    )
    spare_part_quantity_used = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="(alt) Entnommene Anzahl",
    )
    spare_part_quantity_remaining = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="(alt) Bestand nach Entnahme",
    )

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
        verbose_name="Eintrag",
    )

    sap_number = models.CharField(
        max_length=50,
        verbose_name="SAP-Nummer",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Beschreibung",
    )

    quantity_used = models.PositiveIntegerField(
        default=0,
        verbose_name="Entnommene Anzahl",
    )
    quantity_remaining = models.PositiveIntegerField(
        default=0,
        verbose_name="Bestand nach Entnahme",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Erfasst von",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erfasst am",
    )

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
        related_name="images",
        verbose_name="Eintrag",
    )
    image = models.ImageField(
        upload_to="shift_images/",
        verbose_name="Bild",
    )
    comment = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Kommentar",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hochgeladen am",
    )

    def __str__(self):
        return f"Bild zu: {self.entry}"


# ---------------------------------------------------
# Videos
# ---------------------------------------------------
class ShiftEntryVideo(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name="Eintrag",
    )
    video = models.FileField(
        upload_to="shift_videos/",
        verbose_name="Video",
    )
    comment = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Kommentar",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hochgeladen am",
    )

    def __str__(self):
        return f"Video zu: {self.entry}"


# ---------------------------------------------------
# Likes
# ---------------------------------------------------
class Like(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="Eintrag",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Benutzer",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
    )

    class Meta:
        unique_together = ("entry", "user")

    def __str__(self):
        return f"Like von {self.user} für {self.entry}"


# ---------------------------------------------------
# Ergänzungen / Updates zu einem Eintrag
# ---------------------------------------------------
class ShiftEntryUpdate(models.Model):
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name="Eintrag",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Benutzer",
    )

    comment = models.TextField(
        verbose_name="Ergänzung / Kommentar",
    )
    action_time = models.DateTimeField(
        verbose_name="Zeitpunkt der Maßnahme",
    )

    status_before = models.CharField(
        max_length=10,
        choices=ShiftEntry.STATUS_CHOICES,
        blank=True,
        verbose_name="Status vorher",
    )
    status_after = models.CharField(
        max_length=10,
        choices=ShiftEntry.STATUS_CHOICES,
        blank=True,
        verbose_name="Status nachher",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erfasst am",
    )

    class Meta:
        ordering = ["action_time", "id"]
        verbose_name = "Ergänzung"
        verbose_name_plural = "Ergänzungen"

    def __str__(self):
        return f"Update zu {self.entry} von {self.user} am {self.action_time}"