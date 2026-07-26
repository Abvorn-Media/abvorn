"""Tests for UIX — moderation, components, engagement tracking."""

import pytest, tempfile, json
from pathlib import Path
from abvorn.uix.moderation import CommentModerator
from abvorn.uix.components import UIXComponents, UIX_SCRIPT_JS


class TestCommentModerator:
    def test_clean_comment_approved(self):
        m = CommentModerator()
        result = m.moderate("Alice", "Great review! Thanks for the recommendation.")
        assert result["approved"]
        assert result["status"] == "approved"
        assert len(result["flags"]) == 0

    def test_profanity_detected(self):
        m = CommentModerator()
        result = m.moderate("Bob", "This product is shit")
        assert not result["approved"]
        assert "profanity" in str(result["flags"][0])
        assert result["status"] == "pending"

    def test_link_blocked(self):
        m = CommentModerator(block_links=True)
        result = m.moderate("Spammer", "Check this out https://spam.com/buy")
        assert not result["approved"]
        assert "links_blocked" in result["flags"]
        assert "[link removed]" in result["filtered_body"]

    def test_multiple_links_flagged(self):
        m = CommentModerator()
        result = m.moderate("Spammer", "Good post https://a.com and https://b.com")
        assert "multiple_links" in result["flags"]

    def test_too_short_rejected(self):
        m = CommentModerator(min_length=5)
        result = m.moderate("A", "Hi")
        assert result["status"] == "rejected"
        assert "too_short" in result["flags"]

    def test_too_long_rejected(self):
        m = CommentModerator(max_length=10)
        result = m.moderate("User", "This is way too long for the max length")
        assert result["status"] == "rejected"
        assert "too_long" in result["flags"]

    def test_excessive_caps_flagged(self):
        m = CommentModerator()
        result = m.moderate("User", "THIS IS AN AMAZING PRODUCT AND EVERYONE SHOULD BUY IT RIGHT NOW")
        assert "excessive_caps" in result["flags"]

    def test_sanitize_strips_profanity(self):
        m = CommentModerator()
        cleaned = m.sanitize("This is shit really")
        assert "shit" not in cleaned
        assert "[redacted]" in cleaned

    def test_sanitize_strips_links(self):
        m = CommentModerator(block_links=True)
        cleaned = m.sanitize("Visit https://spam.com now")
        assert "https://spam.com" not in cleaned
        assert "[link removed]" in cleaned

    def test_profanity_and_link_combined(self):
        m = CommentModerator()
        result = m.moderate("Troll", "This fucking site https://bad.com sucks")
        assert not result["approved"]
        assert any("profanity" in f for f in result["flags"])
        assert any("links" in f for f in result["flags"])


class TestUIXComponents:
    def test_social_proof_empty(self):
        html = UIXComponents.social_proof()
        assert "Be the first to react" in html

    def test_social_proof_with_counts(self):
        html = UIXComponents.social_proof(likes=5, shares=3, comments=2, readers=10)
        assert "5" in html
        assert "3" in html
        assert "10" in html

    def test_reactions_bar_has_buttons(self):
        html = UIXComponents.reactions_bar(post_id=42, like_count=3, love_count=1)
        assert 'data-post-id="42"' in html
        assert "Like" in html
        assert "Love" in html
        assert "3" in html
        assert "1" in html

    def test_reactions_bar_liked_state(self):
        html = UIXComponents.reactions_bar(post_id=1, liked=True, like_count=5)
        assert "active" in html

    def test_reactions_bar_loved_state(self):
        html = UIXComponents.reactions_bar(post_id=1, loved=True, love_count=2)
        assert "loved" in html

    def test_share_buttons_include_x(self):
        html = UIXComponents.reactions_bar(post_id=7, like_count=0, love_count=0)
        assert "share-x" in html
        assert "share-linkedin" in html
        assert "share-facebook" in html
        assert "share-copy" in html

    def test_comment_section_empty(self):
        html = UIXComponents.comment_section(post_id=1)
        assert "No comments yet" in html
        assert "uix-comment-form" in html

    def test_comment_section_with_comments(self):
        comments = [
            {"author": "Alice", "body": "Great post!", "created_at": "2026-01-15T10:00:00"},
            {"author": "Bob", "body": "Thanks for sharing", "created_at": "2026-01-16T12:00:00"},
        ]
        html = UIXComponents.comment_section(post_id=1, comments=comments)
        assert "Alice" in html
        assert "Bob" in html
        assert "(2)" in html

    def test_full_engagement_block(self):
        engagement = {
            "likes": {"like": 3, "love": 1, "total": 4},
            "shares": {"total": 2, "platforms": []},
            "comments": {"count": 1, "recent": [{"author": "C", "body": "Nice", "created_at": "2026-01-01"}]}
        }
        html = UIXComponents.full_engagement_block(post_id=10, engagement=engagement)
        assert "4" in html
        assert "C" in html
        assert "uix-reactions" in html
        assert "uix-comments" in html

    def test_script_js_contains_core_functions(self):
        assert "uixReact" in UIX_SCRIPT_JS
        assert "uixTrackShare" in UIX_SCRIPT_JS
        assert "uixCopyLink" in UIX_SCRIPT_JS
        assert "uixSubmitComment" in UIX_SCRIPT_JS


class TestEngagementState:
    def test_add_like(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        posts = state.get_posts_for_niche("test")
        pid = posts[0]["id"]
        state.add_like(pid, "hash1", "like")
        likes = state.get_likes(pid)
        assert likes["like"] == 1
        assert likes["total"] == 1

    def test_dedup_like(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_like(pid, "hash1", "like")
        state.add_like(pid, "hash1", "like")
        likes = state.get_likes(pid)
        assert likes["total"] == 1

    def test_multiple_reactions(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_like(pid, "a", "like")
        state.add_like(pid, "b", "love")
        likes = state.get_likes(pid)
        assert likes["like"] == 1
        assert likes["love"] == 1
        assert likes["total"] == 2

    def test_remove_like(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_like(pid, "hash1", "like")
        state.remove_like(pid, "hash1")
        assert state.get_likes(pid)["total"] == 0

    def test_has_liked(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_like(pid, "hash1", "love")
        assert state.has_liked(pid, "hash1")
        assert not state.has_liked(pid, "nobody")

    def test_track_share(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.track_share(pid, "x")
        assert state.get_total_shares(pid) == 1

    def test_track_share_increment(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.track_share(pid, "x")
        state.track_share(pid, "x")
        assert state.get_total_shares(pid) == 2

    def test_add_comment(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_comment(pid, "Alice", "Great review!", "approved")
        comments = state.get_comments(pid)
        assert len(comments) == 1
        assert comments[0]["author"] == "Alice"

    def test_moderate_comment(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_comment(pid, "Alice", "Great!", "pending")
        comments = state.get_comments(pid, "pending")
        assert len(comments) == 1
        state.moderate_comment(comments[0]["id"], "approved")
        assert len(state.get_comments(pid, "approved")) == 1

    def test_engagement_summary(self, tmp_path):
        from abvorn.core.state import AbvornState
        db = tmp_path / "test.db"
        state = AbvornState(db)
        state.add_post("test", "Post", "post.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        state.add_like(pid, "a", "like")
        state.add_like(pid, "b", "love")
        state.track_share(pid, "x")
        state.add_comment(pid, "User", "Nice!", "approved")
        summary = state.get_engagement_summary(pid)
        assert summary["likes"]["total"] == 2
        assert summary["shares"]["total"] == 1
        assert summary["comments"]["count"] == 1