"""Redirect HTML generator — meta refresh for GitHub Pages path migrations."""


def generate_redirect_html(target_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0; url={target_url}">
<link rel="canonical" href="{target_url}">
</head>
<body>
<p>Redirecting to <a href="{target_url}">{target_url}</a>...</p>
</body>
</html>"""
