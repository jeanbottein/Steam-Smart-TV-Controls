#!/usr/bin/env python3
"""Compute the next semantic version from conventional commits since the latest tag."""

import os
import re
import subprocess

CONVENTIONAL_COMMIT = re.compile(r"^(\w+)(?:\([^)]*\))?(!)?:\s+.+")
SKIPPED_TYPES = {"ci", "doc", "docs"}
PATCH_TYPES = {"chore", "fix"}
BUMP_PRECEDENCE = {"major": 3, "minor": 2, "patch": 1}


def classify_commit(subject, body):
    match = CONVENTIONAL_COMMIT.match(subject)
    if match is None:
        return None
    commit_type, breaking = match.group(1), match.group(2)
    if commit_type in SKIPPED_TYPES:
        return None
    if breaking or "BREAKING CHANGE:" in body:
        return "major"
    if commit_type in PATCH_TYPES:
        return "patch"
    return "minor"


def strongest_bump(bumps):
    return max(bumps, key=BUMP_PRECEDENCE.get, default=None)


def apply_bump(version, bump):
    major, minor, patch = version
    if bump == "major":
        return (major + 1, 0, 0)
    if bump == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def format_version(version):
    return ".".join(map(str, version))


def parse_version_tag(tag):
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", tag)
    return tuple(map(int, match.groups())) if match else None


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout.strip()


def latest_version():
    refs = _run("git", "ls-remote", "--tags", "origin").splitlines()
    names = (line.split("refs/tags/")[-1] for line in refs if "refs/tags/" in line and not line.endswith("^{}"))
    versions = [version for version in map(parse_version_tag, names) if version]
    return max(versions, default=(0, 0, 0))


def commits_since(version):
    scope = "HEAD" if version == (0, 0, 0) else f"v{format_version(version)}..HEAD"
    raw = _run("git", "log", scope, "--format=%s%x1f%b%x1e")
    blocks = (block.strip("\n") for block in raw.split("\x1e") if block.strip())
    return [block.partition("\x1f")[::2] for block in blocks]


def plan_release(version, commits):
    classified = [(subject, classify_commit(subject, body)) for subject, body in commits]
    releasable = [subject for subject, bump in classified if bump]
    bump = strongest_bump([bump for _, bump in classified if bump])
    if bump is None:
        return format_version(version), False, ""
    changelog = "\n".join(f"- {subject}" for subject in releasable)
    return format_version(apply_bump(version, bump)), True, changelog


def write_output(new_version, should_release, changelog):
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        print(f"new_version={new_version}\nshould_release={should_release}\n{changelog}")
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"new_version={new_version}\n")
        handle.write(f"should_release={str(should_release).lower()}\n")
        handle.write(f"changelog<<__CHANGELOG__\n{changelog}\n__CHANGELOG__\n")


def main():
    version = latest_version()
    new_version, should_release, changelog = plan_release(version, commits_since(version))
    write_output(new_version, should_release, changelog)


if __name__ == "__main__":
    main()
