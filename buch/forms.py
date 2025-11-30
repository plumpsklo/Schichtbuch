from django import forms
from .models import ShiftEntry


class ShiftEntryForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        label="Bild (optional)",
        help_text="Optional ein Foto zur Störung oder Maßnahme hochladen."
    )

    # falls du auch Video nutzen willst, könntest du noch:
    # video = forms.FileField(
    #     required=False,
    #     label="Video (optional)",
    #     help_text="Optional ein kurzes Video (z.B. Störung) hochladen."
    # )

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
            # 🔧 NEU: Ersatzteil-Felder ins Formular aufnehmen
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
            # Wenn Haken nicht gesetzt → Felder sauber leeren
            cleaned_data['spare_part_description'] = ''
            cleaned_data['spare_part_sap_number'] = ''
            cleaned_data['spare_part_quantity_used'] = None
            cleaned_data['spare_part_quantity_remaining'] = None

        return cleaned_data