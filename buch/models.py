from django.db import models
from django.contrib.auth.models import User


# ---------------------------------------------------
# Maschinen
# ---------------------------------------------------
class Machine(models.Model):
    """
    Stellt eine Maschine im Betrieb dar.
    Beispiel: "RBG-01" in "Halle 2" von Hersteller "Siemens".
    """
    name = models.CharField(
        max_length=100,
        help_text="Kurzbezeichnung der Maschine, z.B. 'RBG-01'.",
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Standort der Maschine, z.B. 'Halle 2'.",
    )
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        help_text="Hersteller, z.B. 'Siemens'.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Gibt an, ob die Maschine aktuell aktiv/in Betrieb ist.",
    )

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------
# Haupt-Eintrag im Schichtbuch
# ---------------------------------------------------
class ShiftEntry(models.Model):
    """
    Ein Schichtbucheintrag beschreibt ein Ereignis an einer Maschine
    (Störung, Wartung, Umbau, Kontrolle etc.) innerhalb einer Schicht.
    """
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

    # Zeitpunkt der Erstellung des Eintrags (nicht gleich Ereigniszeit)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
    )

    # Datum & Uhrzeit des Ereignisses / der Maßnahme
    date = models.DateField(
        verbose_name="Datum",
        help_text="Datum des Ereignisses.",
    )
    time = models.TimeField(
        default=None,
        null=True,
        blank=True,
        verbose_name="Uhrzeit",
        help_text="Uhrzeit des Ereignisses (optional).",
    )

    # Schicht: Früh / Spät / Nacht
    shift = models.CharField(
        max_length=1,
        choices=SHIFT_CHOICES,
        verbose_name="Schicht",
    )

    # Zuordnung zu einem Benutzer (Mitarbeiter) und einer Maschine
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Mitarbeiter",
        help_text="Mitarbeiter, der den Eintrag erstellt hat.",
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        verbose_name="Maschine",
    )
    additional_workers = models.ManyToManyField(
        User,
        blank=True,
        related_name="shift_entries_as_worker",
        verbose_name="Weitere Mitarbeiter",
        help_text="Weitere Kollegen, die an diesem Vorgang beteiligt waren.",
    )

    # Klassifizierung und Beschreibung
    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        verbose_name="Kategorie",
    )
    title = models.CharField(
        max_length=200,
        verbose_name="Titel",
        help_text="Kurzbeschreibung des Vorgangs.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Ausführliche Beschreibung des Vorgangs.",
    )

    # Dauer, Priorität, Status
    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Dauer (Minuten)",
        help_text="Geschätzte oder tatsächliche Dauer des Vorgangs.",
    )
    priority = models.PositiveIntegerField(
        default=2,      # 1 = hoch, 2 = normal, 3 = niedrig
        verbose_name="Priorität",
        help_text="1 = hoch, 2 = normal, 3 = niedrig.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="OFFEN",
        verbose_name="Status",
    )

    # ---------------------------------------------------
    # Alte, einfache Ersatzteil-Daten (für Bestandsdaten / Anzeige)
    # ---------------------------------------------------
    used_spare_parts = models.BooleanField(
        default=False,
        verbose_name="(alt) Ersatzteile verwendet",
        help_text="Wurde bei diesem Vorgang mindestens ein Ersatzteil verwendet?",
    )
    spare_part_description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="(alt) Ersatzteil-Beschreibung",
        help_text="Freitext-Beschreibung des Ersatzteils.",
    )
    spare_part_sap_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="(alt) SAP-Nummer",
        help_text="SAP-Nummer des Ersatzteils.",
    )
    spare_part_quantity_used = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="(alt) Entnommene Anzahl",
        help_text="Wie viele Stück wurden entnommen?",
    )
    spare_part_quantity_remaining = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="(alt) Bestand nach Entnahme",
        help_text="Restbestand nach der Entnahme.",
    )

    # ---------------------------------------------------
    # Neuer Status: SAP-Bearbeitung für Ersatzteile
    # ---------------------------------------------------
    spare_parts_processed = models.BooleanField(
        default=False,
        verbose_name="Ersatzteile in SAP verbucht",
        help_text=(
            "Wird von Meister/Admin gesetzt, wenn die Ersatzteil-Entnahme "
            "in SAP erfasst/verbucht wurde."
        ),
    )
    spare_parts_processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sap_processed_entries",
        verbose_name="SAP-Buchung bestätigt von",
        help_text="Benutzer (typischerweise Meister/Admin), der die SAP-Buchung bestätigt hat.",
    )
    spare_parts_processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="SAP-Buchung bestätigt am",
        help_text="Zeitpunkt der Bestätigung der SAP-Buchung.",
    )

    def __str__(self) -> str:
        return f"{self.date} - {self.machine} - {self.title}"

    # Hilfs-Property: Wurden irgendwo (alt oder strukturiert) Ersatzteile erfasst?
    @property
    def has_any_spare_parts(self) -> bool:
        """
        True, wenn entweder die alten Ersatzteil-Felder gesetzt sind
        oder strukturierte Ersatzteile (SparePart) hinterlegt wurden.
        """
        if self.used_spare_parts:
            return True
        return self.spare_parts.exists()

    @property
    def has_unprocessed_spares(self) -> bool:
        """
        True, wenn Ersatzteile verwendet wurden, aber noch nicht als
        in SAP verbucht markiert sind. Praktisch für Benachrichtigungslisten.
        """
        return self.has_any_spare_parts and not self.spare_parts_processed


