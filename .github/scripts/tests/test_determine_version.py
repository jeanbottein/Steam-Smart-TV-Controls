import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from determine_version import apply_bump, classify_commit, plan_release, strongest_bump


def test_feature_commit_bumps_minor():
    assert classify_commit("feat: add brand dropdown", "") == "minor"


def test_fix_commit_bumps_patch():
    assert classify_commit("fix: retry on timeout", "") == "patch"


def test_chore_commit_bumps_patch():
    assert classify_commit("chore: tidy imports", "") == "patch"


def test_scoped_breaking_marker_bumps_major():
    assert classify_commit("feat(store)!: drop legacy format", "") == "major"


def test_breaking_change_in_body_bumps_major():
    assert classify_commit("feat: new store", "BREAKING CHANGE: format changed") == "major"


def test_docs_commit_is_skipped():
    assert classify_commit("docs: update readme", "") is None


def test_ci_commit_is_skipped():
    assert classify_commit("ci: cache pnpm", "") is None


def test_non_conventional_commit_is_skipped():
    assert classify_commit("Merge branch main", "") is None


def test_strongest_bump_prefers_major():
    assert strongest_bump(["patch", "major", "minor"]) == "major"


def test_strongest_bump_of_empty_is_none():
    assert strongest_bump([]) is None


def test_apply_major_resets_lower_parts():
    assert apply_bump((1, 4, 2), "major") == (2, 0, 0)


def test_apply_minor_resets_patch():
    assert apply_bump((1, 4, 2), "minor") == (1, 5, 0)


def test_apply_patch_increments():
    assert apply_bump((1, 4, 2), "patch") == (1, 4, 3)


def test_plan_release_without_releasable_commits():
    version, should_release, changelog = plan_release((1, 2, 3), [("docs: x", "")])
    assert (version, should_release, changelog) == ("1.2.3", False, "")


def test_plan_release_picks_highest_bump_and_lists_changes():
    commits = [("fix: a", ""), ("feat: b", "")]
    version, should_release, changelog = plan_release((1, 2, 3), commits)
    assert version == "1.3.0"
    assert should_release is True
    assert changelog == "- fix: a\n- feat: b"
