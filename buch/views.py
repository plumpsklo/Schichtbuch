from datetime import timedelta
import os

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponse

from .models import ShiftEntry, ShiftEntryImage
from .forms import ShiftEntryForm


@login_required
def home(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Montag

    # Statistik
    entries_today = ShiftEntry.objects.filter(date=today).count()
    entries_week = ShiftEntry.objects.filter(date__gte=week_start, date__lte=today).count()
    open_entries = ShiftEntry.objects.filter(status='OFFEN').count()
    done_entries = ShiftEntry.objects.filter(status='ERLED').count()

    # Top 5 Maschinen nach Störungsanzahl (nur Kategorie "Störung")
    top_machines = (
        ShiftEntry.objects.filter(category='STOER')
        .values('machine__name')
        .order_by('machine__name')
    )

    # Letzte 20 Einträge
    entries = (
        ShiftEntry.objects.select_related('machine', 'user')
        .order_by('-date', '-created_at')[:20]
    )

    context = {
        'entries_today': entries_today,
        'entries_week': entries_week,
        'open_entries': open_entries,
        'done_entries': done_entries,
        'entries': entries,
    }
    return render(request, 'buch/home.html', context)


@login_required
def new_entry(request):
    if request.method == 'POST':
        form = ShiftEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()

            image_file = form.cleaned_data.get('image')
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            return redirect('home')
    else:
        # Standard: Datum = heute, Schicht leer → der User wählt
        initial = {'date': timezone.localdate()}
        form = ShiftEntryForm(initial=initial)

    return render(request, 'buch/entry_form.html', {'form': form})


@login_required
def entry_detail(request, entry_id):
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    return render(request, 'buch/entry_detail.html', {
        'entry': entry
    })


@login_required
def debug_media(request):
    """
    Kleine Diagnose-Seite:
    - zeigt MEDIA_ROOT
    - listet alle ShiftEntryImage-Einträge
    - prüft, ob die Dateien wirklich auf der Platte existieren
    - zeigt, was im Verzeichnis shift_images liegt
    """
    lines = [f"MEDIA_ROOT: {settings.MEDIA_ROOT}"]

    images = ShiftEntryImage.objects.all()
    if not images:
        lines.append("Keine ShiftEntryImage-Objekte in der DB.")
    else:
        for img in images:
            path = img.image.name  # z.B. 'shift_images/IMG_1285_nn1VSlI.jpeg'
            exists = default_storage.exists(path)
            lines.append(f"{img.id}: {path} -> exists={exists}")

    # Prüfen, ob der Ordner shift_images existiert und was drin liegt
    shift_dir = os.path.join(settings.MEDIA_ROOT, 'shift_images')
    if os.path.isdir(shift_dir):
        files = os.listdir(shift_dir)
        lines.append(f"shift_images-Verzeichnis gefunden unter: {shift_dir}")
        lines.append(f"Dateien darin: {files}")
    else:
        lines.append(f"shift_images-Verzeichnis NICHT gefunden unter: {shift_dir}")

    return HttpResponse("<br>".join(lines))