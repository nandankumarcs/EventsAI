from __future__ import annotations

from calendar import monthrange
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")

LOCATION_ALIASES = {
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
    "ncr": "New Delhi",
    "gurgaon": "Gurugram",
    "bangalore": "Bengaluru",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
}

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

TIME_BUCKETS = {
    "morning": (time(9, 0), time(12, 0), time(10, 0)),
    "afternoon": (time(13, 0), time(17, 0), time(15, 0)),
    "evening": (time(18, 0), time(21, 0), time(19, 0)),
    "night": (time(20, 0), time(23, 0), time(21, 0)),
}


@dataclass
class ResolverResult:
    status: str
    filter_key: str
    resolved_values: list[Any]
    message: str = ""
    confidence: float | None = None
    candidates: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "filter_key": self.filter_key,
            "resolved_values": self.resolved_values,
            "message": self.message,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.candidates is not None:
            payload["candidates"] = self.candidates
        return payload


def resolve_catalog_values(
    *,
    filter_key: str,
    requested_values: list[str] | str | None,
    available_values: list[str],
    aliases: dict[str, str] | None = None,
) -> ResolverResult:
    aliases = aliases or {}
    requests = _normalize_requested_values(requested_values)

    if not requests:
        return ResolverResult(
            status="no_input",
            filter_key=filter_key,
            resolved_values=[],
            message="No values were provided to resolve.",
            confidence=0.0,
        )

    available_lookup = {value.lower(): value for value in available_values}
    resolved: list[str] = []
    ambiguous_candidates: list[str] = []

    for request in requests:
        normalized = request.lower()
        aliased = aliases.get(normalized, normalized)

        if aliased.lower() in available_lookup:
            resolved.append(available_lookup[aliased.lower()])
            continue

        partial_matches = [
            value
            for value in available_values
            if normalized in value.lower() or value.lower() in normalized
        ]

        if len(partial_matches) == 1:
            resolved.append(partial_matches[0])
            continue

        if len(partial_matches) > 1:
            ambiguous_candidates.extend(partial_matches)
            continue

    deduped_resolved = list(dict.fromkeys(resolved))

    if deduped_resolved:
        return ResolverResult(
            status="resolved",
            filter_key=filter_key,
            resolved_values=deduped_resolved,
            message=f"Resolved {len(deduped_resolved)} value(s) for {filter_key}.",
            confidence=0.92,
        )

    if ambiguous_candidates:
        candidates = sorted(dict.fromkeys(ambiguous_candidates))
        return ResolverResult(
            status="ambiguous",
            filter_key=filter_key,
            resolved_values=[],
            message=f"Multiple possible matches found for {filter_key}.",
            confidence=0.45,
            candidates=candidates,
        )

    return ResolverResult(
        status="no_match",
        filter_key=filter_key,
        resolved_values=[],
        message=f"No matching values found for {filter_key}.",
        confidence=0.0,
    )


def resolve_location_values(
    requested_values: list[str] | str | None,
    available_values: list[str],
) -> ResolverResult:
    return resolve_catalog_values(
        filter_key="city",
        requested_values=requested_values,
        available_values=available_values,
        aliases=LOCATION_ALIASES,
    )


def extract_catalog_mentions(
    *,
    filter_key: str,
    text: str,
    available_values: list[str],
    aliases: dict[str, str] | None = None,
) -> ResolverResult:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return ResolverResult(
            status="no_input",
            filter_key=filter_key,
            resolved_values=[],
            message="No text was provided to resolve.",
            confidence=0.0,
        )

    aliases = aliases or {}
    resolved: list[str] = []

    for available_value in sorted(available_values, key=len, reverse=True):
        if _normalize_text(available_value) in normalized_text:
            resolved.append(available_value)

    for alias, target in aliases.items():
        if _normalize_text(alias) not in normalized_text:
            continue

        matched_target = _match_catalog_target(target, available_values)
        if matched_target:
            resolved.append(matched_target)

    deduped = list(dict.fromkeys(resolved))
    if deduped:
        return ResolverResult(
            status="resolved",
            filter_key=filter_key,
            resolved_values=deduped,
            message=f"Resolved {len(deduped)} value(s) for {filter_key}.",
            confidence=0.95,
        )

    return ResolverResult(
        status="no_match",
        filter_key=filter_key,
        resolved_values=[],
        message=f"No matching values found for {filter_key}.",
        confidence=0.0,
    )


