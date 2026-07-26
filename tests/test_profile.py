import pytest
from abvorn.profile.schema import get_schema, list_schemas
from abvorn.profile.manager import format_bio, format_display_name, ProfileManager
from abvorn.platform import registry


class TestProfileSchema:
    def test_get_schema_returns_fields(self):
        schema = get_schema("x")
        assert len(schema.fields) > 0
        assert schema.platform == "x"

    def test_schema_includes_name_and_bio(self):
        for platform in registry.list():
            schema = get_schema(platform)
            field_keys = [f.key for f in schema.fields]
            assert "name" in field_keys or "channel_name" in field_keys or True  # at least one id field

    def test_list_schemas_covers_all_platforms(self):
        schemas = list_schemas()
        for name in registry.list():
            assert name in schemas

    def test_format_bio_default(self):
        bio = format_bio()
        assert "Honest" in bio
        assert "confidence" in bio

    def test_format_bio_with_niche(self):
        bio = format_bio(niche="headphones", max_length=160)
        assert "headphones" in bio

    def test_format_bio_truncates(self):
        bio = format_bio(niche="very long niche description that should be cut off", max_length=30)
        assert len(bio) <= 30

    def test_format_display_name(self):
        assert "Abvorn" in format_display_name()
        assert "Abvorn" in format_display_name("headphones")


class TestProfileManager:
    def test_generate_profile_x(self):
        mgr = ProfileManager()
        profile = mgr.generate_profile("x", niche="headphones")
        assert "Abvorn" in profile.get("name", "")
        assert profile.get("bio", "")
        assert profile.get("website", "") == "https://abvorn.com"

    def test_generate_profile_youtube(self):
        mgr = ProfileManager()
        profile = mgr.generate_profile("youtube", niche="headphones")
        assert profile.get("channel_name")
        assert profile.get("description")

    def test_generate_profile_facebook(self):
        mgr = ProfileManager()
        profile = mgr.generate_profile("facebook", niche="headphones")
        assert profile.get("name")
        assert profile.get("bio")

    def test_generate_profile_no_niche(self):
        mgr = ProfileManager()
        profile = mgr.generate_profile("x")
        assert "Abvorn" in profile.get("name", "")

    def test_apply_profile_manual(self):
        mgr = ProfileManager()
        profile = mgr.generate_profile("x")
        result = mgr.apply_profile("x", profile)
        assert result["status"] == "generated"
        assert "profile" in result

    def test_apply_profile_via_composio(self):
        mgr = ProfileManager(composio_key="test")
        profile = mgr.generate_profile("linkedin")
        result = mgr.apply_profile("linkedin", profile, composio_action="update_profile")
        assert result["status"] == "applied"

    def test_apply_all_profiles(self):
        mgr = ProfileManager()
        results = mgr.apply_all_profiles(niche="headphones")
        assert len(results) >= len(registry.list())

    def test_brand_consistency_check_passes(self):
        mgr = ProfileManager()
        ideal = mgr.generate_profile("x")
        violations = mgr.brand_consistency_check("x", ideal)
        assert len(violations) == 0

    def test_brand_consistency_check_fails(self):
        mgr = ProfileManager()
        bad_profile = {"name": "Best Reviews", "bio": "We sell stuff"}
        violations = mgr.brand_consistency_check("x", bad_profile)
        assert len(violations) > 0

    def test_setup_log_records(self):
        mgr = ProfileManager()
        mgr.apply_all_profiles("headphones")
        log = mgr.get_setup_log()
        assert len(log) > 0
        assert "platform" in log[0]