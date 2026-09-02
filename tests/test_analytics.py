import sys, types
import pytest
from abvorn.deploy.analytics import compute_ga4_score

def test_compute_score():
    """Score should weight users more than views, duration as bonus."""
    score = compute_ga4_score(views=100, users=20, avg_duration=30.0)
    assert score > 100  # 100 + 40 + 3 = 143
    assert score < 200


class _Row:
    def __init__(self, path, views, users, duration):
        self.dimension_values = [type("D", (), {"value": path})()]
        self.metric_values = [
            type("M", (), {"value": str(views)})(),
            type("M", (), {"value": str(users)})(),
            type("M", (), {"value": str(duration)})(),
        ]


def _fake_google_modules(fake_client_cls):
    """Build fake google.* modules that mirror abvorn.deploy.analytics' imports."""
    data_module = types.ModuleType("google.analytics.data_v1beta")
    data_module.BetaAnalyticsDataClient = fake_client_cls
    for name in ("RunReportRequest", "Metric", "DateRange", "Dimension"):
        setattr(data_module, name, type(name, (), {"__init__": lambda self, **kw: None}))
    oauth2_module = types.ModuleType("google.oauth2")
    oauth2_module.service_account = types.SimpleNamespace(
        Credentials=type("Credentials", (), {"from_service_account_info": staticmethod(lambda info: "creds")})
    )
    return {
        "google.analytics.data_v1beta": data_module,
        "google.oauth2": oauth2_module,
    }


@pytest.mark.parametrize("path,expected", [
    ("/abvorn/wireless-earbuds/best-wireless-earbuds-2026.html", "wireless-earbuds"),
    ("/abvorn/webcams/index.html", "webcams"),
    ("/wireless-headphones/best-wireless-headphones.html", "wireless-headphones"),
    ("/abvorn/compare.html", None),
    ("/abvorn/about.html", None),
    ("/abvorn/privacy/index.html", None),
])
def test_pull_ga4_slug_strips_base_path(path, expected, monkeypatch):
    """Slugs must drop the site base path and skip non-niche pages."""
    from abvorn.deploy import analytics as deploy_analytics

    class FakeClient:
        def __init__(self, credentials=None):
            pass
        def run_report(self, request):
            return type("R", (), {"rows": [_Row(path, 5, 1, 10.0)]})()

    for mod_name, mod in _fake_google_modules(FakeClient).items():
        monkeypatch.setitem(sys.modules, mod_name, mod)

    secrets = {"GA4_PROPERTY_ID": "546938118",
               "GA4_CREDENTIALS_JSON": '{"type":"service_account","client_email":"x@x.iam.gserviceaccount.com"}',
               "SITE_URL": "https://Abvorn-Media.github.io/abvorn"}
    result = deploy_analytics.pull_ga4_analytics(secrets)
    if expected is None:
        assert result == {}
    else:
        assert expected in result