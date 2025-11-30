from django import forms
from .models import ShiftEntry


class ShiftEntryForm(forms.ModelForm):
    # Bild (zusätzliche, nicht im Modell definierte Field)
    image = forms.ImageField(
        required=False,
        label="Bild (optional)",
        help_text="Optional ein Foto zur Störung oder Maßnahme hochladen."
    )

    # 🔙 NEU/WIEDER DA: Video-Feld (auch zusätzlich, eigenes Modell ShiftEntryVideo)
    video = forms.FileField(
        required=False,
        label="Video (optional)",
        help_text="Optional ein kurzes Video (z.B. Störung) hochladen.",
        widget=forms.ClearableFileInput(attrs={'accept': 'video/*'})
    )

    class Meta:
        model = ShiftEntry
        fields = [
            'date',
            'shift',
            'machine',
            'category',
            'title',
            'description',
            'duration_minutes',
            'priority',
            'status',
            # Ersatzteile
            'used_spare_parts',
            'spare_part_description',
            'spare_part_sap_number',
            'spare_part_quantity_used',
            'spare_part_quantity_remaining',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        used = cleaned_data.get('used_spare_parts')
        desc = cleaned_data.get('spare_part_description')
        sap = cleaned_data.get('spare_part_sap_number')
        qty_used = cleaned_data.get('spare_part_quantity_used')
        qty_rem = cleaned_data.get('spare_part_quantity_remaining')

        # Wenn Ersatzteile verwendet wurden → alle Felder Pflicht
        if used:
            if not desc:
                self.add_error('spare_part_description', "Bitte eine Beschreibung des Ersatzteils eingeben.")
            if not sap:
                self.add_error('spare_part_sap_number', "Bitte die SAP-Nummer eingeben.")
            if qty_used is None:
                self.add_error('spare_part_quantity_used', "Bitte die entnommene Anzahl angeben.")
            if qty_rem is None:
                self.add_error('spare_part_quantity_remaining', "Bitte den verbleibenden Bestand angeben.")
        else:
            # Wenn kein Haken → Felder aufgeräumt zurückschreiben
            cleaned_data['spare_part_description'] = ''
            cleaned_data['spare_part_sap_number'] = ''
            cleaned_data['spare_part_quantity_used'] = None
            cleaned_data['spare_part_quantity_remaining'] = None

        return cleaned_data