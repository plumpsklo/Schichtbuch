import datetime

from django import forms
from django.utils import timezone

from .models import ShiftEntry, ShiftEntryUpdate


class ShiftEntryForm(forms.ModelForm):
    """
    Formular für NEUEN Eintrag.
    Zusätzlich:
    - Uhrzeit-Feld (time)
    - optionale Felder für Bild/Video
    - Validierung: Datum/Uhrzeit nicht in der Zukunft
    """

    # extra Feld nur im Formular (wird zu action_datetime kombiniert)
    time = forms.TimeField(
        required=True,
        label="Uhrzeit",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    image = forms.ImageField(required=False, label="Bild (optional)")
    video = forms.FileField(required=False, label="Video (optional)")

    class Meta:
        model = ShiftEntry
        fields = [
            "date",
            "time",  # <== nur Formular, nicht im Modell
            "shift",
            "machine",
            "category",
            "title",
            "description",
            "duration_minutes",
            "priority",
            "status",

            # Ersatzteile (Basis-Eintrag)
            "used_spare_parts",
            "spare_part_description",
            "spare_part_sap_number",
            "spare_part_quantity_used",
            "spare_part_quantity_remaining",
        ]
        labels = {
            "date": "Datum",
            "shift": "Schicht",
            "machine": "Maschine",
            "category": "Kategorie",
            "title": "Titel",
            "description": "Beschreibung",
            "duration_minutes": "Dauer (Minuten)",
            "priority": "Priorität",
            "status": "Status",

            "used_spare_parts": "Ersatzteile verwendet",
            "spare_part_description": "Beschreibung des Ersatzteils",
            "spare_part_sap_number": "SAP-Nummer",
            "spare_part_quantity_used": "Entnommene Anzahl",
            "spare_part_quantity_remaining": "Bestand nach Entnahme",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "duration_minutes": forms.NumberInput(attrs={"min": 0}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        time_value = cleaned_data.get("time")

        if date and time_value:
            # Datum + Uhrzeit zu einem AWARE datetime kombinieren
            dt_naive = datetime.datetime.combine(date, time_value)
            dt_aware = timezone.make_aware(
                dt_naive,
                timezone.get_current_timezone(),
            )

            if dt_aware > timezone.now():
                raise forms.ValidationError(
                    "Datum und Uhrzeit dürfen nicht in der Zukunft liegen."
                )

            # Merken, damit die View es ins Modell schreiben kann
            cleaned_data["action_datetime"] = dt_aware

        return cleaned_data


class ShiftEntryUpdateForm(forms.ModelForm):
    """
    Formular für ERGÄNZUNG eines bestehenden Eintrags.
    - eigener Kommentar
    - frei wählbare Uhrzeit (action_time)
    - optional neuer Status
    - optionale Ersatzteil-Felder (wie beim Erstellen)
    - optional Bild / Video
    """

    # Neuer Status (optional)
    status = forms.ChoiceField(
        choices=ShiftEntry.STATUS_CHOICES,
        required=False,
        label="Neuer Status",
    )

    # Ersatzteil-Felder (wie beim Erstellen)
    used_spare_parts = forms.BooleanField(
        required=False,
        label="Ersatzteile verwendet",
    )
    spare_part_description = forms.CharField(
        max_length=200,
        required=False,
        label="Beschreibung des Ersatzteils",
    )
    spare_part_sap_number = forms.CharField(
        max_length=50,
        required=False,
        label="SAP-Nummer",
    )
    spare_part_quantity_used = forms.IntegerField(
        required=False,
        min_value=0,
        label="Entnommene Anzahl",
    )
    spare_part_quantity_remaining = forms.IntegerField(
        required=False,
        min_value=0,
        label="Bestand nach Entnahme",
    )

    # Medien
    image = forms.ImageField(required=False, label="Zusätzliches Bild")
    video = forms.FileField(required=False, label="Zusätzliches Video")

    class Meta:
        model = ShiftEntryUpdate
        fields = [
            "comment",
            "action_time",
        ]
        labels = {
            "comment": "Ergänzung / Kommentar",
            "action_time": "Zeitpunkt der Maßnahme",
        }
        widgets = {
            "action_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }

    def clean_action_time(self):
        action_time = self.cleaned_data.get("action_time")
        if action_time:
            # sicherstellen, dass aware und nicht in der Zukunft
            if timezone.is_naive(action_time):
                action_time = timezone.make_aware(
                    action_time,
                    timezone.get_current_timezone(),
                )
            if action_time > timezone.now():
                raise forms.ValidationError(
                    "Der Zeitpunkt der Maßnahme darf nicht in der Zukunft liegen."
                )
        return action_time