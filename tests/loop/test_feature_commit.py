from __future__ import annotations

from engineeringagent.feature_commit import feature_completion_commit_subject


def test_feature_completion_commit_subject_prefers_expected_subject() -> None:
    subject = feature_completion_commit_subject(
        {
            "id": "FEAT-174",
            "title": "Retire overly rigid fitness rules",
            "type": "chore",
            "expected_commit_subject": "chore: retire rigid fitness rules",
        }
    )

    assert subject == "chore: retire rigid fitness rules"


def test_feature_completion_commit_subject_includes_title_with_default_prefix() -> None:
    subject = feature_completion_commit_subject(
        {
            "id": "FEAT-174",
            "title": "Retire overly rigid fitness rules",
            "type": "unknown-type",
        }
    )

    assert subject == "feat: complete FEAT-174 - Retire overly rigid fitness rules"
