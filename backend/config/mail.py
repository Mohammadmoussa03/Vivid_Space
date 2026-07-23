"""Branded transactional email.

Every message the app sends goes through `send_branded_mail`. It keeps the
existing plain-text body verbatim — that's still what text-only clients and
most notification pipelines read — and adds an HTML alternative carrying the
Vivid Space logo and the site's palette.

Two decisions worth knowing:

* **The logo is attached inline (Content-ID), not hotlinked.** Gmail, Outlook
  and Apple Mail all block remote images by default, which would leave a broken
  placeholder at the top of every email for most recipients. A 14 KB inline PNG
  always renders. The bytes are read once and cached for the process.
* **Sends stay best-effort.** Callers rely on a mail failure never breaking the
  request that triggered it, so `fail_silently` defaults to True here exactly as
  it did when every call site used `send_mail` directly.
"""
import re
from functools import lru_cache
from html import escape
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

LOGO_PATH = Path(settings.BASE_DIR) / 'static' / 'email' / 'vivid-logo.png'
LOGO_CID = 'vividspace-logo'

# Mirrors frontend/src/lib/ms.js — keep in step if the site palette changes.
INK = '#1A1A1A'
MUTED = '#6B6560'
FAINT = '#8A857E'
LINE = '#E5E3E6'
PAGE_BG = '#F5F1ED'
CARD_BG = '#FFFFFF'
ACCENT = '#9B7EBD'

_URL_RE = re.compile(r'(https?://[^\s<>"\']+)')


@lru_cache(maxsize=1)
def _logo_bytes():
    """The inline logo, read once per process. None if the asset is missing."""
    try:
        return LOGO_PATH.read_bytes()
    except OSError:
        # A missing asset must degrade to a logo-less email, never a 500 in the
        # request that triggered the send.
        return None


def _linkify(text):
    """Escape for HTML, then turn bare URLs into anchors.

    Bodies are written as plain text and contain raw reset/confirmation links;
    without this they'd render as unclickable text in the HTML part.
    """
    out = []
    last = 0
    for match in _URL_RE.finditer(text):
        out.append(escape(text[last:match.start()]))
        url = match.group(1)
        # Trailing sentence punctuation isn't part of the link.
        trailing = ''
        while url and url[-1] in '.,;:)':
            trailing = url[-1] + trailing
            url = url[:-1]
        safe = escape(url, quote=True)
        out.append(
            f'<a href="{safe}" style="color:{ACCENT};text-decoration:underline;'
            f'word-break:break-all;">{safe}</a>{escape(trailing)}'
        )
        last = match.end()
    out.append(escape(text[last:]))
    return ''.join(out)


def _body_html(body):
    """Plain-text body -> paragraphs, preserving line breaks and alignment.

    `white-space:pre-wrap` (rather than converting newlines to <br />) keeps the
    space-aligned detail blocks the booking emails are written with — "Date:
    Monday" lines up under "Space:" instead of collapsing to a single space —
    while still wrapping long lines on narrow screens.
    """
    blocks = [b for b in re.split(r'\n\s*\n', body.strip()) if b.strip()]
    return '\n'.join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{INK};'
        f'white-space:pre-wrap;">{_linkify(block)}</p>'
        for block in blocks
    )


def render_email_html(body, logo=True):
    """Wrap a plain-text body in the branded HTML shell.

    Table-based and inline-styled on purpose: Outlook ignores most modern CSS,
    and <style> blocks are stripped by several webmail clients.
    """
    header = ''
    if logo and _logo_bytes():
        header = (
            f'<tr><td align="center" style="padding:32px 32px 8px;">'
            f'<img src="cid:{LOGO_CID}" alt="Vivid Space" width="160" '
            f'style="display:block;border:0;width:160px;max-width:60%;height:auto;" />'
            f'</td></tr>'
        )

    return f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="color-scheme" content="light only" />
</head>
<body style="margin:0;padding:0;background:{PAGE_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{PAGE_BG};padding:24px 12px;">
  <tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0"
           style="width:560px;max-width:100%;background:{CARD_BG};border:1px solid {LINE};
                  border-radius:16px;overflow:hidden;
                  font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      {header}
      <tr><td style="padding:16px 32px 28px;">
        {_body_html(body)}
      </td></tr>
      <tr><td style="padding:0 32px 28px;">
        <div style="border-top:1px solid {LINE};padding-top:16px;
                    font-size:12.5px;line-height:1.5;color:{FAINT};">
          Vivid Space &middot; Coworking &amp; Private Offices<br />
          This is an automated message — replies to it aren't monitored.
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def send_branded_mail(subject, body, recipients, from_email=None, fail_silently=True):
    """Send `body` as plain text plus a branded HTML alternative.

    `recipients` may be a single address or an iterable. Returns the number of
    messages sent (0 when there's no recipient, or when a send failed while
    `fail_silently` is on).
    """
    if not recipients:
        return 0
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        return 0

    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=list(recipients),
    )
    message.attach_alternative(render_email_html(body), 'text/html')

    logo = _logo_bytes()
    if logo:
        # Inline disposition + Content-ID so the image renders in the body
        # rather than showing up as a downloadable attachment.
        from email.mime.image import MIMEImage

        image = MIMEImage(logo, 'png')
        image.add_header('Content-ID', f'<{LOGO_CID}>')
        image.add_header('Content-Disposition', 'inline', filename='vivid-logo.png')
        message.attach(image)
        message.mixed_subtype = 'related'

    try:
        return message.send(fail_silently=fail_silently)
    except Exception:
        # Mirrors the old belt-and-braces behaviour: fail_silently covers SMTP
        # errors, this covers everything else (bad address, encoding, …).
        if not fail_silently:
            raise
        return 0
