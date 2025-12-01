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
    SparePart,
)
from .forms import ShiftEntryForm, ShiftEntryUpdateForm


# ---------------------------------------------------
# Startseite mit Statistiken und Tabellen
# ---------------------------------------------------
@login_required
def home(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Montag

    # Kacheln
    entries_today = ShiftEntry.objects.filter(date=today).count()
    entries_week = ShiftEntry.objects.filter(
        date__gte=week_start, date__lte=today
    ).count()
    open_entries = ShiftEntry.objects.filter(status="OFFEN").count()
    done_entries = ShiftEntry.objects.filter(status="ERLED").count()

    # Top-Maschinen nach Störung (optional)
    top_machines = (
        ShiftEntry.objects.filter(category="STOER")
        .values("machine__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    # Diagramm 1: Verteilung nach Status
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
        code = row["status"]
        label = STATUS_LABELS.get(code, code)
        status_labels.append(label)
        status_data.append(row["count"])

    # Diagramm 2: Einträge pro Tag (letzte 7 Tage)
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
        date_labels.append(d.strftime("%d.%m."))
        date_data.append(counts_by_date.get(d, 0))

    # Letzte 20 Einträge
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
        "status_labels_json": json.dumps(status_labels),
        "status_data_json": json.dumps(status_data),
        "date_labels_json": json.dumps(date_labels),
        "date_data_json": json.dumps(date_data),
    }
    return render(request, "buch/home.html", context)


# ---------------------------------------------------
# Neuer Eintrag
# ---------------------------------------------------
@login_required
def new_entry(request):
    if request.method == "POST":
        form = ShiftEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()

            # Bild (optional)
            image_file = form.cleaned_data.get("image")
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            # Video (optional)
            video_file = form.cleaned_data.get("video")
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            # Falls im Hauptformular Ersatzteile gesetzt wurden,
            # setzen wir used_spare_parts entsprechend (ist eh im Model).
            if entry.used_spare_parts:
                # damit es auf der Detailseite klar ist
                entry.save()

            return redirect("home")
    else:
        initial = {"date": timezone.localdate()}
        form = ShiftEntryForm(initial=initial)

    return render(request, "buch/entry_form.html", {"form": form})


# ---------------------------------------------------
# Detailansicht
# ---------------------------------------------------
@login_required
def entry_detail(request, entry_id):
    entry = get_object_or_404(ShiftEntry, id=entry_id)
    user = request.user

    # Rechte für Ersatzteile: Ersteller ODER Admin/Meister ODER jemand, der ergänzt hat
    is_owner = (entry.user_id == user.id)
    is_admin_or_meister = (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Meister"]).exists()
    )
    is_contributor = entry.updates.filter(user=user).exists()

    can_view_spares = is_owner or is_admin_or_meister or is_contributor

    # Likes
    likes_count = entry.likes.count() if hasattr(entry, "likes") else 0
    user_liked = entry.likes.filter(user=user).exists() if hasattr(entry, "likes") else False

    updates = entry.updates.select_related("user").order_by("action_time", "id")
    spare_parts = entry.spare_parts.all().order_by("sap_number", "id")

    context = {
        "entry": entry,
        "can_view_spares": can_view_spares,
        "likes_count": likes_count,
        "user_liked": user_liked,
        "updates": updates,
        "spare_parts": spare_parts,
    }
    return render(request, "buch/entry_detail.html", context)


# ---------------------------------------------------
# Eintrag ERGÄNZEN
# ---------------------------------------------------
@login_required
def update_entry(request, entry_id):
    """
    Ergänzung zu einem vorhandenen Eintrag:
    - Kommentar + Zeitpunkt
    - optional neuer Status
    - optional Bild/Video
    - optional strukturierte Ersatzteile:
      * Beschreibung
      * SAP-Nummer
      * entnommene Anzahl
      * neuer Restbestand

    Logik für Ersatzteile:
    - wenn SAP-Nummer bereits für diesen Eintrag existiert
      -> quantity_used += neue_Menge
      -> quantity_remaining = neuer Restbestand (falls angegeben)
    - sonst neues SparePart-Objekt anlegen
    - Legacy-Felder auf ShiftEntry werden konsistent mitgezogen
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    if request.method == "POST":
        form = ShiftEntryUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.cleaned_data["comment"]
            action_time = form.cleaned_data["action_time"]
            new_status = form.cleaned_data.get("status") or entry.status

            # Historien-Eintrag speichern
            update = ShiftEntryUpdate.objects.create(
                entry=entry,
                user=request.user,
                comment=comment,
                action_time=action_time,
                status_before=entry.status,
                status_after=new_status,
            )

            # Status am Haupteintrag anpassen (falls geändert)
            if new_status != entry.status:
                entry.status = new_status
                entry.save()

            # Bild (optional)
            image_file = form.cleaned_data.get("image")
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            # Video (optional)
            video_file = form.cleaned_data.get("video")
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            # ----------------------------
            # Ersatzteile aus Ergänzung
            # ----------------------------
            if form.cleaned_data.get("used_spare_parts"):
                sap = (form.cleaned_data.get("spare_part_sap_number") or "").strip()
                desc = (form.cleaned_data.get("spare_part_description") or "").strip()
                qty_used = form.cleaned_data.get("spare_part_quantity_used") or 0
                qty_rem = form.cleaned_data.get("spare_part_quantity_remaining")

                if sap and qty_used > 0:
                    spare, created = SparePart.objects.get_or_create(
                        entry=entry,
                        sap_number=sap,
                        defaults={
                            "description": desc,
                            "quantity_used": qty_used,
                            "quantity_remaining": qty_rem or 0,
                            "created_by": request.user,
                        },
                    )
                    if not created:
                        # Menge addieren
                        spare.quantity_used += qty_used
                        # Restbestand überschreiben, wenn angegeben
                        if qty_rem is not None:
                            spare.quantity_remaining = qty_rem
                        # Beschreibung ergänzen, falls bisher leer
                        if desc and not spare.description:
                            spare.description = desc
                        spare.save()

                    # Legacy-Felder im Haupt-Eintrag konsistent halten
                    entry.used_spare_parts = True
                    entry.spare_part_sap_number = sap or entry.spare_part_sap_number

                    if desc and not entry.spare_part_description:
                        entry.spare_part_description = desc

                    if entry.spare_part_quantity_used is None:
                        entry.spare_part_quantity_used = 0
                    entry.spare_part_quantity_used = (
                        (entry.spare_part_quantity_used or 0) + qty_used
                    )

                    if qty_rem is not None:
                        entry.spare_part_quantity_remaining = qty_rem

                    entry.save()

            return redirect("entry_detail", entry_id=entry.id)
    else:
        now = timezone.now().replace(second=0, microsecond=0)
        form = ShiftEntryUpdateForm(
            initial={
                "action_time": now,
                "status": entry.status,
            }
        )

    return render(request, "buch/entry_update.html", {
        "entry": entry,
        "form": form,
    })


# ---------------------------------------------------
# Debug Media
# ---------------------------------------------------
@login_required
def debug_media(request):
    lines = [f"MEDIA_ROOT: {settings.MEDIA_ROOT}"]

    images = ShiftEntryImage.objects.all()
    if not images:
        lines.append("Keine ShiftEntryImage-Objekte in der DB.")
    else:
        for img in images:
            path = img.image.name
            exists = default_storage.exists(path)
            lines.append(f"{img.id}: {path} -> exists={exists}")

    shift_dir = os.path.join(settings.MEDIA_ROOT, "shift_images")
    if os.path.isdir(shift_dir):
        files = os.listdir(shift_dir)
        lines.append(f"shift_images-Verzeichnis gefunden unter: {shift_dir}")
        lines.append(f"Dateien darin: {files}")
    else:
        lines.append(f"shift_images-Verzeichnis NICHT gefunden unter: {shift_dir}")

    return HttpResponse("<br>".join(lines))


# ---------------------------------------------------
# Likes
# ---------------------------------------------------
@login_required
def toggle_like(request, entry_id):
    entry = get_object_or_404(ShiftEntry, id=entry_id)

    like, created = Like.objects.get_or_create(
        user=request.user,
        entry=entry,
    )
    if not created:
        like.delete()

    return redirect("entry_detail", entry_id=entry.id)