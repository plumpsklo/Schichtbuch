from datetime import timedelta
import os
import json
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User

from .models import (
    Machine,
    ShiftEntry,
    ShiftEntryImage,
    ShiftEntryVideo,
    Like,
    ShiftEntryUpdate,
    MentionNotification,
)
from .forms import ShiftEntryForm, ShiftEntryUpdateForm


# ---------------------------------------------------------
# Helper: @username im Text erkennen und Benachrichtigungen erstellen
# ---------------------------------------------------------

MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.\-]+)")


def _create_mentions_from_text(text, entry, created_by, source: str):
    """
    Sucht im Text nach @username und legt MentionNotification für existierende User an.

    - text: Titel, Beschreibung oder Kommentar
    - entry: ShiftEntry-Instanz
    - created_by: User, der die Erwähnung auslöst
    - source: "ENTRY" oder "UPDATE"
    """
    if not text:
        return

    # Alle Usernames aus dem Text ziehen (ohne Duplikate)
    usernames = set(MENTION_PATTERN.findall(text))
    if not usernames:
        return

    # Passende Benutzer holen
    users = User.objects.filter(username__in=usernames).distinct()

    for target_user in users:
        # Sich selbst erwähnen ist sinnlos -> überspringen
        if created_by and target_user.id == created_by.id:
            continue

        snippet = text.strip()
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."

        MentionNotification.objects.create(
            user=target_user,
            entry=entry,
            created_by=created_by,
            source=source,
            text_snippet=snippet,
        )


