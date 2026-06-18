"""CSRF failure handling."""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.csrf import csrf_failure as default_csrf_failure


def csrf_failure(request, reason=''):
    """Send login users back to a fresh sign-in page instead of a raw 403."""
    path = (request.path or '').rstrip('/') or '/'
    if path == '/login':
        messages.warning(
            request,
            'Your sign-in session expired. Please try again.',
        )
        next_url = request.GET.get('next', '').strip()
        login_url = reverse('login')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(f'{login_url}?next={next_url}')
        return redirect(login_url)
    return default_csrf_failure(request, reason=reason)