def get_temporal_reference(
    *,
    reference_date: date | str | None = None,
    timezone_name: str = "Asia/Kolkata",
) -> dict[str, Any]:
    resolved_reference_date = _coerce_date(reference_date) or timezone.localdate()
    current_week_start = resolved_reference_date - timedelta(days=resolved_reference_date.weekday())
    current_week_end = current_week_start + timedelta(days=6)
    next_week_start = current_week_end + timedelta(days=1)
    next_week_end = next_week_start + timedelta(days=6)
    month_start = resolved_reference_date.replace(day=1)
    month_end = resolved_reference_date.replace(
        day=monthrange(resolved_reference_date.year, resolved_reference_date.month)[1]
    )
    if resolved_reference_date.month == 12:
        next_month_start = resolved_reference_date.replace(year=resolved_reference_date.year + 1, month=1, day=1)
    else:
        next_month_start = resolved_reference_date.replace(month=resolved_reference_date.month + 1, day=1)
    next_month_end = next_month_start.replace(
        day=monthrange(next_month_start.year, next_month_start.month)[1]
    )

    return {
        "reference_date": resolved_reference_date.isoformat(),
        "timezone": timezone_name,
        "weekday_index": resolved_reference_date.weekday(),
        "weekday_name": resolved_reference_date.strftime("%A"),
        "current_week_start": current_week_start.isoformat(),
        "current_week_end": current_week_end.isoformat(),
        "next_week_start": next_week_start.isoformat(),
        "next_week_end": next_week_end.isoformat(),
        "current_month_start": month_start.isoformat(),
        "current_month_end": month_end.isoformat(),
        "next_month_start": next_month_start.isoformat(),
        "next_month_end": next_month_end.isoformat(),
        "current_month": resolved_reference_date.month,
        "current_year": resolved_reference_date.year,
        "current_day": resolved_reference_date.day,
    }


def resolve_weekday_date(
    *,
    reference_date: date | str | None,
    weekday_name: str,
    scope: str = "upcoming",
) -> str:
    resolved_reference_date = _coerce_date(reference_date) or timezone.localdate()
    normalized_weekday = weekday_name.strip().lower()
    if normalized_weekday not in WEEKDAY_INDEX:
        raise ValueError(f"Unsupported weekday: {weekday_name}")

    weekday_index = WEEKDAY_INDEX[normalized_weekday]
    current_week_start = resolved_reference_date - timedelta(days=resolved_reference_date.weekday())

    if scope == "this_week":
        return (current_week_start + timedelta(days=weekday_index)).isoformat()

    if scope == "next_week":
        next_week_start = current_week_start + timedelta(days=7)
        return (next_week_start + timedelta(days=weekday_index)).isoformat()

    if scope != "upcoming":
        raise ValueError(f"Unsupported weekday scope: {scope}")

    days_ahead = (weekday_index - resolved_reference_date.weekday()) % 7
    return (resolved_reference_date + timedelta(days=days_ahead)).isoformat()


def build_calendar_date(*, year: int, month: int, day: int) -> str:
    return date(year, month, day).isoformat()


def shift_iso_date(*, date_value: str, days: int) -> str:
    return (date.fromisoformat(date_value) + timedelta(days=days)).isoformat()


def build_date_range(*, start_date: str | None = None, end_date: str | None = None) -> dict[str, str | None]:
    if start_date is not None:
        date.fromisoformat(start_date)
    if end_date is not None:
        date.fromisoformat(end_date)
    return {"date_from": start_date, "date_to": end_date}


