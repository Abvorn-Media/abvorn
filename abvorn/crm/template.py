"""Email HTML templates — beautiful, consistent, responsive."""

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
                 tracking_consent: bool = False) -> str:
    """Render a complete HTML email with all optional blocks."""
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