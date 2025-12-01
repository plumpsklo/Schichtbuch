from datetime import timedelta
import os
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

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
    """
    Übersicht / Dashboard:
    - Statistik-Kacheln (heute / Woche / offen / erledigt)
    - Top-Maschinen nach Störung
    - Diagramme:
      * Verteilung nach Status
      * Einträge pro Tag (letzte 7 Tage)
    - Letzte 20 Einträge
    - Für Meister/Admin zusätzlich:
      * Benachrichtigungsliste für Einträge mit offenen Ersatzteil-Buchungen
        (Ersatzteile verwendet, aber nicht als 'in SAP verbucht' markiert).
    """
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

    # --- Rolle: ist der aktuelle Benutzer Meister/Admin? ---
    user = request.user
    is_admin_or_meister = (
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name__in=["Admin", "Meister"]).exists()
        )
    )

    # --- Benachrichtigungen: offene Ersatzteil-Buchungen (nur für Meister/Admin) ---
    notifications = []
    notifications_count = 0

    if is_admin_or_meister:
        # Bedingung:
        # - Ersatzteile verwendet (alte Felder oder strukturierte SpareParts)
        # - noch nicht in SAP verbucht
        notifications_qs = (
            ShiftEntry.objects
            .select_related("machine", "user")
            .filter(spare_parts_processed=False)
            .filter(
                Q(used_spare_parts=True) | Q(spare_parts__isnull=False)
            )
            .order_by("-date", "-created_at")
            .distinct()[:50]
        )
        notifications = list(notifications_qs)
        notifications_count = len(notifications)

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
        # Benachrichtigungen / Rolleninfo
        "is_admin_or_meister": is_admin_or_meister,
        "notifications": notifications,
        "notifications_count": notifications_count,
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
    - ggf. optionale Medien (Bild, Video)
    - Datum + Uhrzeit werden zu action_datetime kombiniert (falls im Model vorhanden)
      und/oder auf date/time-Felder gemappt.
    Die Form stellt sicher, dass die Zeitangabe nicht in der Zukunft liegt.
    """
    if request.method == "POST":
        form = ShiftEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user

            # kombiniertes Datum+Uhrzeit aus der Form übernehmen (falls verwendet)
            action_dt = form.cleaned_data.get("action_datetime")
            if action_dt:
                # Falls du im Model ein action_datetime-Feld hast, hier zuweisen:
                # entry.action_datetime = action_dt
                # Falls nicht, aber date/time befüllt werden sollen:
                entry.date = action_dt.date()
                entry.time = action_dt.time()

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
            "time": now.time(),      # Uhrzeit = jetzt
        }
        form = ShiftEntryForm(initial=initial)

    return render(request, "buch/entry_form.html", {"form": form})


# -------------------------------------------------------------------
# Detailansicht
# -------------------------------------------------------------------
@login_required
def entry_detail(request, entry_id):
    """
    Detailansicht eines Schichtbucheintrags:
    - zeigt Grunddaten, Bilder, Videos
    - zeigt Historie (ShiftEntryUpdate)
    - über can_view_spares wird gesteuert, wer Ersatzteile sieht:
      * Admin
      * Meister
      * Ersteller
      * jeder, der einen Update-Eintrag zu diesem Eintrag geschrieben hat
    - can_process_spares: steuert, ob der Benutzer den SAP-Status toggeln darf
      (nur Admin/Meister).
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)
    user = request.user

    # Rollen / Berechtigungen
    is_owner = (entry.user_id == user.id)
    is_admin_or_meister = (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Meister"]).exists()
    )
    has_updated = entry.updates.filter(user=user).exists()

    # Ersatzteile sehen:
    can_view_spares = is_owner or is_admin_or_meister or has_updated

    # Ersatzteile bearbeiten (SAP-Status toggeln) nur für Admin/Meister
    can_process_spares = is_admin_or_meister

    # Likes
    likes_count = getattr(entry, "likes", None).count() if hasattr(entry, "likes") else 0
    user_liked = (
        hasattr(entry, "likes")
        and entry.likes.filter(user=user).exists()
    )

    # Historie (Ergänzungen)
    updates = entry.updates.select_related("user").all()

    context = {
        "entry": entry,
        "can_view_spares": can_view_spares,
        "can_process_spares": can_process_spares,
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
    - Zeitpunkt der Maßnahme (Form prüft: nicht in der Zukunft)
    - optional neuer Status
    - optionale Ersatzteil-Daten (alte Felder):
      -> wenn gleiche SAP-Nummer wie im Haupteintrag:
         * entnommene Anzahl wird addiert
         * Bestand wird durch neuen Wert ersetzt
      -> wenn andere SAP-Nummer oder bisher keine:
         * Werte werden gesetzt / überschrieben
    - optionale zusätzliche Medien (Bild, Video)
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

            # 2) Ersatzteil-Logik (alte Felder)
            if used_spare_parts and spare_sap:
                entry.used_spare_parts = True

                existing_sap = (entry.spare_part_sap_number or "").strip()
                new_sap = spare_sap.strip()

                # Beschreibung: nur setzen, wenn bisher leer
                if spare_desc and not entry.spare_part_description:
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

                # Achtung: sobald erneut Ersatzteile eingetragen werden,
                # kann die SAP-Buchung nicht mehr "gültig" sein -> zurücksetzen
                entry.spare_parts_processed = False
                entry.spare_parts_processed_by = None
                entry.spare_parts_processed_at = None

            # 3) Änderungen am Haupteintrag speichern
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
# SAP-Bearbeitungsstatus für Ersatzteile toggeln (nur Meister/Admin)
# -------------------------------------------------------------------
@login_required
@require_POST
def toggle_spare_parts_processed(request, entry_id):
    """
    Meister-/Admin-Funktion:
    Schaltet das Flag 'spare_parts_processed' für einen Eintrag um.

    Bedingungen:
    - Benutzer muss Admin/Meister sein.
    - Für den Eintrag müssen überhaupt Ersatzteile erfasst sein
      (entweder alte Felder oder strukturierte SpareParts).
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)
    user = request.user

    # Rolle prüfen
    is_admin_or_meister = (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Meister"]).exists()
    )

    if not is_admin_or_meister:
        return redirect("entry_detail", entry_id=entry.id)

    # Wenn keine Ersatzteile erfasst sind, macht der Haken keinen Sinn
    if not entry.has_any_spare_parts:
        return redirect("entry_detail", entry_id=entry.id)

    # Status umschalten
    new_state = not entry.spare_parts_processed
    entry.spare_parts_processed = new_state

    if new_state:
        # Jetzt als bearbeitet markiert -> User + Zeitstempel setzen
        entry.spare_parts_processed_by = user
        entry.spare_parts_processed_at = timezone.now()
    else:
        # Zurückgesetzt -> Felder leeren
        entry.spare_parts_processed_by = None
        entry.spare_parts_processed_at = None

    entry.save()

    return redirect("entry_detail", entry_id=entry.id)


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