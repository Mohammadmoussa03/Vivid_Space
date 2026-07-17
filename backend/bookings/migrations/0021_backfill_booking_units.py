"""Give every booking of a multi-unit space an explicit unit label.

Bookings made while a space had a single unit were saved with `unit = ''` — the
booking modal only asks for a unit once `units > 1`. Once an admin adds a second
unit those rows become ambiguous: they occupy *a* room but name none. Capacity
still adds up (an unnamed booking counts as one occupied unit), but identity
doesn't — a member can then book "Unit 1" for a time an unnamed booking already
holds, which in practice is the very same room.

This stamps each unit-less booking with a unit that was actually free at its
time, so the ambiguity is resolved from here on.

The label logic is inlined rather than imported from `Space.unit_labels`: a data
migration must keep behaving the same even if that property changes later.
"""
from django.db import migrations


def _labels_for(space):
    """Mirror of Space.unit_labels at the time of this migration. Kept in step
    with it deliberately: if this stamped a label the property doesn't generate,
    the booking would point at a unit the picker never shows."""
    names = [str(n).strip() for n in (space.unit_names or []) if str(n).strip()]
    total = space.units or 1
    if len(names) >= total:
        return names[:total]
    base = (space.name or '').strip()
    used = {n.lower() for n in names}
    labels = list(names)
    i = len(labels) + 1
    while len(labels) < total:
        candidate = f'{base} {i}' if base else f'Unit {i}'
        if candidate.lower() not in used:
            labels.append(candidate)
            used.add(candidate.lower())
        i += 1
    return labels


def _overlaps(a, b):
    """True when two same-day bookings share any time. A full-day booking (or one
    with missing times) occupies the whole day."""
    if a.duration == 'fullday' or not a.start_time or not a.end_time:
        return True
    if b.duration == 'fullday' or not b.start_time or not b.end_time:
        return True
    return a.start_time < b.end_time and b.start_time < a.end_time


def backfill(apps, schema_editor):
    Space = apps.get_model('bookings', 'Space')
    Booking = apps.get_model('bookings', 'Booking')

    for space in Space.objects.all():
        if (space.units or 1) <= 1:
            continue  # single-unit space: a blank unit is unambiguous already
        labels = _labels_for(space)
        # Oldest first, so long-standing bookings keep the lowest-numbered unit.
        rows = list(space.bookings.exclude(status='cancelled')
                    .order_by('date', 'start_time', 'id'))
        for booking in rows:
            if (booking.unit or '').strip():
                continue
            same_day = [b for b in rows if b.date == booking.date and b.id != booking.id]
            taken = {(b.unit or '').strip().lower()
                     for b in same_day
                     if (b.unit or '').strip() and _overlaps(booking, b)}
            free = next((l for l in labels if l.lower() not in taken), None)
            if free is None:
                # Every unit is occupied at this time — the row predates capacity
                # being enforced. Leave it blank rather than invent a double-booking.
                continue
            booking.unit = free
            booking.save(update_fields=['unit'])


def noop(apps, schema_editor):
    """Irreversible by design: we can't tell a backfilled unit from one the
    member actually chose, so undoing would wrongly blank real selections."""


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0020_remove_order_auto_verified_remove_order_ocr_text'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
