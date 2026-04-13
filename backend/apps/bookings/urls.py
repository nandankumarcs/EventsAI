from django.urls import path

from apps.bookings.views import booking_confirm_view, booking_delete_view, booking_list_view

app_name = "bookings"

urlpatterns = [
    path("", booking_list_view, name="booking-list"),
    path("<uuid:booking_id>/", booking_delete_view, name="booking-delete"),
    path("confirm/", booking_confirm_view, name="booking-confirm"),
]
