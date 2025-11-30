from django import forms
from .models import ShiftEntry, ShiftEntryUpdate


class ShiftEntryForm(forms.ModelForm):
    """
    Formular für NEUE Einträge.
    - Speichert nur die ShiftEntry-Felder direkt im Modell
    - Zusätzlich:
        * image  (optional, geht in ShiftEntryImage)
        * video  (optional, geht in ShiftEntryVideo)
        * used_spares + spare_… (nur Form-Felder – später zum Anlegen eines SparePart nutzbar)
    """

    image = forms.ImageField(
        required=False,
        label="Bild (optional)",
        help_text="Optional ein Foto zur Störung oder Maßnahme hochladen.",
    )

    video = forms.FileField(
        required=False,
        label="Video (optional)",
        help_text="Optional ein kurzes Video hochladen (z. B. 10–20 Sek.).",
    )

    # 🔧 Nur Formularfelder, KEINE Modellfelder
    used_spares = forms.BooleanField(
        required=False,
        label="Ersatzteile verwendet?",
    )

    spare_description = forms.CharField(
        required=False,
        label="Ersatzteil-Beschreibung",
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "z.B.: Zahnriemen Antrieb RBG 1",
            }
        ),
    )

    spare_sap_number = forms.CharField(
        required=False,
        label="SAP-Nummer",
        widget=forms.TextInput(
            attrs={
                "placeholder": "z.B.: 123456789",
            }
        ),
    )

    spare_quantity_used = forms.IntegerField(
        required=False,
        label="Entnommene Anzahl",
        min_value=0,
    )

    spare_quantity_remaining = forms.IntegerField(
        required=False,
        label="Restbestand",
        min_value=0,
    )

    class Meta:
        model = ShiftEntry
        fields = [
            "date",
            "shift",
            "machine",
            "category",
            "title",
            "description",
            "duration_minutes",
            "priority",
            "status",
            # ⚠️ HIER KEINE spare_*-Felder und KEIN used_spares eintragen!
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class ShiftEntryUpdateForm(forms.ModelForm):
    """
    Formular für Ergänzungen zu einem bestehenden Eintrag.
    - Überschreibt NICHT die ursprüngliche Beschreibung.
    - Legt eine neue ShiftEntryUpdate-Zeile als Historie an.
    - Kann zusätzlich ein Bild, Video und Ersatzteil-Info aufnehmen.
    """

    status = forms.ChoiceField(
        choices=[("", "Status unverändert")] + list(ShiftEntry.STATUS_CHOICES),
        required=False,
        label="Neuer Status (optional)",
    )

    image = forms.ImageField(
        required=False,
        label="Zusätzliches Bild",
        help_text="Optional weiteres Bild zur Ergänzung hochladen.",
    )

    video = forms.FileField(
        required=False,
        label="Zusätzliches Video",
        help_text="Optional weiteres Video zur Ergänzung hochladen.",
    )

    spare_info = forms.CharField(
        required=False,
        label="Ersatzteil-Informationen (optional)",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Z.B.: Zahnriemen, SAP 123456, 2 Stück entnommen, 5 verbleibend",
            }
        ),
    )

    class Meta:
        model = ShiftEntryUpdate
        fields = [
            "comment",
            "action_time",
            # status_before / status_after setzt die View
        ]
        widgets = {
            "action_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            )
        }