def normalize_clock_time(*, time_text: str) -> dict[str, str]:
    normalized_text = time_text.strip().lower()
    regex = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        normalized_text,
    )
    if regex is None:
        raise ValueError(f"Could not normalize time value: {time_text}")

    hour = int(regex.group(1))
    minute = int(regex.group(2) or "0")
    meridiem = regex.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    if meridiem is None and hour > 23:
        raise ValueError(f"Invalid 24-hour time value: {time_text}")
    if minute > 59:
        raise ValueError(f"Invalid time value: {time_text}")

    return {"normalized_time": time(hour, minute).isoformat()}


def build_time_window(*, anchor_time: str, radius_minutes: int = 60) -> dict[str, str]:
    anchor = time.fromisoformat(anchor_time)
    return {
        "anchor_time": anchor.isoformat(),
        "start": _shift_time(anchor, -radius_minutes).isoformat(),
        "end": _shift_time(anchor, radius_minutes).isoformat(),
    }


def get_named_time_bucket(*, label: str) -> dict[str, str]:
    normalized_label = label.strip().lower()
    if normalized_label not in TIME_BUCKETS:
        raise ValueError(f"Unsupported time bucket: {label}")

    start, end, anchor = TIME_BUCKETS[normalized_label]
    return {
        "anchor_time": anchor.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def build_temporal_response_payload(
    filters: Any,
    *,
    reference_date: date | str | None = None,
    timezone_name: str = "Asia/Kolkata",
) -> dict[str, Any]:
    resolved_reference_date = _coerce_date(reference_date) or timezone.localdate()
    tz = ZoneInfo(timezone_name)
    payload = _coerce_filter_payload(filters)

    event_dates = payload.get("event_dates", []) or []
    date_from = payload.get("date_from")
    date_to = payload.get("date_to")
    start_time_from = payload.get("start_time_from")
    start_time_to = payload.get("start_time_to")
    anchor_time = _derive_anchor_time(start_time_from, start_time_to)

    resolved_datetimes: list[str] = []
    if anchor_time:
        for event_date in event_dates:
            resolved_datetimes.append(
                datetime.combine(date.fromisoformat(event_date), anchor_time, tzinfo=tz).isoformat()
            )

    return {
        "reference_date": resolved_reference_date.isoformat(),
        "dates": event_dates,
        "date_from": date_from,
        "date_to": date_to,
        "resolved_datetimes": resolved_datetimes,
        "time_range": {
            "start": start_time_from,
            "end": start_time_to,
        },
        "anchor_time": anchor_time.isoformat() if anchor_time else None,
    }


def _normalize_requested_values(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r",|/|\bor\b|\band\b", value) if item.strip()]
    return [item.strip() for item in value if item and item.strip()]


def _match_catalog_target(target: str, available_values: list[str]) -> str | None:
    normalized_target = _normalize_text(target)

    for available_value in available_values:
        if _normalize_text(available_value) == normalized_target:
            return available_value

    partial_matches = [
        available_value
        for available_value in available_values
        if normalized_target in _normalize_text(available_value)
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    return None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _shift_time(value: time, minutes: int) -> time:
    anchor = datetime.combine(date(2000, 1, 1), value) + timedelta(minutes=minutes)
    return anchor.time()


def _coerce_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _coerce_filter_payload(filters: Any) -> dict[str, Any]:
    if hasattr(filters, "model_dump"):
        return filters.model_dump()
    if isinstance(filters, dict):
        return filters
    raise TypeError("Unsupported filter payload type.")


def _derive_anchor_time(
    start_time_from: str | None,
    start_time_to: str | None,
) -> time | None:
    if not start_time_from or not start_time_to:
        return None

    start = time.fromisoformat(start_time_from)
    end = time.fromisoformat(start_time_to)
    start_dt = datetime.combine(date(2000, 1, 1), start)
    end_dt = datetime.combine(date(2000, 1, 1), end)
    midpoint = start_dt + (end_dt - start_dt) / 2
    return midpoint.time().replace(microsecond=0)
