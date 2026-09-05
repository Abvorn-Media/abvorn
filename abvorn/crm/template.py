"""Email HTML templates — beautiful, consistent, responsive."""

from urllib.parse import quote

from src.humanizer_engine import HumanizerEngine

_humanizer = HumanizerEngine()

_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{subject}</title>
<style type="text/css">
@media only screen and (max-width:600px){{table[class=container]{{width:100%!important}}td[class=content]{{padding:20px 16px!important;font-size:15px!important}}td[class=header]{{padding:16px 20px!important}}td[class=footer]{{padding:16px 20px!important}}td[class=cta]{{padding:10px 20px!important;display:block!important;text-align:center!important}}a[class=cta-link]{{display:block!important;text-align:center!important;font-size:16px!important;padding:14px 20px!important}}h1[class=greeting]{{font-size:20px!important}}h2[class=email-title]{{font-size:18px!important}}p[class=email-body]{{font-size:15px!important}}}}
</style>
</head>
<body style="margin:0;padding:0;background-color:#f0ebe3;font-family:'Helvetica Neue',Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0ebe3">
<tr><td align="center" style="padding:30px 16px">
<table role="presentation" width="600" class="container" cellpadding="0" cellspacing="0" style="background-color:#faf6f1;border-radius:12px;overflow:hidden;max-width:100%">

<!-- Header -->
<tr><td class="header" style="background-color:#d4633e;padding:24px 32px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.5px;font-family:Georgia,'Times New Roman',serif">Abvorn</td>
<td style="color:rgba(255,255,255,.7);font-size:12px;text-align:right">Honest Reviews</td>
</tr>
</table>
</td></tr>

<!-- Content -->
<tr><td class="content" style="padding:32px">
<h1 class="greeting" style="margin:0 0 8px;font-size:24px;color:#2a2724;font-weight:700">Hi {to_name},</h1>
{body_html}
{cta_block}
{lead_magnet_block}
</td></tr>

<!-- Footer -->
<tr><td class="footer" style="background-color:#faf6f1;padding:24px 32px;border-top:1px solid #e3dbd4">
<p style="margin:0 0 8px;font-size:12px;color:#9e9690;line-height:1.5">
As an Amazon Associate we earn from qualifying purchases.
</p>
<p style="margin:0 0 8px;font-size:12px;color:#9e9690">
You received this because you subscribed to {niche} updates.
</p>
<p style="margin:0;font-size:12px;color:#9e9690">
<a href="{unsubscribe_url}" style="color:#d4633e;text-decoration:underline">Unsubscribe</a>
</p>
{tracking_pixel_html}
</td></tr>

</table>
</td></tr></table>
</body>
</html>"""


def render_email(to_name: str, subject: str, body_html: str,
                 cta_text: str = "", cta_url: str = "",
                 magnet_title: str = "", magnet_url: str = "",
                 niche: str = "products",
                 unsubscribe_url: str = "#",
                 tracking_pixel: str = "",
                 tracking_consent: bool = False,
                 humanize: bool = True) -> str:
    """Render a complete HTML email with all optional blocks.

    humanize=False is for callers that supply final HTML bodies containing
    raw URLs/links: the humanizer's text-rewrite rules operate on plain text
    and can split markup (e.g. "https://abvorn.com/..." becoming
    "https://abvorn." + "com/...").
    """
    cta_block = ""
    if cta_text and cta_url:
        cta_block = f'''
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0">
<tr>
<td class="cta" style="background-color:#d4633e;border-radius:8px;padding:12px 28px;text-align:center">
<a class="cta-link" href="{cta_url}" style="color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;display:inline-block">{cta_text} &rarr;</a>
</td>
</tr>
</table>'''

    lead_magnet_block = ""
    if magnet_title and magnet_url:
        lead_magnet_block = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f7f7;border-radius:6px;margin:20px 0;padding:16px">
<tr><td>
<p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Free Guide</p>
<p style="margin:0 0 12px;font-size:16px;color:#1a1a1a;font-weight:600">{magnet_title}</p>
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background-color:#d4633e;border-radius:6px;padding:8px 20px">
<a href="{magnet_url}" style="color:#ffffff;font-size:13px;font-weight:600;text-decoration:none">Download Your Free Copy</a>
</td>
</tr>
</table>
</td></tr></table>'''

    if humanize:
        subject = _humanizer.humanize_email_subject(subject)
        body_html = _humanizer.humanize_email_body(body_html)

    return _EMAIL_TEMPLATE.format(
        subject=subject, to_name=to_name,
        body_html=body_html, cta_block=cta_block,
        lead_magnet_block=lead_magnet_block,
        niche=niche, unsubscribe_url=unsubscribe_url,
        tracking_pixel=(tracking_pixel if tracking_consent else "") or "",
        tracking_pixel_html=f'<img src="{tracking_pixel}" width="1" height="1" alt="" style="display:none">' if tracking_consent and tracking_pixel else "",
    )


def render_lead_magnet_email(to_name: str, magnet_title: str,
                               magnet_url: str = "#",
                               niche: str = "products",
                               tracking_consent: bool = False) -> str:
    """Render a lead magnet delivery email."""
    body = f"<p style=\"margin:0 0 16px;font-size:16px;color:#333;line-height:1.6\">Thanks for your interest in {niche}. Here's your free guide to help you make the right choice.</p>"
    return render_email(
        to_name=to_name,
        subject=f"Your {niche} guide is here",
        body_html=body,
        magnet_title=magnet_title,
        magnet_url=magnet_url,
        niche=niche,
        tracking_consent=tracking_consent,
    )


def render_pdf_guide_email(to_name: str, guide_title: str,
                           pdf_url: str, niche: str = "products",
                           guide_url: str = "",
                           tracking_consent: bool = False) -> str:
    """Render a 'your PDF guide is ready' delivery email."""
    live_line = ""
    if guide_url:
        live_line = (f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
                     f'Prefer the live version? <a href="{guide_url}" style="color:#d4633e">'
                     f'Read the full guide online</a> instead.</p>')
    body = (f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
            f'Your copy of <strong>{guide_title}</strong> is ready. Every score, price, '
            f'and verdict from the guide, in one clean downloadable document.</p>'
            f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
            f'No sign-up walls and no paywall — just the guide, so you can read it at '
            f'your own pace.</p>{live_line}')
    return render_email(
        to_name=to_name,
        subject=f"Your guide is ready: {guide_title[:50]}",
        body_html=body,
        cta_text="Download Your Guide (PDF)",
        cta_url=pdf_url,
        niche=niche,
        tracking_consent=tracking_consent,
    )


def render_persona_update(to_name: str, persona_name: str,
                           post_title: str, post_url: str,
                           niche: str = "products",
                           tracking_consent: bool = False) -> str:
    """Render a persona-targeted content update email."""
    body = f"""<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">We found something we think you'll love — a new guide written specifically for someone like you.</p>
