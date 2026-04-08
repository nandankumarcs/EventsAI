from django.urls import path

from apps.bookings.views import booking_confirm_view, booking_list_view

app_name = "bookings"

urlpatterns = [
    path("", booking_list_view, name="booking-list"),
    path("confirm/", booking_confirm_view, name="booking-confirm"),
]