# -------------------------------------------------------------------
# Startseite / Übersicht
# -------------------------------------------------------------------
@login_required
def home(request):
    """
    Übersicht / Dashboard:
    - Statistik-Kacheln (heute / Woche / offen / erledigt)
    - Diagramm-Daten (eigener Tab in home.html)
    - Eintragsliste mit:
      * Filtern (Maschine, Status, Schicht, Kategorie, Datum von/bis)
      * Suchfeld (Titel)
      * Einträge pro Seite wählbar
    - Benachrichtigungen bei offenen Ersatzteil-Buchungen (eigener Tab)
    """
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Montag

    # --- Statistik-Kacheln ---
    entries_today = ShiftEntry.objects.filter(date=today).count()
    entries_week = ShiftEntry.objects.filter(
        date__gte=week_start,
        date__lte=today,
    ).count()
    open_entries = ShiftEntry.objects.filter(status="OFFEN").count()
    done_entries = ShiftEntry.objects.filter(status="ERLED").count()

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
        code = row["status"]
        label = STATUS_LABELS.get(code, code)
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
        date_labels.append(d.strftime("%d.%m."))
        date_data.append(counts_by_date.get(d, 0))

    # ---------------------------------------------------------
    # Eintragsliste: ALLE Einträge, mit Filter + Suche
    # ---------------------------------------------------------
    entries_qs = (
        ShiftEntry.objects
        .select_related("machine", "user")
        .prefetch_related("additional_workers")
        .order_by("-date", "-created_at")
    )

    # Filter-/Such-Parameter aus GET
    filter_machine = request.GET.get("machine") or ""
    filter_status = request.GET.get("status") or ""
    filter_shift = request.GET.get("shift") or ""
    filter_category = request.GET.get("category") or ""
    filter_date_from = request.GET.get("date_from") or ""
    filter_date_to = request.GET.get("date_to") or ""
    filter_search = (request.GET.get("search") or "").strip()

    if filter_machine:
        entries_qs = entries_qs.filter(machine_id=filter_machine)

    if filter_status:
        entries_qs = entries_qs.filter(status=filter_status)

    if filter_shift:
        entries_qs = entries_qs.filter(shift=filter_shift)

    if filter_category:
        entries_qs = entries_qs.filter(category=filter_category)

    if filter_date_from:
        entries_qs = entries_qs.filter(date__gte=filter_date_from)

    if filter_date_to:
        entries_qs = entries_qs.filter(date__lte=filter_date_to)

    if filter_search:
        entries_qs = entries_qs.filter(title__icontains=filter_search)

    # ---------------------------------------------------------
    # Einträge pro Seite
    # ---------------------------------------------------------
    default_per_page = 20
    try:
        per_page = int(request.GET.get("per_page", default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page

    if per_page < 5:
        per_page = 5
    if per_page > 200:
        per_page = 200

    per_page_options = [10, 20, 50, 100]

    paginator = Paginator(entries_qs, per_page)
    page_number = request.GET.get("page")

    try:
        entries_page = paginator.page(page_number)
    except PageNotAnInteger:
        entries_page = paginator.page(1)
    except EmptyPage:
        entries_page = paginator.page(paginator.num_pages)

    # Sind aktuell Filter aktiv?
    filters_active = bool(
        filter_machine
        or filter_status
        or filter_shift
        or filter_category
        or filter_date_from
        or filter_date_to
        or filter_search
        or per_page != default_per_page
    )

    # --- Rolle: Meister/Admin? ---
    user = request.user
    is_admin_or_meister = (
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name__in=["Admin", "Meister"]).exists()
        )
    )

    # --- Benachrichtigungen: offene Ersatzteil-Buchungen ---
    notifications = []
    notifications_count = 0
    if is_admin_or_meister:
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

    # Dropdown-Daten
    machines = Machine.objects.filter(is_active=True).order_by("name")
    shift_choices = ShiftEntry.SHIFT_CHOICES
    status_choices = ShiftEntry.STATUS_CHOICES
    category_choices = ShiftEntry.CATEGORY_CHOICES

    context = {
        "entries_today": entries_today,
        "entries_week": entries_week,
        "open_entries": open_entries,
        "done_entries": done_entries,

        # paginierte Einträge
        "entries": entries_page,
        "page_obj": entries_page,
        "is_paginated": paginator.num_pages > 1,
        "per_page": per_page,
        "per_page_options": per_page_options,
        "filters_active": filters_active,

        # Filter-/Suchwerte (für Formular + Pagination)
        "filter_machine": filter_machine,
        "filter_status": filter_status,
        "filter_shift": filter_shift,
        "filter_category": filter_category,
        "filter_date_from": filter_date_from,
        "filter_date_to": filter_date_to,
        "filter_search": filter_search,

        # Daten für Dropdowns
        "machines": machines,
        "shift_choices": shift_choices,
        "status_choices": status_choices,
        "category_choices": category_choices,

        # Diagramm-Daten
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
    - optionale Medien (Bild, Video)
    - zusätzliche Mitarbeiter (additional_workers)
    - @Erwähnungen in Titel/Beschreibung erzeugen MentionNotification
    """
    if request.method == "POST":
        form = ShiftEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user

            # Falls Formular ein kombiniertes action_datetime liefert, darauf mappen
            action_dt = form.cleaned_data.get("action_datetime")
            if action_dt:
                entry.date = action_dt.date()
                entry.time = action_dt.time()

            entry.save()

            # ManyToMany: weitere Mitarbeiter
            additional_workers = form.cleaned_data.get("additional_workers")
            if additional_workers is not None:
                entry.additional_workers.set(additional_workers)

            # Medien
            image_file = form.cleaned_data.get("image")
            if image_file:
                ShiftEntryImage.objects.create(entry=entry, image=image_file)

            video_file = form.cleaned_data.get("video")
            if video_file:
                ShiftEntryVideo.objects.create(entry=entry, video=video_file)

            # @mentions in Titel & Beschreibung
            _create_mentions_from_text(
                text=entry.title,
                entry=entry,
                created_by=request.user,
                source="ENTRY",
            )
            _create_mentions_from_text(
                text=entry.description,
                entry=entry,
                created_by=request.user,
                source="ENTRY",
            )

            return redirect("home")
    else:
        now = timezone.localtime().replace(second=0, microsecond=0)
        initial = {
            "date": now.date(),
            "time": now.time(),
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
    - zeigt Grunddaten, weitere Mitarbeiter, Bilder, Videos
    - zeigt Historie (ShiftEntryUpdate)
    - Ersatzteile & SAP-Fahne (nur für berechtigte Rollen)
    """
    entry = get_object_or_404(
        ShiftEntry.objects
        .select_related("machine", "user")
        .prefetch_related("additional_workers", "images", "videos", "updates", "likes"),
        id=entry_id,
    )
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
    likes_count = entry.likes.count()
    user_liked = entry.likes.filter(user=user).exists()

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
    - optionale Ersatzteil-Daten (alte Felder)
    - optionale zusätzliche Medien (Bild, Video)
    - @Erwähnungen im Kommentar erzeugen MentionNotification (Quelle=UPDATE)
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
            # Ersatzteil-Daten (alte Felder)
            # -----------------------------
            used_spare_parts = form.cleaned_data.get("used_spare_parts")
            spare_desc = form.cleaned_data.get("spare_part_description")
            spare_sap = form.cleaned_data.get("spare_part_sap_number")
            qty_used = form.cleaned_data.get("spare_part_quantity_used")
            qty_remaining = form.cleaned_data.get("spare_part_quantity_remaining")

            # -----------------------------
            # Änderungen am Haupteintrag
            # -----------------------------
            entry.status = new_status

            if used_spare_parts and spare_sap:
                entry.used_spare_parts = True

                existing_sap = (entry.spare_part_sap_number or "").strip()
                new_sap = spare_sap.strip()

                # Beschreibung ggf. setzen
                if spare_desc and not entry.spare_part_description:
                    entry.spare_part_description = spare_desc

                if existing_sap and existing_sap == new_sap:
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

                # sobald erneut Ersatzteile erfasst werden, ist SAP-Fahne ungültig
                entry.spare_parts_processed = False
                entry.spare_parts_processed_by = None
                entry.spare_parts_processed_at = None

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

            # -----------------------------
            # @Erwähnungen im Kommentar
            # -----------------------------
            _create_mentions_from_text(
                text=comment,
                entry=entry,
                created_by=request.user,
                source="UPDATE",
            )

            return redirect("entry_detail", entry_id=entry.id)
    else:
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
    - Für den Eintrag müssen überhaupt Ersatzteile erfasst sein.
    """
    entry = get_object_or_404(ShiftEntry, id=entry_id)
    user = request.user

    is_admin_or_meister = (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Meister"]).exists()
    )
    if not is_admin_or_meister:
        return redirect("entry_detail", entry_id=entry.id)

    if not entry.has_any_spare_parts:
        return redirect("entry_detail", entry_id=entry.id)

    new_state = not entry.spare_parts_processed
    entry.spare_parts_processed = new_state

    if new_state:
        entry.spare_parts_processed_by = user
        entry.spare_parts_processed_at = timezone.now()
    else:
        entry.spare_parts_processed_by = None
        entry.spare_parts_processed_at = None

    entry.save()

    return redirect("entry_detail", entry_id=entry.id)


# -------------------------------------------------------------------
# Erwähnungs-Benachrichtigungen – klassische Ansicht
# (wird z.B. über URL-Namen 'mention_notifications' aufgerufen)
# -------------------------------------------------------------------
@login_required
def mention_notifications_view(request):
    """
    Liste der Erwähnungs-Benachrichtigungen für den eingeloggten Benutzer.
    Optional: per POST alle als gelesen markieren.
    Nutzt das Template buch/mention_notifications.html mit Kontext 'notifications'.
    """
    qs = (
        MentionNotification.objects
        .filter(user=request.user)
        .select_related("entry", "created_by", "entry__machine")
        .order_by("-created_at")
    )

    if request.method == "POST":
        qs.update(is_read=True)
        return redirect("mention_notifications")

    notifications = list(qs)

    context = {
        "notifications": notifications,
    }
    return render(request, "buch/mention_notifications.html", context)


# -------------------------------------------------------------------
# Erwähnungs-Benachrichtigungen – Inbox (Header-Button "Hinweise")
# -------------------------------------------------------------------
@login_required
def notifications_inbox(request):
    """
    Wird von der Navigationsleiste (Button 'Hinweise') aufgerufen.
    Nutzt das gleiche Template wie mention_notifications_view.

    - zeigt alle Erwähnungen (unabhängig von gelesen/ungelesen)
    - markiert beim Aufruf alle ungelesenen als gelesen
    """
    user = request.user

    qs = (
        MentionNotification.objects
        .filter(user=user)
        .select_related("entry", "created_by", "entry__machine")
        .order_by("-created_at")
    )

    # Ungelesene beim Öffnen als gelesen markieren
    qs.filter(is_read=False).update(is_read=True)

    notifications = list(qs)

    context = {
        "notifications": notifications,
    }
    return render(request, "buch/mention_notifications.html", context)


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
        like.delete()

    return redirect("entry_detail", entry_id=entry.id)