# ---------------------------------------------------
# Strukturierte Ersatzteile (NEU, korrekt)
# ---------------------------------------------------
class SparePart(models.Model):
    """
    Strukturierte Ablage von Ersatzteil-Informationen zu einem Eintrag.
    Mehrere Ersatzteile können einem ShiftEntry zugeordnet sein.
    """
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="spare_parts",
        verbose_name="Eintrag",
    )

    sap_number = models.CharField(
        max_length=50,
        verbose_name="SAP-Nummer",
        help_text="SAP-Nummer des Ersatzteils.",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Beschreibung",
        help_text="Freitext-Beschreibung des Ersatzteils.",
    )

    quantity_used = models.PositiveIntegerField(
        default=0,
        verbose_name="Entnommene Anzahl",
        help_text="Wie viele Stück wurden entnommen?",
    )
    quantity_remaining = models.PositiveIntegerField(
        default=0,
        verbose_name="Bestand nach Entnahme",
        help_text="Restbestand nach Entnahme.",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Erfasst von",
        help_text="Benutzer, der diese Ersatzteil-Info erfasst hat.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erfasst am",
    )

    class Meta:
        verbose_name = "Ersatzteil"
        verbose_name_plural = "Ersatzteile"

    def __str__(self) -> str:
        return f"{self.sap_number} (Eintrag-ID: {self.entry_id})"


# ---------------------------------------------------
# Bilder
# ---------------------------------------------------
class ShiftEntryImage(models.Model):
    """
    Bilddateien, die einem Schichtbucheintrag zugeordnet sind.
    Beispiel: Foto von Schaden, Aufbau, Umbau etc.
    """
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
        help_text="Kurzer Kommentar zum Bild.",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hochgeladen am",
    )

    def __str__(self) -> str:
        return f"Bild zu: {self.entry}"


# ---------------------------------------------------
# Videos
# ---------------------------------------------------
class ShiftEntryVideo(models.Model):
    """
    Videodateien zu einem Schichtbucheintrag.
    Beispiel: Video vom Fehlerbild oder Bewegungsablauf.
    """
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
        help_text="Kurzer Kommentar zum Video.",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hochgeladen am",
    )

    def __str__(self) -> str:
        return f"Video zu: {self.entry}"


# ---------------------------------------------------
# Likes
# ---------------------------------------------------
class Like(models.Model):
    """
    Einfache 'Like'-Funktion für Einträge, um Zustimmung / Relevanz zu markieren.
    Ein Benutzer kann einen Eintrag nur einmal liken.
    """
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
        verbose_name = "Like"
        verbose_name_plural = "Likes"

    def __str__(self) -> str:
        return f"Like von {self.user} für {self.entry}"


# ---------------------------------------------------
# Ergänzungen / Updates zu einem Eintrag
# ---------------------------------------------------
class ShiftEntryUpdate(models.Model):
    """
    Ergänzungen / Maßnahmen zu einem bestehenden Eintrag.
    Dient dazu, Verlauf und Statusänderungen nachvollziehbar zu machen.
    """
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
        help_text="Beschreibung der durchgeführten Maßnahme oder Ergänzung.",
    )
    action_time = models.DateTimeField(
        verbose_name="Zeitpunkt der Maßnahme",
        help_text="Wann die Maßnahme durchgeführt wurde.",
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

    def __str__(self) -> str:
        return f"Update zu {self.entry} von {self.user} am {self.action_time}"
    
# Makieren von Usern im Beitrag

class MentionNotification(models.Model):
    """
    Benachrichtigung, wenn jemand in einem Eintrag oder Update mit @username
    erwähnt wird.
    """
    SOURCE_CHOICES = [
        ("ENTRY", "Eintrag"),
        ("UPDATE", "Ergänzung"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mention_notifications",
        verbose_name="Benutzer",
    )
    entry = models.ForeignKey(
        ShiftEntry,
        on_delete=models.CASCADE,
        related_name="mention_notifications",
        verbose_name="Eintrag",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentions_created",
        verbose_name="Erstellt von",
    )
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="ENTRY",
        verbose_name="Quelle",
    )
    text_snippet = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Textauszug",
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="Gelesen",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"@Mention für {self.user} in {self.entry} ({self.source})"