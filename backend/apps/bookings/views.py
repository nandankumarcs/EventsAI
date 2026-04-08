import json
from datetime import datetime
from json import JSONDecodeError
from secrets import token_hex

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.bookings.models import Booking
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.events.models import MovieEvent, SportEvent
from apps.events.services import search_movie_events, search_sport_events


def booking_list_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    bookings = [_serialize_booking(booking) for booking in Booking.objects.all()]
    return JsonResponse({"count": len(bookings), "bookings": bookings})


@csrf_exempt
def booking_confirm_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        return JsonResponse({"error": f"Invalid booking payload: {exc}"}, status=400)

    thread_id = payload.get("thread_id")
    listing_code = (payload.get("listing_code") or "").strip()
    if not thread_id or not listing_code:
        return JsonResponse({"error": "thread_id and listing_code are required"}, status=400)

    thread = get_object_or_404(ChatThread, id=thread_id)
    thread_filter = ThreadFilter.objects.filter(thread=thread).first()
    event_type, event_obj, event_snapshot = _resolve_event_by_listing_code(listing_code)
    if event_obj is None:
        return JsonResponse({"error": "No event found for the given listing_code"}, status=404)

    booking = Booking.objects.create(
        thread=thread,
        booking_reference=_generate_booking_reference(),
        event_type=event_type,
        status=Booking.Status.CONFIRMED,
        movie_event=event_obj if event_type == Booking.EventType.MOVIE else None,
        sport_event=event_obj if event_type == Booking.EventType.SPORT else None,
        event_title=event_snapshot["title"],
        city=event_snapshot["city"],
        venue_name=event_snapshot["venue_name"],
        starts_at=_parse_starts_at(event_snapshot["start_at"]),
        filter_snapshot=(thread_filter.active_filters if thread_filter else {}),
        event_snapshot=event_snapshot,
        metadata={"confirmed_via": "chat"},
    )

    thread.status = ChatThread.Status.BOOKED
    confirmation_message = (
        f"Booking confirmed for {booking.event_title} in {booking.city} at "
        f"{booking.venue_name}. Your reference is {booking.booking_reference}."
    )
    thread.last_message_preview = confirmation_message[:500]
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["status", "last_message_preview", "last_activity_at", "updated_at"])

    next_position = (thread.messages.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    ChatMessage.objects.create(
        thread=thread,
        position=next_position,
        role=ChatMessage.Role.ASSISTANT,
        content=confirmation_message,
        metadata={
            "booking_id": str(booking.id),
            "booking_reference": booking.booking_reference,
            "listing_code": listing_code,
        },
    )

    return JsonResponse({"booking": _serialize_booking(booking)}, status=201)


def _resolve_event_by_listing_code(listing_code: str):
    movie_result = search_movie_events({"listing_codes": [listing_code]}, limit=1, offset=0)
    if movie_result.results:
        movie_event = MovieEvent.objects.get(listing_code=listing_code)
        return Booking.EventType.MOVIE, movie_event, movie_result.results[0]

    sport_result = search_sport_events({"listing_codes": [listing_code]}, limit=1, offset=0)
    if sport_result.results:
        sport_event = SportEvent.objects.get(listing_code=listing_code)
        return Booking.EventType.SPORT, sport_event, sport_result.results[0]

    return None, None, None


def _generate_booking_reference() -> str:
    return f"ATD-{token_hex(4).upper()}"


def _parse_starts_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _serialize_booking(booking: Booking) -> dict[str, object]:
    return {
        "id": str(booking.id),
        "thread_id": str(booking.thread_id) if booking.thread_id else None,
        "booking_reference": booking.booking_reference,
        "event_type": booking.event_type,
        "status": booking.status,
        "event_title": booking.event_title,
        "city": booking.city,
        "venue_name": booking.venue_name,
        "starts_at": booking.starts_at.isoformat(),
        "confirmed_at": booking.confirmed_at.isoformat(),
        "filter_snapshot": booking.filter_snapshot,
        "event_snapshot": booking.event_snapshot,
    }
