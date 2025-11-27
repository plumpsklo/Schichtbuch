from django import forms
from .models import ShiftEntry


class ShiftEntryForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        label="Bild (optional)",
        help_text="Optional ein Foto zur Störung oder Maßnahme hochladen."
    )

    video = forms.FileField(
        required=False,
        label="Video (optional)",
        help_text="Optional ein Video zur Störung oder Maßnahme hochladen.",
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
            'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }