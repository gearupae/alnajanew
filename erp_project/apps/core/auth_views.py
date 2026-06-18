from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.contrib.auth.views import LoginView


@method_decorator(never_cache, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class ERPLoginView(LoginView):
    """Clear stale flash messages from prior requests when login succeeds."""

    template_name = 'auth/login.html'

    def form_valid(self, form):
        # Discard old errors (e.g. failed PDF download, permission denied) so they
        # do not appear on the dashboard after login.
        list(messages.get_messages(self.request))
        return super().form_valid(form)
