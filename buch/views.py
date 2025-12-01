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

from .models import (
    ShiftEntry,
    ShiftEntryImage,
    ShiftEntryVideo,
    Like,
    ShiftEntryUpdate,
)
from .forms import ShiftEntryForm, ShiftEntryUpdateForm


# -------------------------------------------------------------------
# Startseite / Übersicht
# -------------------------------------------------------------------
@login_required
def home(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Montag (Wochenanfang)

    # --- Statistik-Kacheln ---
    entries_today = ShiftEntry.objects.filter(date=today).count()
    entries_week = ShiftEntry.objects.filter(
        date__gte=week_start,
        date__lte=today,
    ).count()
    open_entries = ShiftEntry.objects.filter(status="OFFEN").count()
    done_entries = ShiftEntry.objects.filter(status="ERLED").count()

    # --- Top-Maschinen nach Störung (optional) ---
    top_machines = (
        ShiftEntry.objects.filter(category="STOER")
        .values("machine__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    # --- Diagramm 1: Verteilung nach Status (alle Einträge) ---
    status_qs = (
        ShiftEntry.objects
        .values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    STATUS_LABELS = dict(ShiftEntry.STATUS_CHOICES)

    status_labels = []
    status_data = []

    for row in status_qs:
        code = row["status"]                  # z.B. "OFFEN"
        label = STATUS_LABELS.get(code, code) # z.B. "Offen"
        status_labels.append(label)
        status_data.append(row["count"])

    # --- Diagramm 2: Einträge pro Tag (letzte 7 Tage) ---
    days_back = 6
    start_date = today - timedelta(days=days_back)

    date_qs = (
        ShiftEntry.objects
        .filter(date__gte=start_date, date__lte=today)
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    counts_by_date = {row["date"]: row["count"] for row in date_qs}

    date_labels = []
    date_data = []

    for i in range(days_back + 1):
        d = start_date + timedelta(days=i)
        date_labels.append(d.strftime("%d.%m."))  # z.B. "27.11."
        date_data.append(counts_by_date.get(d, 0))

    # --- Letzte 20 Einträge für die Tabelle ---
    entries = (
        ShiftEntry.objects.select_related("machine", "user")
        .order_by("-date", "-created_at")[:20]
    )

    context = {
        "entries_today": entries_today,
        "entries_week": entries_week,
        "open_entries": open_entries,
        "done_entries": done_entries,
        "entries": entries,
        "top_machines": top_machines,
        # Daten für Chart.js
        "status_labels_json": json.dumps(status_labels),
        "status_data_json": json.dumps(status_data),
        "date_labels_json": json.dumps(date_labels),
        "date_data_json": json.dumps(date_data),
    }
    return render(request, "buch/home.html", context)


# -------------------------------------------------------------------
# Neuer Eintrag
# -------------------------------------------------------------------
@login_required
def new_entry(request):
    """
    Neuen Schichtbucheintrag anlegen.
    - Basisdaten über ShiftEntryForm
    - optional ein Bild
    - optional ein Video
    - Ersatzteil-Felder direkt im Modell (ein Satz Felder)
    Die Prüfung "kein Datum/Uhrzeit in der Zukunft" macht die Form-Klasse.
    """
    if request.method == "POST":
        form = ShiftEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            # Zeit wird aktuell nur zur Validierung genutzt,
            # gespeichert wird weiterhin das Datum im Modell.
            entry.save()

            # Bild (optional)
            image_file = form.cleaned_data.get("image")
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            # Video (optional)
            video_file = form.cleaned_data.get("video")
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            return redirect("home")
    else:
        now = timezone.localtime().replace(second=0, microsecond=0)
        initial = {
            "date": now.date(),      # Datum = heute
            "time": now.time(),      # Uhrzeit = jetzt (für das neue Feld in der Form)
        }
        form = ShiftEntryForm(initial=initial)

    return render(request, "buch/entry_form.html", {"form": form})


# -------------------------------------------------------------------
# Detailansicht
# -------------------------------------------------------------------
@login_required
def entry_detail(request, entry_id):
    """
    Detailansicht:
    - zeigt Grunddaten, Bilder, Videos
    - zeigt Historie (ShiftEntryUpdate)
    - über can_view_spares wird gesteuert, wer Ersatzteile sieht:
      * Admin
      * Meister
      * Ersteller
      * jeder, der einen Update-Eintrag zu diesem Eintrag geschrieben hat
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)
    user = request.user

    is_owner = (entry.user_id == user.id)
    is_admin_or_meister = (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Meister"]).exists()
    )
    has_updated = entry.updates.filter(user=user).exists()

    can_view_spares = is_owner or is_admin_or_meister or has_updated

    # Likes
    likes_count = getattr(entry, "likes", None).count() if hasattr(entry, "likes") else 0
    user_liked = (
        hasattr(entry, "likes")
        and entry.likes.filter(user=user).exists()
    )

    # Historie
    updates = entry.updates.select_related("user").all()

    context = {
        "entry": entry,
        "can_view_spares": can_view_spares,
        "likes_count": likes_count,
        "user_liked": user_liked,
        "updates": updates,
    }
    return render(request, "buch/entry_detail.html", context)


# -------------------------------------------------------------------
# Eintrag ergänzen
# -------------------------------------------------------------------
@login_required
def update_entry(request, entry_id):
    """
    Ergänzung zu einem vorhandenen Eintrag:
    - Kommentar
    - Zeitpunkt der Maßnahme (vom Benutzer gewählt, nicht in der Zukunft – Form prüft)
    - optional neuer Status
    - optionale Ersatzteil-Daten
      -> wenn gleiche SAP-Nummer wie im Haupteintrag:
         * entnommene Anzahl wird addiert
         * Bestand wird durch neuen Wert ersetzt
      -> wenn andere SAP-Nummer oder bisher keine:
         * Werte werden einfach gesetzt / überschrieben
    - optional zusätzliches Bild
    - optional zusätzliches Video
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    if request.method == "POST":
        form = ShiftEntryUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.cleaned_data["comment"]
            action_time = form.cleaned_data["action_time"]

            # Status-Handling
            status_before = entry.status
            new_status = form.cleaned_data.get("status") or entry.status

            # -----------------------------
            # Ersatzteil-Daten aus Formular
            # -----------------------------
            used_spare_parts = form.cleaned_data.get("used_spare_parts")
            spare_desc = form.cleaned_data.get("spare_part_description")
            spare_sap = form.cleaned_data.get("spare_part_sap_number")
            qty_used = form.cleaned_data.get("spare_part_quantity_used")
            qty_remaining = form.cleaned_data.get("spare_part_quantity_remaining")

            # -----------------------------
            # Änderungen am Haupteintrag
            # -----------------------------
            # 1) Status setzen (noch nicht speichern)
            entry.status = new_status

            # 2) Ersatzteil-Logik
            if used_spare_parts and spare_sap:
                entry.used_spare_parts = True

                existing_sap = (entry.spare_part_sap_number or "").strip()
                new_sap = spare_sap.strip()

                # Beschreibung: nur setzen, wenn bisher leer
                if spare_desc:
                    if not entry.spare_part_description:
                        entry.spare_part_description = spare_desc

                if existing_sap and existing_sap == new_sap:
                    # Gleiche SAP-Nummer -> entnommene Anzahl addieren
                    old_qty_used = entry.spare_part_quantity_used or 0
                    add_qty = qty_used or 0
                    entry.spare_part_quantity_used = old_qty_used + add_qty

                    # Bestand durch neuen Wert ersetzen (wenn angegeben)
                    if qty_remaining is not None:
                        entry.spare_part_quantity_remaining = qty_remaining
                else:
                    # neue / erstmalige SAP-Nummer
                    entry.spare_part_sap_number = new_sap
                    if qty_used is not None:
                        entry.spare_part_quantity_used = qty_used
                    if qty_remaining is not None:
                        entry.spare_part_quantity_remaining = qty_remaining

            # 3) Änderungen am Haupteintrag einmal speichern
            entry.save()

            # -----------------------------
            # Historien-Eintrag anlegen
            # -----------------------------
            ShiftEntryUpdate.objects.create(
                entry=entry,
                user=request.user,
                comment=comment,
                action_time=action_time,
                status_before=status_before,
                status_after=new_status,
            )

            # -----------------------------
            # Medien zur Ergänzung
            # -----------------------------
            image_file = form.cleaned_data.get("image")
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            video_file = form.cleaned_data.get("video")
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            return redirect("entry_detail", entry_id=entry.id)
    else:
        # Default: jetzt, auf volle Minute gerundet, Status = aktueller Status
        now = timezone.localtime().replace(second=0, microsecond=0)
        form = ShiftEntryUpdateForm(initial={
            "action_time": now,
            "status": entry.status,
        })

    return render(request, "buch/entry_update.html", {
        "entry": entry,
        "form": form,
    })


# -------------------------------------------------------------------
# Diagnose-Seite Medien
# -------------------------------------------------------------------
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
    shift_dir = os.path.join(settings.MEDIA_ROOT, "shift_images")
    if os.path.isdir(shift_dir):
        files = os.listdir(shift_dir)
        lines.append(f"shift_images-Verzeichnis gefunden unter: {shift_dir}")
        lines.append(f"Dateien darin: {files}")
    else:
        lines.append(f"shift_images-Verzeichnis NICHT gefunden unter: {shift_dir}")

    return HttpResponse("<br>".join(lines))


# -------------------------------------------------------------------
# Likes
# -------------------------------------------------------------------
@login_required
def toggle_like(request, entry_id):
    """
    Like/Unlike für einen Eintrag.
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    like, created = Like.objects.get_or_create(
        user=request.user,
        entry=entry,
    )

    if not created:
        # existierte schon -> wieder entfernen = "unlike"
        like.delete()

    return redirect("entry_detail", entry_id=entry.id)