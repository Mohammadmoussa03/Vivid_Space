"""Project middleware."""
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """Attach a Content-Security-Policy header to every response.

    Defense-in-depth against XSS/content injection. The policy string lives in
    settings.CONTENT_SECURITY_POLICY so it can be tuned per-environment.
    """

    def process_response(self, request, response):
        policy = getattr(settings, 'CONTENT_SECURITY_POLICY', '')
        if policy and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = policy
        return response
