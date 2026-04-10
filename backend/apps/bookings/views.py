import json
from json import JSONDecodeError

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from apps.bookings.models import Booking
from apps.bookings.services import BookingFlowError, create_booking_from_listing, serialize_booking
from apps.chats.models import ChatThread, ThreadFilter


def booking_list_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    bookings = [serialize_booking(booking) for booking in Booking.objects.all()]
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
    try:
        booking, already_confirmed = create_booking_from_listing(
            thread=thread,
            thread_filter=thread_filter,
            listing_code=listing_code,
            confirmed_via="chat_button",
        )
    except BookingFlowError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status_code)

    return JsonResponse(
        {"booking": serialize_booking(booking), "already_confirmed": already_confirmed},
        status=200 if already_confirmed else 201,
    )
