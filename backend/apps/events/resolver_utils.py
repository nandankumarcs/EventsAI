from __future__ import annotations

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


def normalize_temporal_expression(
    text: str,
    *,
    reference_date: date | None = None,
    timezone_name: str = "Asia/Kolkata",
) -> dict[str, Any]:
    tz = ZoneInfo(timezone_name)
    reference_date = reference_date or timezone.localdate()
    lowered = text.lower()

    resolved_dates = _extract_dates(lowered, reference_date)
    start_time, end_time, anchor_time = _extract_time_info(lowered)
    resolved_datetimes = []

    if anchor_time and resolved_dates:
        for resolved_date in resolved_dates:
            resolved_datetimes.append(
                datetime.combine(resolved_date, anchor_time, tzinfo=tz).isoformat()
            )

    payload: dict[str, Any] = {
        "reference_date": reference_date.isoformat(),
        "dates": [value.isoformat() for value in resolved_dates],
        "resolved_datetimes": resolved_datetimes,
        "time_range": {
            "start": start_time.isoformat() if start_time else None,
            "end": end_time.isoformat() if end_time else None,
        },
        "anchor_time": anchor_time.isoformat() if anchor_time else None,
    }

    return payload


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


def _extract_dates(text: str, reference_date: date) -> list[date]:
    dates: list[date] = []

    if "today" in text:
        dates.append(reference_date)
    if "tomorrow" in text:
        dates.append(reference_date + timedelta(days=1))

    if "weekend" in text:
        saturday = _next_weekday(reference_date, WEEKDAY_INDEX["saturday"])
        sunday = _next_weekday(reference_date, WEEKDAY_INDEX["sunday"])
        dates.extend([saturday, sunday])

    weekday_pattern = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b")
    mentioned_weekdays = [match.group(1) for match in weekday_pattern.finditer(text)]

    for weekday in mentioned_weekdays:
        dates.append(_next_weekday(reference_date, WEEKDAY_INDEX[weekday]))

    deduped_dates = list(dict.fromkeys(dates))
    return deduped_dates


def _next_weekday(reference_date: date, target_weekday: int) -> date:
    days_ahead = (target_weekday - reference_date.weekday()) % 7
    days_ahead = 7 if days_ahead == 0 else days_ahead
    return reference_date + timedelta(days=days_ahead)


def _extract_time_info(text: str) -> tuple[time | None, time | None, time | None]:
    regex = re.search(
        r"\b(?:around|at|by)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        text,
    )
    if regex:
        hour = int(regex.group(1))
        minute = int(regex.group(2) or "0")
        meridiem = regex.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0

        anchor = time(hour, minute)
        start = _shift_time(anchor, -60)
        end = _shift_time(anchor, 60)
        return start, end, anchor

    for keyword, (start, end, anchor) in TIME_BUCKETS.items():
        if keyword in text:
            return start, end, anchor

    return None, None, None


def _shift_time(value: time, minutes: int) -> time:
    anchor = datetime.combine(date(2000, 1, 1), value) + timedelta(minutes=minutes)
    return anchor.time()
