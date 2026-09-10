import shutil
import tempfile
from pathlib import Path

import pytest

from abvorn.domination.self_learning_engine import SelfLearningEngine


@pytest.fixture
def learn_db(tmp_path):
    yield str(tmp_path / "learn.db")
    for p in sorted(tmp_path.glob("*"), reverse=True):
        try:
            p.unlink()
        except OSError:
            pass


def test_posted_urls_empty_on_fresh_db(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    assert sle.posted_urls() == set()


def test_post_urls_roundtrip_via_record(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
    )
    assert sle.posted_urls() == {"https://abvorn.com/reviews/laptops/"}
    # duplicate insert must not duplicate the returned set
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
    )
    assert sle.posted_urls() == {"https://abvorn.com/reviews/laptops/"}