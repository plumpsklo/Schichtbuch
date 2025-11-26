from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

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