<p style="margin:0 0 4px;font-size:13px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Just for you, {persona_name}</p>
<h2 style="margin:0 0 12px;font-size:20px;color:#1a1a1a;font-weight:700">{post_title}</h2>"""
    return render_email(
        to_name=to_name,
        subject=f"New: {post_title[:50]}",
        body_html=body,
        cta_text="Read the Full Guide",
        cta_url=post_url,
        niche=niche,
        tracking_consent=tracking_consent,
    )


def _unsubscribe_url(email: str, apps_script_url: str = "") -> str:
    """Real one-click unsubscribe against the live Apps Script web-app URL.

    Matches the endpoint deployed in abvorn/reactions_merged_Code.gs
    (action=unsubscribe). Falls back to "#" when the URL is unknown, which
    mirrors the previous no-op default.
    """
    if not apps_script_url or apps_script_url == "#":
        return "#"
    sep = "&" if "?" in apps_script_url else "?"
    return f"{apps_script_url}{sep}action=unsubscribe&email={quote(email)}"


def render_niche_welcome_email(to_name: str, niche_name: str, niche_slug: str,
                               email: str, apps_script_url: str = "",
                               tracking_consent: bool = False) -> str:
    """Render the niche-subscription welcome (mirror of the Apps Script version).

    A reader who used the "Get updates for this niche" card gets a welcome that
    names their niche and promises exactly one email per new guide in it.
    """
    browse_url = ("https://abvorn.com/" if niche_slug == "general"
                  else f"https://abvorn.com/reviews/{niche_slug}/")
    body = (
        f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
        f'You are now subscribed to <strong>{niche_name} updates</strong>. One email whenever we publish a new '
        f'{niche_name} guide — no spam, unsubscribe anytime.</p>'
        f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
        f'In the meantime, here is the latest on {niche_name.lower()}:</p>'
    )
    return render_email(
        to_name=to_name,
        subject=f"You are subscribed to {niche_name} updates",
        body_html=body,
        cta_text=f"Browse {niche_name} reviews",
        cta_url=browse_url,
        niche=niche_name,
        unsubscribe_url=_unsubscribe_url(email, apps_script_url),
        tracking_consent=tracking_consent,
        humanize=False,
    )


def render_new_post_digest(to_name: str, niche_name: str, niche_slug: str,
                           email: str, items: list, apps_script_url: str = "",
                           tracking_consent: bool = False) -> str:
    """Render the new-post digest (mirror of the Apps Script broadcast version).

    items: list of {"title": str, "link": str} for the niche's new guides.
    A single item produces a one-title subject; multiple produce a count.
    """
    titles = [it["title"] for it in items]
    if len(titles) == 1:
        subject = f"New on Abvorn: {titles[0]}"
    else:
        subject = f"New on Abvorn ({niche_name}): {len(titles)} new guides"
    list_html = "".join(
        f'<p style="margin:0 0 14px;font-size:16px;color:#333;line-height:1.5">'
        f'<a href="{it["link"]}" style="color:#d4633e;font-weight:600;text-decoration:none">{it["title"]}</a></p>'
        for it in items
    )
    browse_url = ("https://abvorn.com/" if niche_slug == "general"
                  else f"https://abvorn.com/reviews/{niche_slug}/")
    body = (
        f'<p style="margin:0 0 16px;font-size:16px;color:#333;line-height:1.6">'
        f'New {niche_name.lower()} guides just went live on Abvorn, scored and priced fresh:</p>{list_html}'
    )
    return render_email(
        to_name=to_name,
        subject=subject,
        body_html=body,
        cta_text=f"Browse all {niche_name} reviews",
        cta_url=browse_url,
        niche=niche_name,
        unsubscribe_url=_unsubscribe_url(email, apps_script_url),
        tracking_consent=tracking_consent,
        humanize=False,
    )