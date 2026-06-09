from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class BlockedUserMiddleware:
    """
    On every request, checks if the authenticated user has been blocked
    by an admin.  If so, logs them out immediately and redirects to the
    login page with an error message.

    Placement: must come AFTER AuthenticationMiddleware so request.user
    is already populated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                is_blocked = (
                    request.user.__class__.objects
                    .filter(pk=request.user.pk)
                    .values_list("is_blocked", flat=True)
                    .first()
                )
            except Exception:
                is_blocked = False

            if is_blocked:
                # Log the user out (clears their session)
                logout(request)
                # Add error message AFTER logout so it goes into the new session
                messages.error(
                    request,
                    "Your account has been blocked by the administrator. "
                    "Please contact support for assistance."
                )
                return redirect(reverse("login"))

        return self.get_response(request)

