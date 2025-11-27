from datetime import timedelta
import os
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import ShiftEntry, ShiftEntryImage, ShiftEntryVideo, Like
from .forms import ShiftEntryForm


@login_required
def home(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Montag (Wochenanfang)

    # --- Statistik-Kacheln ---
    entries_today = ShiftEntry.objects.filter(date=today).count()
    entries_week = ShiftEntry.objects.filter(date__gte=week_start, date__lte=today).count()
    open_entries = ShiftEntry.objects.filter(status='OFFEN').count()
    done_entries = ShiftEntry.objects.filter(status='ERLED').count()

    # --- (optional) Top-Maschinen nach Störung, falls später im Template genutzt ---
    top_machines = (
        ShiftEntry.objects.filter(category='STOER')
        .values('machine__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # --- Diagramm 1: Verteilung nach Status (alle Einträge) ---
    status_qs = (
        ShiftEntry.objects
        .values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )

    STATUS_LABELS = dict(ShiftEntry.STATUS_CHOICES)

    status_labels = []
    status_data = []

    for row in status_qs:
        code = row['status']                     # z.B. "OFFEN"
        label = STATUS_LABELS.get(code, code)    # z.B. "Offen"
        status_labels.append(label)
        status_data.append(row['count'])

    # --- Diagramm 2: Einträge pro Tag (letzte 7 Tage) ---
    days_back = 6
    start_date = today - timedelta(days=days_back)

    date_qs = (
        ShiftEntry.objects
        .filter(date__gte=start_date, date__lte=today)
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    counts_by_date = {row['date']: row['count'] for row in date_qs}

    date_labels = []
    date_data = []

    for i in range(days_back + 1):
        d = start_date + timedelta(days=i)
        date_labels.append(d.strftime("%d.%m."))  # z.B. "27.11."
        date_data.append(counts_by_date.get(d, 0))

    # --- Letzte 20 Einträge für die Tabelle ---
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
        'top_machines': top_machines,

        # Daten für Chart.js (werden in home.html als JS-Arrays verwendet)
        'status_labels_json': json.dumps(status_labels),
        'status_data_json': json.dumps(status_data),
        'date_labels_json': json.dumps(date_labels),
        'date_data_json': json.dumps(date_data),
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

            # Bild (optional)
            image_file = form.cleaned_data.get('image')
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            # Video (optional)
            video_file = form.cleaned_data.get('video')
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            return redirect('home')
    else:
        # Standard: Datum = heute
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
    Diagnose-Seite:
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


@login_required
def toggle_like(request, entry_id):
    """
    Like/Unlike für einen Eintrag.
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    like, created = Like.objects.get_or_create(
        user=request.user,
        entry=entry
    )

    if not created:
        # existierte schon -> wieder entfernen = "unlike"
        like.delete()

    return redirect('entry_detail', entry_id=entry.id)